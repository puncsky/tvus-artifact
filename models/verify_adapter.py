"""Independent numerical verification of full-action teacher-forced scoring.

Checks (real model, no mock):
 1. numpy recompute: log-softmax over the gathered positions from the same logits
    equals the adapter's per-token log-probs (independent arithmetic path).
 2. incremental path: prompt prefill with a KV cache, then continuation tokens
    fed one at a time; summed log-probs agree with the single uncached pass
    (independent compute path; tolerance accounts for quantized kernels).
 3. EOS is included: n_tokens == len(encode(text)) + 1 and the last token is EOS.
 4. greedy determinism: two greedy generations are identical.
Torch backend additionally: 5. right-padded batched candidates == per-candidate sums (< 1e-3).
Backends: MLX (mlx.core recompute / mlx_lm prompt cache — unchanged) and Torch
(numpy recompute from torch logits / ``past_key_values``).
Writes reports/model-readiness/verify-<model>.json.

Comparison mode (no checks):
    verify_adapter.py <spec> --compare-with <other-spec | scores-json> [--cases S01,P01,H02]
scores the clean + attack contexts of the cases with both adapters and reports argmax agreement
and the Spearman correlation of candidate-relative log-odds (lp_i - logsumexp_j lp_j).
``--dump-scores`` writes the per-context scores of <spec> to
reports/model-readiness/scores-<spec>.json, so backends living in different venvs / machines
(MLX on the Mac, Torch on CUDA) can be compared by passing that file to ``--compare-with``.
"""
from __future__ import annotations
import argparse, json, math, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from runner.paths import resolve_out
from runner.schema import load_case, project, serialize_candidate
from runner.prompting import build_action_prompt
from models.adapter import load_adapter

OUT_DIR = "reports/model-readiness"   # --out-dir overrides (keeps historical readiness reports untouched)


def _safe(spec: str) -> str:
    return spec.replace("/", "_").replace("@", "_").replace("=", "-").replace(",", "_")


# ---------------------------------------------------------------------------
# backend-specific checks 1 + 2
# ---------------------------------------------------------------------------

def _mlx_checks(ad, p_ids, res, conts):
    import mlx.core as mx
    from mlx_lm.models.cache import make_prompt_cache
    # 1. numpy recompute
    max_err = 0.0
    for r, cont in zip(res, conts):
        c_ids = ad._cont_ids(cont)
        logits = ad.model(mx.array(p_ids + c_ids)[None])
        L = np.array(logits[0, len(p_ids)-1:len(p_ids)-1+len(c_ids), :].astype(mx.float32), dtype=np.float64)
        lse = np.log(np.exp(L - L.max(1, keepdims=True)).sum(1)) + L.max(1)
        tok_lp = L[np.arange(len(c_ids)), c_ids] - lse
        max_err = max(max_err, float(np.abs(tok_lp - np.array(r.token_logprobs)).max()))

    # 2. incremental KV-cache path
    diffs = []
    for r, cont in zip(res, conts):
        c_ids = ad._cont_ids(cont)
        cache = make_prompt_cache(ad.model)
        logits = ad.model(mx.array(p_ids)[None], cache=cache)
        lp_sum = 0.0
        last = logits[0, -1].astype(mx.float32)
        for t in c_ids:
            lp = last - mx.logsumexp(last)
            lp_sum += float(lp[t])
            logits = ad.model(mx.array([t])[None], cache=cache)
            last = logits[0, -1].astype(mx.float32)
        diffs.append(abs(lp_sum - r.logprob))
    return max_err, diffs


def _torch_checks(ad, p_ids, res, conts):
    import torch
    dev = ad.device
    # 1. numpy recompute: full-sequence logits (no logits_to_keep slicing), float64 log-softmax in numpy
    max_err = 0.0
    for r, cont in zip(res, conts):
        c_ids = ad._cont_ids(cont)
        with torch.no_grad():
            logits = ad.model(torch.tensor([p_ids + c_ids], device=dev), use_cache=False).logits
        L = logits[0, len(p_ids)-1:len(p_ids)-1+len(c_ids), :].float().cpu().numpy().astype(np.float64)
        lse = np.log(np.exp(L - L.max(1, keepdims=True)).sum(1)) + L.max(1)
        tok_lp = L[np.arange(len(c_ids)), c_ids] - lse
        max_err = max(max_err, float(np.abs(tok_lp - np.array(r.token_logprobs)).max()))

    # 2. incremental path: prefill with past_key_values, then one token at a time
    diffs = []
    for r, cont in zip(res, conts):
        c_ids = ad._cont_ids(cont)
        with torch.no_grad():
            out = ad.model(torch.tensor([p_ids], device=dev), use_cache=True)
            past = out.past_key_values
            last = out.logits[0, -1].float()
            lp_sum = 0.0
            for t in c_ids:
                lp = last - torch.logsumexp(last, dim=-1)
                lp_sum += float(lp[t])
                out = ad.model(torch.tensor([[t]], device=dev), past_key_values=past, use_cache=True)
                past = out.past_key_values
                last = out.logits[0, -1].float()
        diffs.append(abs(lp_sum - r.logprob))
    return max_err, diffs


def _torch_batch_check(ad, p_ids, conts) -> float:
    """5. right-padded batched forward vs per-candidate forward (memo bypassed)."""
    c_list = [ad._cont_ids(c) for c in conts]
    # equal-length candidates never pad, so the masked path would go untested: lengthen the last one
    c_list[-1] = c_list[-1][:-1] + ad._cont_ids(" trailing text that forces right padding of the other rows")
    single = [sum(ad._token_logprobs(p_ids, c)) for c in c_list]
    batched = [sum(tl) for tl in ad._token_logprobs_batch(p_ids, c_list)]
    return max(abs(a - b) for a, b in zip(single, batched))


# ---------------------------------------------------------------------------

def main(spec: str) -> int:
    ad = load_adapter(spec)
    backend = ad.describe()["backend"]
    case = load_case("S01")
    msgs = build_action_prompt(project(case, "attack"))
    conts = [serialize_candidate(case, c, {"memo": "x"}) for c in case.candidates]
    rep = {"model": ad.describe(), "checks": {}}

    p_ids = ad._prompt_ids(msgs)
    res = ad.score(msgs, conts)
    if backend == "mlx":
        max_err, diffs = _mlx_checks(ad, p_ids, res, conts)
    elif backend == "torch":
        max_err, diffs = _torch_checks(ad, p_ids, res, conts)
    else:
        raise SystemExit(f"verify_adapter: unsupported backend {backend!r}")
    rep["checks"]["numpy_recompute_max_abs_err"] = max_err
    rep["checks"]["incremental_vs_uncached_max_abs_diff_nats"] = max(diffs)
    rep["checks"]["scores_uncached"] = [r.logprob for r in res]

    # 3. EOS inclusion
    c_ids = ad._cont_ids(conts[0])
    rep["checks"]["eos_included"] = (c_ids[-1] == ad.eos_id) and (res[0].n_tokens == len(ad.tokenizer.encode(conts[0], add_special_tokens=False)) + 1)

    # 4. greedy determinism
    g1 = ad.generate(msgs, seed=0, temperature=0.0, max_tokens=120)
    if backend == "torch":
        ad._memo.clear()   # torch: make the second greedy run a real recompute, not a memo hit
    g2 = ad.generate(msgs, seed=0, temperature=0.0, max_tokens=120)
    rep["checks"]["greedy_deterministic"] = g1.text == g2.text
    rep["checks"]["sampled_differs_across_seeds"] = ad.generate(msgs, seed=11, temperature=0.7, max_tokens=120).text != ad.generate(msgs, seed=23, temperature=0.7, max_tokens=120).text
    ok = max_err < 1e-4 and max(diffs) < 0.5 and rep["checks"]["eos_included"] and rep["checks"]["greedy_deterministic"]

    if backend == "torch":
        bdiff = _torch_batch_check(ad, p_ids, conts)
        rep["checks"]["batched_vs_single_max_abs_diff_nats"] = bdiff
        ok = ok and bdiff < 1e-3
        # throughput on the actual device: s per score pass, normalised to 1k tokens; s per 90-token generation
        n_tok = [len(p_ids) + r.n_tokens for r in res]
        ad._memo.clear()
        t0 = time.perf_counter()
        g90 = ad.generate(msgs, seed=0, temperature=0.0, max_tokens=90)
        rep["throughput"] = {
            "score_pass_tokens": n_tok,
            "s_per_1k_token_score_pass": float(np.mean([r.cost.wall_seconds / n * 1000 for r, n in zip(res, n_tok)])),
            "gen90_seconds": time.perf_counter() - t0,
            "gen90_tokens": g90.cost.generated_tokens,
        }
    rep["peak_memory_gb"] = ad.peak_memory_gb()
    rep["timing"] = {"score_pass_seconds": [r.cost.wall_seconds for r in res], "gen_seconds": g1.cost.wall_seconds, "prompt_tokens": len(p_ids)}
    rep["pass"] = bool(ok)
    out = resolve_out(f"{OUT_DIR}/verify-{_safe(spec)}.json", mkdir=True)
    out.write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep["checks"], indent=1), "\nPASS" if ok else "\nFAIL", out)
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# cross-adapter comparison
# ---------------------------------------------------------------------------

def _ranks(x: list[float]) -> list[float]:
    """Average ranks (1-based), ties share the mean rank."""
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return float("nan") if va == 0 or vb == 0 else cov / math.sqrt(va * vb)


def spearman(a: list[float], b: list[float]) -> float:
    return _pearson(_ranks(a), _ranks(b))


def _rel(lps: list[float]) -> list[float]:
    m = max(lps)
    lse = m + math.log(sum(math.exp(x - m) for x in lps))
    return [x - lse for x in lps]


def score_contexts(ad, case_ids: list[str]) -> dict:
    out = {"model": ad.describe(), "contexts": {}}
    for cid in case_ids:
        case = load_case(cid)
        conts = [serialize_candidate(case, c, {"memo": "x"}) for c in case.candidates]
        for cond in ("clean", "attack"):
            msgs = build_action_prompt(project(case, cond))
            res = ad.score(msgs, conts, label=f"compare/{cid}/{cond}")
            out["contexts"][f"{cid}/{cond}"] = {
                "prompt_tokens": len(ad._prompt_ids(msgs)),
                "n_tokens": [r.n_tokens for r in res],
                "logprob": [r.logprob for r in res],
            }
    return out


def compare(spec: str, other: str, case_ids: list[str], dump: bool) -> int:
    ad = load_adapter(spec)
    A = score_contexts(ad, case_ids)
    if dump:
        p = resolve_out(f"{OUT_DIR}/scores-{_safe(spec)}.json", mkdir=True)
        p.write_text(json.dumps(A, indent=2))
        print("dumped", p)
    if other.endswith(".json"):
        B = json.loads(resolve_out(other).read_text())
        b_name = other
    else:
        del ad   # free memory before the second model
        B = score_contexts(load_adapter(other), case_ids)
        b_name = other
    rows, agree, ra, rb, tok_mismatch = [], 0, [], [], []
    for key, a in A["contexts"].items():
        b = B["contexts"].get(key)
        if b is None:
            raise SystemExit(f"context {key} missing from {b_name}")
        if a["n_tokens"] != b["n_tokens"] or a["prompt_tokens"] != b["prompt_tokens"]:
            tok_mismatch.append(key)
        am, bm = int(np.argmax(a["logprob"])), int(np.argmax(b["logprob"]))
        agree += am == bm
        rel_a, rel_b = _rel(a["logprob"]), _rel(b["logprob"])
        ra += rel_a
        rb += rel_b
        rows.append({"context": key, "argmax_a": am, "argmax_b": bm,
                     "rel_logodds_a": rel_a, "rel_logodds_b": rel_b,
                     "max_abs_logprob_diff": max(abs(x - y) for x, y in zip(a["logprob"], b["logprob"]))})
    eos_a, eos_b = A["model"].get("eos_id"), B["model"].get("eos_id")
    rep = {
        "a": spec, "b": b_name, "cases": case_ids,
        "model_a": A["model"], "model_b": B["model"],
        "argmax_agreement": agree / len(rows),
        "spearman_rel_logodds": spearman(ra, rb),
        "pearson_rel_logodds": _pearson(ra, rb),
        "max_abs_logprob_diff": max(r["max_abs_logprob_diff"] for r in rows),
        "tokenization_mismatch_contexts": tok_mismatch,
        "eos_id_match": eos_a == eos_b,
        "rows": rows,
    }
    out = resolve_out(f"{OUT_DIR}/compare-{_safe(spec)}--{_safe(Path(b_name).stem if b_name.endswith('.json') else b_name)}.json", mkdir=True)
    out.write_text(json.dumps(rep, indent=2))
    print(json.dumps({k: rep[k] for k in ("a", "b", "argmax_agreement", "spearman_rel_logodds", "pearson_rel_logodds",
                                         "max_abs_logprob_diff", "tokenization_mismatch_contexts", "eos_id_match")}, indent=1), out)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--compare-with", default=None, help="other adapter spec, or a scores-*.json from --dump-scores")
    ap.add_argument("--cases", default="S01", help="comma-separated case ids for --compare-with / --dump-scores")
    ap.add_argument("--dump-scores", action="store_true")
    ap.add_argument("--out-dir", default=OUT_DIR, help="report directory under the project (default reports/model-readiness)")
    a = ap.parse_args()
    OUT_DIR = a.out_dir
    cases = [c for c in a.cases.split(",") if c]
    if a.compare_with:
        sys.exit(compare(a.spec, a.compare_with, cases, a.dump_scores))
    if a.dump_scores:
        A = score_contexts(load_adapter(a.spec), cases)
        p = resolve_out(f"{OUT_DIR}/scores-{_safe(a.spec)}.json", mkdir=True)
        p.write_text(json.dumps(A, indent=2))
        print("dumped", p)
        sys.exit(0)
    sys.exit(main(a.spec))
