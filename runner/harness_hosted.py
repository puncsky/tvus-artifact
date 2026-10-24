"""Shared plumbing for non-Anthropic hosted agents under H3 (OpenAI, Gemini).

H3 semantics are owned by ``harness_claude``: the tool loop (``run_loop``), the
nudge-retry for the final action (``_final_action``), in-place last-turn edits
(``_inplace``), clean-checkpoint closure and trusted reconstruction.  Those
functions operate on a *canonical* transcript (Anthropic-style content blocks:
``text`` / ``tool_use`` / ``tool_result``) and talk to the model only through
``agent.step(system, messages, tools, label=, temperature=)``.

A provider agent therefore only has to (1) translate the canonical transcript
and the canonical tool list into its own wire format, and (2) return a
duck-typed response (``stop_reason`` + ``content`` blocks).  Provider state that
must survive the round trip (OpenAI encrypted reasoning items, Gemini thought
signatures) travels inside an ``opaque`` block that the canonical edit
functions never touch.  Re-exporting ``run_agent``/``reconstruct`` from
``harness_claude`` keeps the loop code byte-identical across providers.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

from models.adapter import Cost, CostLedger, GenResult
from runner.harness_claude import run_agent, reconstruct, H3_SYSTEM  # noqa: F401  (re-exported: identical H3 loop)

_KEYLIKE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[A-Za-z0-9_\-]{8,}|(?:api[_-]?key|key)=[A-Za-z0-9_\-]{8,})", re.I)


def scrub(text: str) -> str:
    """Remove anything that looks like an API key (errors are logged; keys must never be)."""
    return _KEYLIKE.sub("[REDACTED]", str(text))


class Block:
    """Duck-typed content block consumed by ``harness_claude._serialize_content``."""

    def __init__(self, type: str, **kw):
        self.type = type
        self.__dict__.update(kw)

    def to_dict(self) -> dict:   # used for ``opaque`` blocks only
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class HostedResponse:
    stop_reason: str                  # end_turn | tool_use | refusal | max_tokens | empty | <provider finish>
    content: list = field(default_factory=list)
    raw_finish: str = ""


class HostedAgent:
    """USD ledger + spend cap + text ``generate`` shared by the hosted providers."""

    family = "hosted"
    PRICES: dict = {}          # model -> {"input", "cached_input", "cache_write", "output"} USD per 1M tokens
    PRICE_SOURCE: dict = {}
    MAX_OUTPUT_TOKENS = 8000   # includes reasoning/thinking tokens on both providers

    def __init__(self, model: str, cap_usd: float = 50.0, effort: str = "medium", spend_file: str | None = None):
        self.model, self.cap_usd, self.effort = model, cap_usd, effort
        self.spend_file = spend_file
        self.spent_usd = 0.0
        self.tokens = {"input": 0, "cached_input": 0, "output": 0, "reasoning": 0}
        if spend_file and os.path.exists(spend_file):
            prev = json.load(open(spend_file))
            self.spent_usd = prev.get("spent_usd", 0.0)
            self.tokens.update(prev.get("tokens", {}))
        self.ledger = CostLedger()
        self.name = model
        self.price = self.PRICES.get(model)          # None => USD unknown, ledger counts tokens only
        self.temperature_supported: bool | None = None

    # -- accounting -------------------------------------------------------------------------------
    def _usd(self, inp: int, cached: int, cache_write: int, out: int) -> float | None:
        p = self.price
        if p is None:
            return None
        fresh = max(inp - cached - cache_write, 0)
        return (fresh * p["input"] + cached * (p.get("cached_input") or p["input"])
                + cache_write * (p.get("cache_write") or p["input"]) + out * p["output"]) / 1e6

    def _record(self, label: str, *, inp: int, cached: int, cache_write: int, out: int, reasoning: int,
                dt: float, stop: str) -> Cost:
        usd = self._usd(inp, cached, cache_write, out)
        self.spent_usd += usd or 0.0
        for k, v in (("input", inp), ("cached_input", cached), ("output", out), ("reasoning", reasoning)):
            self.tokens[k] += v
        if self.spend_file:
            json.dump({"spent_usd": round(self.spent_usd, 6), "usd_known": self.price is not None, "tokens": self.tokens,
                       "model": self.model, "provider": self.family,
                       "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(self.spend_file, "w"))
        cost = Cost(prompt_tokens=inp, generated_tokens=out, forward_passes=1, wall_seconds=dt)
        self.ledger.record(label, cost, kind="api", usd=usd or 0.0, usd_known=usd is not None, model=self.model,
                           provider=self.family, cached_tokens=cached, reasoning_tokens=reasoning, stop=stop)
        return cost

    def check_cap(self) -> None:
        if self.price is not None and self.spent_usd >= self.cap_usd:
            raise RuntimeError(f"spend cap reached: ${self.spent_usd:.2f} >= ${self.cap_usd:.2f}")

    def peak_memory_gb(self) -> float:
        return 0.0

    def describe(self) -> dict:
        return {"harness": "h3", "provider": self.family, "family": self.family, "model": self.model, "effort": self.effort,
                "max_output_tokens": self.MAX_OUTPUT_TOKENS, "cap_usd": self.cap_usd,
                "price_usd_per_mtok": self.price, "usd_known": self.price is not None,
                "price_source": self.PRICE_SOURCE.get(self.model),
                "temperature_supported": self.temperature_supported,
                "fallbacks": "disabled (model identity must stay fixed for the study)",
                "loop": "harness_claude.run_loop/_final_action/_inplace/reconstruct (shared H3 code path)"}

    def step(self, system: str, messages: list[dict], tools: list[dict], *, label: str, temperature: float | None = None):
        raise NotImplementedError

    def generate(self, messages: list[dict], *, seed: int = 0, temperature: float = 0.0, max_tokens: int = 256, label: str = "gen"):
        system = "\n".join(m["content"] for m in messages if m["role"] == "system") or "You are a precise assistant."
        user = [m for m in messages if m["role"] != "system"]
        resp, cost = self.step(system, user, [], label=label, temperature=temperature)
        text = "".join(b.text for b in resp.content if b.type == "text")
        return GenResult(text=text, cost=cost, finish="refusal" if resp.stop_reason == "refusal" else "stop")

    def score(self, *a, **k):
        raise NotImplementedError("hosted API: no log-probabilities")


def tool_names_by_id(messages: list[dict]) -> dict[str, str]:
    out = {}
    for m in messages:
        if m["role"] == "assistant" and isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_use":
                    out[b["id"]] = b["name"]
    return out
