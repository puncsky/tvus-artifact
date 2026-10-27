"""Torch/transformers backend with the same interface and semantics as ``MLXAdapter``.

    adapter.generate(messages, seed=0, temperature=0.0, max_tokens=256, label="gen") -> GenResult
    adapter.score(messages, continuations, label="score") -> list[ScoreResult]

Semantics mirrored from the MLX adapter:
  * prompt = tokenizer chat template (``add_generation_prompt=True``) encoded without extra
    special tokens; prompts longer than ``max_prompt_tokens`` are rejected;
  * ``score`` = teacher-forced sum of token log-probs over continuation tokens + EOS, no length
    normalisation, one *fresh uncached* forward pass per continuation (no KV reuse across
    candidates or interventions);
  * optional ``batch_candidates=True``: the missing candidates of one prompt are right-padded into a
    single uncached forward; it must reproduce the per-candidate sums (verify_adapter checks < 1e-3);
  * greedy when ``temperature == 0``; otherwise plain temperature sampling (no top-k/top-p/repetition
    penalty, i.e. what ``mlx_lm.sample_utils.make_sampler(temp=t)`` does) seeded with
    ``torch.manual_seed(seed)``;
  * exact-prompt memo and ``CostLedger`` entries identical in shape to the MLX adapter.

Scoring EOS: ``tokenizer.eos_token_id`` (the chat turn terminator, e.g. ``<|im_end|>`` for Qwen2.5),
overridable with ``eos_id`` in configs/models.json.  Generation stops on any EOS id from the
tokenizer + generation_config.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path

from runner.paths import apply_env
from models.adapter import Cost, CostLedger, GenResult, ScoreResult

_DTYPES = {"fp32": "float32", "float32": "float32", "bf16": "bfloat16", "bfloat16": "bfloat16",
           "fp16": "float16", "float16": "float16", "4bit": "4bit"}
# every sampling knob set EXPLICITLY to its neutral value: transformers fills None fields from the checkpoint's
# generation_config.json (Qwen2.5 ships top_k=20, top_p=0.8, repetition_penalty=1.1), which would silently
# diverge from MLX's plain temperature sampler.
SAMPLING_NEUTRAL = dict(top_k=0, top_p=1.0, min_p=0.0, typical_p=1.0, epsilon_cutoff=0.0, eta_cutoff=0.0,
                        repetition_penalty=1.0, no_repeat_ngram_size=0, num_beams=1)


def pick_device(pref: str = "auto") -> str:
    import torch
    if pref and pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class TorchAdapter:
    def __init__(self, model_path: str, *, family: str, revision: str = "", dtype: str = "bf16",
                 device: str = "auto", attn_implementation: str | None = "sdpa",
                 batch_candidates: bool = False, deterministic: bool = True,
                 max_prompt_tokens: int = 6000, eos_id: int | None = None, hf_repo: str = ""):
        apply_env()
        if deterministic:
            # must be set before the first cuBLAS call for deterministic GEMMs on CUDA
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if dtype not in _DTYPES:
            raise ValueError(f"unknown dtype {dtype!r}; choose from {sorted(_DTYPES)}")
        self.family = family
        self.model_path = str(model_path)
        self.hf_repo = hf_repo
        self.revision = revision
        self.dtype = dtype
        self.device = pick_device(device)
        self.batch_candidates = bool(batch_candidates)
        self.deterministic = bool(deterministic)
        self.max_prompt_tokens = max_prompt_tokens
        self.ledger = CostLedger()
        self._memo: dict = {}   # same contract as MLXAdapter._memo (ledger records the ORIGINAL cost, memo=True)

        torch.use_deterministic_algorithms(self.deterministic, warn_only=True)
        torch.backends.cudnn.benchmark = False
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.deterministic = self.deterministic
        # no TF32 shortcuts: fp32 must be real fp32 and bf16 matmuls keep fp32 accumulation
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False

        load_kw: dict = {}
        if attn_implementation:
            load_kw["attn_implementation"] = attn_implementation
        if dtype == "4bit":
            if importlib.util.find_spec("bitsandbytes") is None:
                raise RuntimeError("dtype=4bit requires bitsandbytes, which is not installed in this env")
            from transformers import BitsAndBytesConfig
            load_kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
            load_kw["device_map"] = {"": self.device}
        else:
            load_kw["dtype"] = getattr(torch, _DTYPES[dtype])
        src_kw = {} if Path(self.model_path).is_dir() else {"revision": revision or None}
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, **src_kw)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_path, **src_kw, **load_kw)
        if dtype != "4bit":
            self.model.to(self.device)
        self.model.eval()
        torch.set_grad_enabled(False)
        self.attn_implementation = getattr(self.model.config, "_attn_implementation", attn_implementation)

        gen_eos = getattr(self.model.generation_config, "eos_token_id", None)
        gen_eos = [gen_eos] if isinstance(gen_eos, int) else list(gen_eos or [])
        self.eos_id = int(eos_id) if eos_id is not None else int(self.tokenizer.eos_token_id)
        self.stop_ids = sorted({self.eos_id, *gen_eos, *([self.tokenizer.eos_token_id] if self.tokenizer.eos_token_id is not None else [])})
        pad = self.tokenizer.pad_token_id
        self.pad_id = int(pad) if pad is not None else self.eos_id
        self.name = Path(self.model_path).name if Path(self.model_path).is_dir() else self.model_path.split("/")[-1]
        try:
            import inspect
            self._has_logits_to_keep = "logits_to_keep" in inspect.signature(self.model.forward).parameters
        except (TypeError, ValueError):
            self._has_logits_to_keep = False
        if self.device == "cuda":
            torch.cuda.reset_peak_memory_stats()

    # -- helpers (identical to MLXAdapter) ---------------------------------
    @staticmethod
    def _merge_adjacent(messages: list[dict]) -> list[dict]:
        """Merge consecutive same-role messages (templates that require strict alternation: Gemma, Mistral)."""
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
        except Exception as e:  # jinja TemplateError: roles must alternate; same fallback as MLXAdapter (protocol-v2 addendum 2)
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

    def _acc_dtype(self):
        """log-softmax accumulation dtype: float64 (a float32 CPU log-softmax over a 152k vocab is off by
        ~1.5e-4 nats); MPS has no float64, so float32 there."""
        import torch
        return torch.float32 if self.device == "mps" else torch.float64

    def _sync(self) -> None:
        import torch
        if self.device == "cuda":
            torch.cuda.synchronize()
        elif self.device == "mps":
            torch.mps.synchronize()

    # -- generation ------------------------------------------------------
    def generate(self, messages: list[dict], *, seed: int = 0, temperature: float = 0.0,
                 max_tokens: int = 256, label: str = "gen") -> GenResult:
        import torch
        from transformers import GenerationConfig

        ids = self._prompt_ids(messages)
        key = ("gen", tuple(ids), seed, temperature, max_tokens)
        if key in self._memo:
            r = self._memo[key]
            self.ledger.record(label, r.cost, kind="generate", seed=seed, temperature=temperature, memo=True)
            return GenResult(text=r.text, cost=r.cost, finish=r.finish)
        torch.manual_seed(seed)
        if self.device == "cuda":
            torch.cuda.manual_seed_all(seed)
        sample = temperature > 0
        gcfg = GenerationConfig(
            max_new_tokens=max_tokens, do_sample=sample, temperature=temperature if sample else 1.0,
            **SAMPLING_NEUTRAL, eos_token_id=self.stop_ids, pad_token_id=self.pad_id)
        inp = torch.tensor([ids], device=self.device)
        t0 = time.perf_counter()
        out = self.model.generate(inp, attention_mask=torch.ones_like(inp), generation_config=gcfg)
        self._sync()
        dt = time.perf_counter() - t0
        new = out[0, len(ids):].tolist()
        if new and new[-1] in self.stop_ids:
            new = new[:-1]   # mlx_lm.generate does not emit the terminating EOS either
        text = self.tokenizer.decode(new, skip_special_tokens=False)
        n_gen = len(self.tokenizer.encode(text, add_special_tokens=False))
        cost = Cost(prompt_tokens=len(ids), generated_tokens=n_gen, forward_passes=1, wall_seconds=dt)
        self.ledger.record(label, cost, kind="generate", seed=seed, temperature=temperature)
        finish = "length" if n_gen >= max_tokens else "stop"
        res = GenResult(text=text, cost=cost, finish=finish)
        self._memo[key] = res
        return res

    # -- scoring ---------------------------------------------------------
    def _token_logprobs(self, p_ids: list[int], c_ids: list[int]) -> list[float]:
        """One fresh, uncached forward over prompt + continuation(+EOS)."""
        import torch
        full = torch.tensor([p_ids + c_ids], device=self.device)
        kw = {"use_cache": False}
        if self._has_logits_to_keep:
            kw["logits_to_keep"] = len(c_ids) + 1   # positions len(p)-1 .. end
        logits = self.model(full, **kw).logits[0]
        lp = logits[-(len(c_ids) + 1):-1] if self._has_logits_to_keep else \
            logits[len(p_ids) - 1: len(p_ids) - 1 + len(c_ids)]
        lp = torch.log_softmax(lp.to(self._acc_dtype()), dim=-1)
        tok = torch.tensor(c_ids, device=self.device)
        return lp.gather(-1, tok[:, None])[:, 0].tolist()

    def _token_logprobs_batch(self, p_ids: list[int], c_list: list[list[int]]) -> list[list[float]]:
        """All continuations in one uncached forward, right-padded (causal ⇒ pads never influence
        the real positions); per-row gather of the continuation positions."""
        import torch
        seqs = [p_ids + c for c in c_list]
        T = max(len(s) for s in seqs)
        ids = torch.full((len(seqs), T), self.pad_id, dtype=torch.long)
        mask = torch.zeros((len(seqs), T), dtype=torch.long)
        for i, s in enumerate(seqs):
            ids[i, :len(s)] = torch.tensor(s)
            mask[i, :len(s)] = 1
        ids, mask = ids.to(self.device), mask.to(self.device)
        kw = {"use_cache": False}
        start = len(p_ids) - 1
        if self._has_logits_to_keep:
            kw["logits_to_keep"] = T - start
        logits = self.model(ids, attention_mask=mask, **kw).logits
        off = start if not self._has_logits_to_keep else 0
        out = []
        for i, c in enumerate(c_list):
            lp = torch.log_softmax(logits[i, off: off + len(c)].to(self._acc_dtype()), dim=-1)
            tok = torch.tensor(c, device=self.device)
            out.append(lp.gather(-1, tok[:, None])[:, 0].tolist())
        return out

    def score(self, messages: list[dict], continuations: list[str], *, label: str = "score") -> list[ScoreResult]:
        p_ids = self._prompt_ids(messages)
        out: list[ScoreResult | None] = [None] * len(continuations)
        todo: list[tuple[int, str, list[int], tuple]] = []
        for i, cont in enumerate(continuations):
            c_ids = self._cont_ids(cont)
            key = ("score", tuple(p_ids), tuple(c_ids))
            if key in self._memo:
                r = self._memo[key]
                self.ledger.record(label, r.cost, kind="score", memo=True)
                out[i] = r
            else:
                todo.append((i, cont, c_ids, key))
        if self.batch_candidates and len(todo) > 1:
            t0 = time.perf_counter()
            tls = self._token_logprobs_batch(p_ids, [c for _, _, c, _ in todo])
            self._sync()
            dt = (time.perf_counter() - t0) / len(todo)   # wall time split evenly across the batch
            timed = [(item, tl, dt) for item, tl in zip(todo, tls)]
        else:
            timed = []
            for item in todo:
                t0 = time.perf_counter()
                tl = self._token_logprobs(p_ids, item[2])
                self._sync()
                timed.append((item, tl, time.perf_counter() - t0))
        for (i, cont, c_ids, key), tl, dt in timed:
            cost = Cost(prompt_tokens=len(p_ids), scored_tokens=len(c_ids), forward_passes=1, wall_seconds=dt)
            self.ledger.record(label, cost, kind="score")
            res = ScoreResult(cont, float(sum(tl)), len(c_ids), [float(x) for x in tl], cost)
            self._memo[key] = res
            out[i] = res
        return out  # type: ignore[return-value]

    # -- accounting ------------------------------------------------------
    def peak_memory_gb(self) -> float:
        import torch
        if self.device == "cuda":
            return torch.cuda.max_memory_allocated() / 1e9
        if self.device == "mps":
            return torch.mps.driver_allocated_memory() / 1e9
        # CPU: process peak RSS (bytes on macOS, KiB on Linux) — includes interpreter + weights
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return rss / 1e9 if sys.platform == "darwin" else rss * 1024 / 1e9

    def describe(self) -> dict:
        import torch
        import transformers
        cfg = {}
        p = Path(self.model_path) / "config.json"
        if p.exists():
            cfg = json.loads(p.read_text())
        d = {
            "backend": "torch",
            "family": self.family,
            "model_path": self.model_path,
            "hf_repo": self.hf_repo,
            "revision": self.revision,
            "model_type": cfg.get("model_type"),
            "quantization": cfg.get("quantization_config") or ({"bnb": "nf4"} if self.dtype == "4bit" else None),
            "eos_id": self.eos_id,
            "stop_ids": self.stop_ids,
            "dtype": self.dtype,
            "device": self.device,
            "attn_implementation": self.attn_implementation,
            "batch_candidates": self.batch_candidates,
            "sampling": {"greedy_if_temperature_0": True, "seeding": "torch.manual_seed + cuda.manual_seed_all per generate",
                         **SAMPLING_NEUTRAL},
            "logits_to_keep": self._has_logits_to_keep,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "python": platform.python_version(),
            "machine": platform.machine(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "deterministic_warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "allow_tf32": torch.backends.cuda.matmul.allow_tf32,
            "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            "num_threads": torch.get_num_threads(),
        }
        if self.device == "cuda":
            d.update({"cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
                      "capability": list(torch.cuda.get_device_capability(0))})
        if importlib.util.find_spec("bitsandbytes") is not None:
            import bitsandbytes
            d["bitsandbytes"] = bitsandbytes.__version__
        return d
