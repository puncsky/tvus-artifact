"""Model adapters: local MLX (self-hosted, full logits), Torch/transformers (models/torch_adapter.py)
and a mock backend.

Interface (both backends):

    adapter.generate(messages, seed=0, temperature=0.0, max_tokens=256) -> GenResult
    adapter.score(messages, continuations) -> list[ScoreResult]

``score`` performs *uncached fresh prefill* per continuation: a full forward pass
over prompt + continuation tokens + EOS and sums the token log-probabilities.
No length normalisation.  Costs (tokens, wall seconds, peak memory) are
recorded on every call so every intervention is accounted for.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from runner.paths import CATEGORY, apply_env


@dataclass
class Cost:
    prompt_tokens: int = 0
    generated_tokens: int = 0
    scored_tokens: int = 0
    forward_passes: int = 0
    wall_seconds: float = 0.0

    def __add__(self, other: "Cost") -> "Cost":
        return self.add(other)

    def add(self, other: "Cost") -> "Cost":
        return Cost(
            self.prompt_tokens + other.prompt_tokens,
            self.generated_tokens + other.generated_tokens,
            self.scored_tokens + other.scored_tokens,
            self.forward_passes + other.forward_passes,
            self.wall_seconds + other.wall_seconds,
        )


@dataclass
class GenResult:
    text: str
    cost: Cost
    finish: str = "stop"


@dataclass
class ScoreResult:
    continuation: str
    logprob: float            # sum of token log-probs incl. EOS
    n_tokens: int
    token_logprobs: list[float] = field(default_factory=list)
    cost: Cost = field(default_factory=Cost)


class CostLedger:
    """Accumulates cost per label; attached to an adapter."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def record(self, label: str, cost: Cost, **meta) -> None:
        self.entries.append({"label": label, **asdict(cost), **meta})

    def total(self, label_prefix: str | None = None) -> Cost:
        c = Cost()
        for e in self.entries:
            if label_prefix is None or e["label"].startswith(label_prefix):
                c = c.add(Cost(e["prompt_tokens"], e["generated_tokens"], e["scored_tokens"], e["forward_passes"], e["wall_seconds"]))
        return c


# ---------------------------------------------------------------------------
# MLX backend
# ---------------------------------------------------------------------------

class MLXAdapter:
    def __init__(self, model_path: str, *, family: str, revision: str = "", max_prompt_tokens: int = 6000):
        apply_env()
        import mlx.core as mx  # noqa: F401  (import inside category env)
        from mlx_lm import load

        self.family = family
        self.model_path = str(model_path)
        self.revision = revision
        self.model, self.tokenizer = load(self.model_path)
        self.max_prompt_tokens = max_prompt_tokens
        self.ledger = CostLedger()
        eos = getattr(self.tokenizer, "eos_token_ids", None)
        self.eos_id = sorted(eos)[0] if eos else self.tokenizer.eos_token_id
        self.name = Path(self.model_path).name
        # exact-prompt memo: byte-identical requests (e.g. in-place deletion of a hidden source) reuse the
        # earlier result; the ledger still records the ORIGINAL cost so accounting reflects what a defense
        # would have to compute, while wall time is saved (flagged memo=True).
        self._memo: dict = {}

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _merge_adjacent(messages: list[dict]) -> list[dict]:
        """Merge consecutive same-role messages (for templates that require strict alternation, e.g. Gemma)."""
        out: list[dict] = []
        for m in messages:
            if out and out[-1]["role"] == m["role"]:
                out[-1] = {"role": m["role"], "content": out[-1]["content"] + "\n\n" + m["content"]}
            else:
                out.append(dict(m))
        return out

    def _prompt_ids(self, messages: list[dict]) -> list[int]:
        try:
            text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception as e:  # jinja TemplateError: roles must alternate (Gemma); fall back to merged turns
            if "alternate" not in str(e):
                raise
            self._merged_turns = getattr(self, "_merged_turns", 0) + 1
            text = self.tokenizer.apply_chat_template(self._merge_adjacent(messages), tokenize=False, add_generation_prompt=True)
        ids = self.tokenizer.encode(text, add_special_tokens=False)
        if len(ids) > self.max_prompt_tokens:
            raise ValueError(f"prompt too long: {len(ids)} tokens")
        return ids

    def _cont_ids(self, text: str) -> list[int]:
        return self.tokenizer.encode(text, add_special_tokens=False) + [self.eos_id]

    # -- generation ------------------------------------------------------
    def generate(self, messages: list[dict], *, seed: int = 0, temperature: float = 0.0,
                 max_tokens: int = 256, label: str = "gen") -> GenResult:
        import mlx.core as mx
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        ids = self._prompt_ids(messages)
        key = ("gen", tuple(ids), seed, temperature, max_tokens)
        if key in self._memo:
            r = self._memo[key]
            self.ledger.record(label, r.cost, kind="generate", seed=seed, temperature=temperature, memo=True)
            return GenResult(text=r.text, cost=r.cost, finish=r.finish)
        mx.random.seed(seed)
        sampler = make_sampler(temp=temperature)
        t0 = time.perf_counter()
        text = generate(self.model, self.tokenizer, prompt=ids, max_tokens=max_tokens, sampler=sampler, verbose=False)
        dt = time.perf_counter() - t0
        n_gen = len(self.tokenizer.encode(text, add_special_tokens=False))
        cost = Cost(prompt_tokens=len(ids), generated_tokens=n_gen, forward_passes=1, wall_seconds=dt)
        self.ledger.record(label, cost, kind="generate", seed=seed, temperature=temperature)
        finish = "length" if n_gen >= max_tokens else "stop"
        res = GenResult(text=text, cost=cost, finish=finish)
        self._memo[key] = res
        return res

    # -- scoring ---------------------------------------------------------
    def score(self, messages: list[dict], continuations: list[str], *, label: str = "score") -> list[ScoreResult]:
        import mlx.core as mx

        p_ids = self._prompt_ids(messages)
        out = []
        for cont in continuations:
            c_ids = self._cont_ids(cont)
            key = ("score", tuple(p_ids), tuple(c_ids))
            if key in self._memo:
                r = self._memo[key]
                self.ledger.record(label, r.cost, kind="score", memo=True)
                out.append(ScoreResult(cont, r.logprob, r.n_tokens, list(r.token_logprobs), r.cost))
                continue
            full = mx.array(p_ids + c_ids)[None]
            t0 = time.perf_counter()
            logits = self.model(full)  # fresh, uncached full pass
            lp = logits[0, len(p_ids) - 1 : len(p_ids) - 1 + len(c_ids), :].astype(mx.float32)
            lp = lp - mx.logsumexp(lp, axis=-1, keepdims=True)
            tok = mx.array(c_ids)
            gathered = mx.take_along_axis(lp, tok[:, None], axis=-1)[:, 0]
            mx.eval(gathered)
            dt = time.perf_counter() - t0
            tl = [float(x) for x in gathered.tolist()]
            cost = Cost(prompt_tokens=len(p_ids), scored_tokens=len(c_ids), forward_passes=1, wall_seconds=dt)
            self.ledger.record(label, cost, kind="score")
            res = ScoreResult(cont, float(sum(tl)), len(c_ids), tl, cost)
            self._memo[key] = res
            out.append(res)
        return out

    def peak_memory_gb(self) -> float:
        import mlx.core as mx
        return mx.get_peak_memory() / 1e9

    def describe(self) -> dict:
        cfg = {}
        p = Path(self.model_path) / "config.json"
        if p.exists():
            cfg = json.loads(p.read_text())
        return {
            "backend": "mlx",
            "family": self.family,
            "model_path": self.model_path,
            "revision": self.revision,
            "model_type": cfg.get("model_type"),
            "quantization": cfg.get("quantization"),
            "eos_id": self.eos_id,
            "merged_adjacent_turns": getattr(self, "_merged_turns", 0),
        }


# ---------------------------------------------------------------------------
# Mock backend (pipeline transport only — never evidence)
# ---------------------------------------------------------------------------

class MockAdapter:
    """Scripted model: picks the candidate row mentioned most often in the prompt.

    It exists only to exercise the pipeline; its outputs are *not* evidence.
    """

    def __init__(self, family: str = "mock", bias_follow_instructions: bool = True):
        self.family = family
        self.name = "mock"
        self.ledger = CostLedger()
        self.bias = bias_follow_instructions

    def _pick(self, user_text: str) -> str:
        rows = []
        block = user_text.split("FROZEN CANDIDATE LIST", 1)[1] if "FROZEN CANDIDATE LIST" in user_text else ""
        for line in block.splitlines():
            m = re.match(r"^\d+\. (\{.*\})\s*$", line)
            if m:
                rows.append(json.loads(m.group(1)))
        if not rows:
            return "{}"
        ext = user_text.split("EXTERNAL ITEMS", 1)[1] if "EXTERNAL ITEMS" in user_text else ""
        note = user_text.split("YOUR EARLIER WORKING NOTE", 1)[1].split("EXTERNAL ITEMS")[0] if "YOUR EARLIER WORKING NOTE" in user_text else ""
        best, best_n = rows[0], -1
        for r in rows:
            key = str(list(r.values())[0])
            n = (ext + note).count(key) * 3 if self.bias else 0
            n += (user_text.split("TASK:")[1].split("\n")[0].count(key) if "TASK:" in user_text else 0)
            if n > best_n:
                best, best_n = r, n
        tool = re.search(r"- (?:action )?tool: (\S+);", user_text)
        fields = re.search(r"fields: (.*)", user_text).group(1).split(", ")
        args = {f: best.get(f, "n/a") for f in fields}
        return json.dumps({"tool": tool.group(1) if tool else "tool", "args": args})

    def generate(self, messages, *, seed=0, temperature=0.0, max_tokens=256, label="gen"):
        user = messages[-1]["content"]
        if "TOOL LOOP" in messages[0]["content"]:
            return self._tool_loop_turn(messages, seed, temperature, label)
        if "working note" in messages[0]["content"]:
            text = "Working note: " + " ".join(user.split("EXTERNAL ITEMS:")[-1].split())[:400]
        else:
            text = self._pick(user)
        cost = Cost(prompt_tokens=len(user) // 4, generated_tokens=len(text) // 4, forward_passes=1, wall_seconds=0.0)
        self.ledger.record(label, cost, kind="generate", seed=seed, temperature=temperature)
        return GenResult(text, cost)

    def _tool_loop_turn(self, messages, seed, temperature, label):
        """Scripted ReAct turns: snapshot -> candidates -> each source -> action (or plain-text note)."""
        joined = "\n".join(m["content"] for m in messages)
        last = messages[-1]["content"]
        if "not a tool call" in last or "working note" in last.lower() or "Reply with plain text" in last:
            text = "Working note: " + " ".join(joined.split("TOOL RESULT (read_source")[-1].split())[:300]
        elif "TOOL RESULT (get_snapshot)" not in joined:
            text = '{"tool": "get_snapshot"}'
        elif "TOOL RESULT (list_candidates)" not in joined:
            text = '{"tool": "list_candidates"}'
        else:
            ids_line = next((ln for ln in messages[1]["content"].splitlines() if ln.startswith("EXTERNAL ITEMS AVAILABLE")), "")
            ids = [x.strip() for x in ids_line.split(":", 1)[1].split(",")] if ":" in ids_line else []
            unread = [i for i in ids if i and i != "(none)" and f"TOOL RESULT (read_source {i})" not in joined]
            if unread and "final action" not in last:
                text = json.dumps({"tool": "read_source", "id": unread[0]})
            else:
                text = self._pick(joined.replace("FROZEN CANDIDATE LIST (choose protected fields from exactly one row):", "FROZEN CANDIDATE LIST") + "\nEXTERNAL ITEMS" + joined.split("TOOL RESULT (read_source", 1)[-1])
        cost = Cost(prompt_tokens=len(joined) // 4, generated_tokens=len(text) // 4, forward_passes=1)
        self.ledger.record(label, cost, kind="generate", seed=seed, temperature=temperature)
        return GenResult(text, cost)

    def score(self, messages, continuations, *, label="score"):
        user = "\n".join(m["content"] for m in messages) if "TOOL LOOP" in messages[0]["content"] else messages[-1]["content"]
        chosen = self._pick(user)
        out = []
        for c in continuations:
            lp = -1.0 if json.loads(c)["args"] == json.loads(chosen)["args"] else -6.0
            cost = Cost(prompt_tokens=len(user) // 4, scored_tokens=len(c) // 4, forward_passes=1)
            self.ledger.record(label, cost, kind="score")
            out.append(ScoreResult(c, lp, len(c) // 4, [], cost))
        return out

    def peak_memory_gb(self):
        return 0.0

    def describe(self):
        return {"backend": "mock", "family": self.family}


# ---------------------------------------------------------------------------

def _parse_overrides(spec: str) -> tuple[str, dict]:
    """``name@k=v,k=v`` -> (name, {k: v}); values parsed as JSON when possible (torch backend only)."""
    if "@" not in spec:
        return spec, {}
    name, _, rest = spec.partition("@")
    ov = {}
    for kv in filter(None, rest.split(",")):
        k, _, v = kv.partition("=")
        try:
            ov[k] = json.loads(v)
        except json.JSONDecodeError:
            ov[k] = v
    return name, ov


def _torch_model_path(m: dict) -> str:
    """Local snapshot dir under cache/hf when present (offline), else the hub repo id."""
    if m.get("path"):
        p = Path(m["path"])
        return str(p if p.is_absolute() else CATEGORY / p)
    repo, rev = m["hf_repo"], m.get("revision", "")
    snap = CATEGORY / "cache" / "hf" / "hub" / ("models--" + repo.replace("/", "--")) / "snapshots" / rev
    return str(snap) if rev and snap.is_dir() else repo


def load_adapter(spec: str):
    """``spec`` is ``mock`` or a key in configs/models.json.

    Entries default to the MLX backend; ``"backend": "torch"`` dispatches to ``TorchAdapter``.
    Torch specs accept overrides ``name@batch_candidates=true,dtype=bf16,device=cuda``.
    """
    if spec == "mock":
        return MockAdapter()
    name, ov = _parse_overrides(spec)
    cfg = json.loads((CATEGORY / "configs" / "models.json").read_text())
    m = cfg[name]
    if m.get("backend", "mlx") == "torch":
        from models.torch_adapter import TorchAdapter
        kw = {k: m[k] for k in ("dtype", "device", "attn_implementation", "batch_candidates",
                                "deterministic", "max_prompt_tokens", "eos_id") if k in m}
        kw.update(ov)
        return TorchAdapter(_torch_model_path(m), family=m["family"], revision=m.get("revision", ""),
                            hf_repo=m.get("hf_repo", ""), **kw)
    if ov:
        raise ValueError(f"overrides are only supported for torch specs: {spec}")
    path = Path(m["path"])
    if not path.is_absolute():
        path = CATEGORY / path
    return MLXAdapter(str(path), family=m["family"], revision=m.get("revision", ""))
