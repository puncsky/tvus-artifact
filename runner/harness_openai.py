"""H3 with a hosted OpenAI agent (Responses API, native function calling).

Same four tools, same canonical transcript and the same loop/edit/reconstruction
code as ``harness_claude`` (see ``harness_hosted``); this module only translates
the canonical transcript to Responses-API input items and back.

* Tools are ``{"type": "function", ..., "strict": true}`` with the same JSON
  schemas as the Claude tools (strict mode accepts them unchanged: every
  property required, ``additionalProperties: false``).
* Requests are stateless (``store=False``); reasoning items are requested with
  ``include=["reasoning.encrypted_content"]`` and carried in the transcript as
  ``opaque`` blocks so multi-turn reasoning context is preserved verbatim.
* Refusals: a ``refusal`` output part or an ``incomplete`` response with reason
  ``content_filter`` -> ``stop_reason == "refusal"`` (recorded as the outcome).
* Rate limits / 5xx: SDK retries (``max_retries``).
"""
from __future__ import annotations

import json
import time

from runner.harness_hosted import HostedAgent, HostedResponse, Block, scrub, run_agent, reconstruct  # noqa: F401

DEFAULT_MODEL = "gpt-5.6-sol"
PRICING_URL = "https://developers.openai.com/api/docs/pricing"
# USD per 1M tokens, Standard tier, short context — fetched from PRICING_URL on 2026-10-05
PRICES = {
    "gpt-5.6-sol": {"input": 4.00, "cached_input": 0.40, "cache_write": 5.00, "output": 20.00},
    "gpt-5.6-terra": {"input": 2.00, "cached_input": 0.20, "cache_write": 2.50, "output": 12.00},
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "cache_write": None, "output": 30.00},
    "gpt-5.5-2026-04-23": {"input": 5.00, "cached_input": 0.50, "cache_write": None, "output": 30.00},
}


def _tools(tools: list[dict]) -> list[dict]:
    return [{"type": "function", "name": t["name"], "description": t.get("description", ""),
             "parameters": t["input_schema"], "strict": bool(t.get("strict", True))} for t in tools]


def _input_items(messages: list[dict]) -> list[dict]:
    items: list[dict] = []
    for m in messages:
        c = m["content"]
        if isinstance(c, str):
            items.append({"role": m["role"], "content": c})
            continue
        for b in c:
            t = b.get("type")
            if t == "text":
                if b.get("text"):
                    items.append({"role": m["role"], "content": b["text"]})
            elif t == "tool_use":
                items.append({"type": "function_call", "call_id": b["id"], "name": b["name"],
                              "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False)})
            elif t == "tool_result":
                items.append({"type": "function_call_output", "call_id": b["tool_use_id"], "output": b["content"]})
            elif t == "opaque" and b.get("provider") == "openai":
                items.append(b["item"])
    return items


class OpenAIAgent(HostedAgent):
    family = "openai"
    PRICES = PRICES
    PRICE_SOURCE = {k: {"url": PRICING_URL, "fetched": "2026-10-05", "tier": "standard, short context"} for k in PRICES}

    def __init__(self, model: str = DEFAULT_MODEL, cap_usd: float = 50.0, effort: str = "medium", spend_file: str | None = None):
        super().__init__(model, cap_usd, effort, spend_file)
        import openai
        self.openai = openai
        self.client = openai.OpenAI(max_retries=8)    # credentials from OPENAI_API_KEY; 429/5xx retried by the SDK

    def _call(self, kwargs: dict):
        try:
            return self.client.responses.create(**kwargs)
        except self.openai.BadRequestError as e:
            msg = str(e)
            if "temperature" in msg and "temperature" in kwargs:
                self.temperature_supported = False
                kwargs.pop("temperature")
                return self._call(kwargs)
            if "reasoning" in msg and "reasoning" in kwargs:
                kwargs.pop("reasoning")
                kwargs.pop("include", None)
                return self._call(kwargs)
            raise RuntimeError("openai bad request: " + scrub(msg)) from None
        except self.openai.APIError as e:
            raise RuntimeError(f"openai API error ({type(e).__name__}): " + scrub(str(e))) from None

    def step(self, system: str, messages: list[dict], tools: list[dict], *, label: str, temperature: float | None = None):
        self.check_cap()
        kwargs = dict(model=self.model, instructions=system, input=_input_items(messages), store=False,
                      max_output_tokens=self.MAX_OUTPUT_TOKENS, reasoning={"effort": self.effort},
                      include=["reasoning.encrypted_content"])
        if tools:
            kwargs["tools"] = _tools(tools)
        if temperature is not None and self.temperature_supported is not False:
            kwargs["temperature"] = temperature
        t0 = time.perf_counter()
        resp = self._call(kwargs)
        if "temperature" in kwargs and self.temperature_supported is None:
            self.temperature_supported = True
        content, refusal = [], False
        for it in resp.output or []:
            if it.type == "reasoning":
                d = it.model_dump(exclude_none=True)
                if d.get("encrypted_content"):
                    content.append(Block("opaque", provider="openai", item=d))
            elif it.type == "message":
                for part in it.content or []:
                    if part.type == "output_text":
                        content.append(Block("text", text=part.text))
                    elif part.type == "refusal":
                        refusal = True
                        content.append(Block("text", text=part.refusal))
            elif it.type == "function_call":
                try:
                    args = json.loads(it.arguments or "{}")
                except json.JSONDecodeError:
                    args = {"_unparsed_arguments": it.arguments}
                content.append(Block("tool_use", id=it.call_id, name=it.name, input=args if isinstance(args, dict) else {"_value": args}))
        reason = getattr(getattr(resp, "incomplete_details", None), "reason", None) or ""
        if refusal or reason == "content_filter":
            stop = "refusal"
        elif reason == "max_output_tokens":
            stop = "max_tokens"
        elif any(b.type == "tool_use" for b in content):
            stop = "tool_use"
        elif not any(b.type == "text" and b.text for b in content):
            stop = "empty"
        else:
            stop = "end_turn"
        u = resp.usage
        cached = getattr(u.input_tokens_details, "cached_tokens", 0) or 0 if u else 0
        cwrite = getattr(u.input_tokens_details, "cache_write_tokens", 0) or 0 if u else 0
        reasoning = getattr(u.output_tokens_details, "reasoning_tokens", 0) or 0 if u else 0
        cost = self._record(label, inp=u.input_tokens if u else 0, cached=cached, cache_write=cwrite,
                            out=u.output_tokens if u else 0, reasoning=reasoning, dt=time.perf_counter() - t0, stop=stop)
        return HostedResponse(stop, content, raw_finish=resp.status or ""), cost

    def describe(self) -> dict:
        d = super().describe()
        d.update({"backend": "openai-responses-api", "store": False, "reasoning_effort": self.effort,
                  "tool_schema": "function tools, strict=true (same JSON schemas as the Claude tools)"})
        return d
