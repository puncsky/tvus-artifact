"""H3 with a hosted Google Gemini agent (google-genai, manual function calling).

Same four tools, same canonical transcript and the same loop/edit/reconstruction
code as ``harness_claude`` (see ``harness_hosted``); this module only translates
the canonical transcript to ``types.Content`` and back.

* Tools are ``FunctionDeclaration``s with ``parameters_json_schema`` = the Claude
  tool schemas.  Gemini has no per-function ``strict`` flag.  Whenever tools are
  offered the call uses ``FunctionCallingConfig(mode=ANY)`` (schema-constrained,
  function calls only).  Reason: the shared contract prompt says "Reply with a
  single JSON object"; under AUTO and VALIDATED, gemini-3.1-pro-preview obeys that
  literally and writes the action as fenced text JSON (``"tool":
  "default_api:post_match"``) on every nudge, so every H3 action would be a parse
  failure (dry-run probe 2026-10-05).  Text-only turns (history notes, release
  extraction) pass no tools and stay free text.  Asymmetry vs Claude/OpenAI
  (tool_choice auto): Gemini cannot answer a tool turn in text, so text refusals
  are impossible there; safety blocks are still recorded as refusals.  Automatic
  function calling is off.
* Each model turn is stored verbatim (``Content.model_dump(mode="json")``, thought
  signatures base64-encoded) as an ``opaque`` block next to the canonical
  ``text``/``tool_use`` blocks, and replayed unchanged; only ``tool_result``
  blocks (user turns) are ever edited by the interventions.
* Refusals: ``prompt_feedback.block_reason`` or a safety-type finish reason ->
  ``stop_reason == "refusal"`` (recorded as the outcome).
* Rate limits / 5xx: SDK retries (``HttpRetryOptions``).
"""
from __future__ import annotations

import time

from runner.harness_hosted import HostedAgent, HostedResponse, Block, scrub, tool_names_by_id, run_agent, reconstruct  # noqa: F401

DEFAULT_MODEL = "gemini-3.1-pro-preview"
PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"
# USD per 1M tokens, paid tier, Standard, prompts <= 200k tokens — fetched from PRICING_URL on 2026-10-05
PRICES = {
    "gemini-3.1-pro-preview": {"input": 2.00, "cached_input": 0.20, "cache_write": None, "output": 12.00},
}
REFUSAL_FINISH = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT"}
_LOCAL_ID = "gemini-local-"


class GeminiAgent(HostedAgent):
    family = "gemini"
    PRICES = PRICES
    PRICE_SOURCE = {k: {"url": PRICING_URL, "fetched": "2026-10-05", "tier": "paid, standard, <=200k prompt"} for k in PRICES}

    def __init__(self, model: str = DEFAULT_MODEL, cap_usd: float = 50.0, effort: str = "medium", spend_file: str | None = None):
        super().__init__(model, cap_usd, effort, spend_file)
        from google import genai
        from google.genai import types, errors
        self.types, self.errors = types, errors
        # credentials from GEMINI_API_KEY; 408/429/5xx retried by the SDK
        self.client = genai.Client(http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=8, max_delay=90.0)))
        self.calling_mode = "ANY"
        self._n_local = 0

    # -- canonical <-> Content ---------------------------------------------------------------------
    def _contents(self, messages: list[dict]) -> list:
        T = self.types
        names = tool_names_by_id(messages)
        out = []
        for m in messages:
            c = m["content"]
            if m["role"] == "assistant":
                if isinstance(c, list):
                    op = next((b for b in c if b.get("type") == "opaque" and b.get("provider") == "gemini"), None)
                    if op is not None:
                        out.append(T.Content.model_validate(op["content"]))
                        continue
                    parts = []
                    for b in c:
                        if b.get("type") == "text" and b.get("text"):
                            parts.append(T.Part(text=b["text"]))
                        elif b.get("type") == "tool_use":
                            parts.append(T.Part(function_call=T.FunctionCall(name=b["name"], args=b.get("input") or {},
                                                                             id=None if b["id"].startswith(_LOCAL_ID) else b["id"])))
                else:
                    parts = [T.Part(text=c)] if c else []
                if parts:
                    out.append(T.Content(role="model", parts=parts))
                continue
            if isinstance(c, str):
                out.append(T.Content(role="user", parts=[T.Part(text=c)]))
                continue
            parts = []
            for b in c:
                if b.get("type") == "tool_result":
                    tid = b["tool_use_id"]
                    parts.append(T.Part(function_response=T.FunctionResponse(
                        name=names.get(tid, "tool"), id=None if tid.startswith(_LOCAL_ID) else tid, response={"result": b["content"]})))
                elif b.get("type") == "text" and b.get("text"):
                    parts.append(T.Part(text=b["text"]))
            if parts:
                out.append(T.Content(role="user", parts=parts))
        return out

    def _config(self, system: str, tools: list[dict], temperature: float | None):
        T = self.types
        kw = dict(system_instruction=system, max_output_tokens=self.MAX_OUTPUT_TOKENS,
                  automatic_function_calling=T.AutomaticFunctionCallingConfig(disable=True),
                  thinking_config=T.ThinkingConfig(thinking_level=self.effort.upper()))
        if temperature is not None and self.temperature_supported is not False:
            kw["temperature"] = temperature
        if tools:
            kw["tools"] = [T.Tool(function_declarations=[
                T.FunctionDeclaration(name=t["name"], description=t.get("description", ""), parameters_json_schema=t["input_schema"])
                for t in tools])]
            kw["tool_config"] = T.ToolConfig(function_calling_config=T.FunctionCallingConfig(mode=self.calling_mode))
        return T.GenerateContentConfig(**kw)

    def _call(self, contents, system, tools, temperature):
        try:
            return self.client.models.generate_content(model=self.model, contents=contents, config=self._config(system, tools, temperature))
        except self.errors.ClientError as e:
            msg = str(e)
            if tools and self.calling_mode != "AUTO" and "function_calling_config" in msg.lower():
                self.calling_mode = "AUTO"
                return self._call(contents, system, tools, temperature)
            if "temperature" in msg.lower() and temperature is not None and self.temperature_supported is not False:
                self.temperature_supported = False
                return self._call(contents, system, tools, None)
            raise RuntimeError("gemini client error: " + scrub(msg)) from None
        except self.errors.APIError as e:
            raise RuntimeError(f"gemini API error ({type(e).__name__}): " + scrub(str(e))) from None

    def step(self, system: str, messages: list[dict], tools: list[dict], *, label: str, temperature: float | None = None):
        self.check_cap()
        t0 = time.perf_counter()
        resp = self._call(self._contents(messages), system, tools, temperature)
        if temperature is not None and self.temperature_supported is None:
            self.temperature_supported = True
        content: list = []
        block = getattr(getattr(resp, "prompt_feedback", None), "block_reason", None)
        cand = resp.candidates[0] if resp.candidates else None
        finish = str(getattr(getattr(cand, "finish_reason", None), "value", getattr(cand, "finish_reason", "")) or "") if cand else ""
        if cand is not None and cand.content is not None and cand.content.parts:
            for p in cand.content.parts:
                if p.thought:
                    continue
                if p.function_call is not None:
                    fid = p.function_call.id
                    if not fid:
                        self._n_local += 1
                        fid = f"{_LOCAL_ID}{self._n_local}"
                    content.append(Block("tool_use", id=fid, name=p.function_call.name, input=dict(p.function_call.args or {})))
                elif p.text:
                    content.append(Block("text", text=p.text))
            content.append(Block("opaque", provider="gemini", content=cand.content.model_dump(mode="json", exclude_none=True)))
        if block or cand is None or finish in REFUSAL_FINISH:
            stop = "refusal"
        elif finish == "MAX_TOKENS":
            stop = "max_tokens"
        elif any(b.type == "tool_use" for b in content):
            stop = "tool_use"
        elif not any(b.type == "text" and b.text for b in content):
            stop = "empty" if finish in ("STOP", "") else finish.lower()
        else:
            stop = "end_turn"
        u = resp.usage_metadata
        prompt = (u.prompt_token_count or 0) + (u.tool_use_prompt_token_count or 0) if u else 0
        cached = (u.cached_content_token_count or 0) if u else 0
        thoughts = (u.thoughts_token_count or 0) if u else 0
        out = ((u.candidates_token_count or 0) + thoughts) if u else 0
        if prompt > 200_000:
            print(f"warning: {label}: prompt {prompt} tokens exceeds the <=200k price tier; USD understated", flush=True)
        cost = self._record(label, inp=prompt, cached=cached, cache_write=0, out=out, reasoning=thoughts,
                            dt=time.perf_counter() - t0, stop=stop if not block else f"refusal:{block}")
        return HostedResponse(stop, content, raw_finish=finish or str(block or "")), cost

    def describe(self) -> dict:
        d = super().describe()
        d.update({"backend": "gemini-api (google-genai)", "thinking_level": self.effort.upper(),
                  "function_calling_mode": self.calling_mode, "automatic_function_calling": "disabled",
                  "tool_schema": "FunctionDeclaration.parameters_json_schema (same JSON schemas as the Claude tools); "
                                 "no per-function strict flag; tool turns forced with FunctionCallingConfig mode (see function_calling_mode)"})
        return d
