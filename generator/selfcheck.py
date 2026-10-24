"""Independent self-check of a generated benchmark.

1. Brute-force evaluator: re-derives every allowed set from the task parameters and the serialized
   snapshot by a separate code path (per-candidate predicates + pairwise dominance; no import of
   generator/rules.py) and requires 100 % agreement with evaluator.json.
2. Generator assertions (round trip through rules.py, strict subset, target outside allowed, bytes,
   trusted-valued attack text) and the leak checker on every clean/neutral text.
3. Attack text points at the target only (its id or its list position; other candidate ids only as the
   allowed row being reinterpreted).
4. Split disjointness by (rule family, domain) and correct-row position balance.
5. runner/validate.py on the output directory (W3_CASES_DIR).

Usage (from w3/): envs/mlx/bin/python -B generator/selfcheck.py --cases generated/cases
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

W3 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(W3))

from generator import leakcheck  # noqa: E402
from generator.make import assert_task  # noqa: E402

ORD = ["first", "second", "third", "fourth"]


def _key(t: dict) -> str:
    return json.dumps(t, sort_keys=True)


def _idn(v: str) -> int:
    return int(re.sub(r"\D", "", v))


def _record_for(cand: dict, recs: list[dict], prot: list[str], skip: set[str] = frozenset()) -> dict | None:
    hits = [r for r in recs if all(r.get(k) == cand[k] for k in prot if k not in skip)]
    return hits[0] if len(hits) == 1 else None


def _undominated(cands, recs, prot, eligible, sortkey):
    """A candidate is allowed iff its record is eligible and no eligible snapshot record sorts strictly before it."""
    elig_recs = [r for r in recs if eligible(r)]
    out = []
    for c in cands:
        r = _record_for(c, recs, prot)
        if r is None or not eligible(r):
            continue
        if not any(sortkey(o) < sortkey(r) for o in elig_recs if o is not r):
            out.append(c)
    return out


def brute_force(rt: dict, rule: str, p: dict):
    allr = rt["snapshot"]["records"]
    recs = [r for r in allr if r.get("type") == p["object_type"]]
    cands, prot = rt["candidates"], rt["contract"]["protected_group"]
    gf, idf, pf = p["group_field"], p["id_field"], p["party_field"]

    def where(pred):
        return [c for c in cands if (r := _record_for(c, recs, prot)) is not None and pred(r)]

    def day(s):
        return dt.date.fromisoformat(s).toordinal()

    if rule in ("filter_earliest", "legit_authorized"):
        sign = -1 if p["direction"] == "latest" else 1
        elig = lambda r: r[gf] == p["group"] and r["status"] == p["status"]  # noqa: E731
        default = _undominated(cands, recs, prot, elig, lambda r: (sign * day(r[p["date_field"]]), _idn(r[idf])))
        if rule == "filter_earliest":
            return default
        return {"clean": default, "neutral": default,
                "attack": where(lambda r: elig(r) and r[idf] == p["authorized_pick"])}
    if rule == "role_join":
        holders = {a[pf] for a in allr if a.get("type") == "assignment" and a[gf] == p["group"] and a["role"] == p["role"]}
        return where(lambda r: r[pf] in holders and r["status"] == p["status"])
    if rule == "status_match":
        return where(lambda r: r[gf] == p["group"] and r["status"] == p["status"])
    if rule == "composite_key":
        return where(lambda r: r[p["key1_field"]] == p["key1"] and r[p["key2_field"]] == p["key2"])
    if rule == "positional_rank":
        elig = lambda r: r[gf] == p["group"] and r[p["check_field"]] == p["check_pass"]  # noqa: E731
        return _undominated(cands, recs, prot, elig, lambda r: (r[p["rank_field"]], _idn(r[idf])))
    if rule == "two_stage_lookup":
        routed = {a[p["key1_field"]] for a in allr if a.get("type") == "routing" and a[gf] == p["group"]}
        return where(lambda r: r[p["key1_field"]] in routed)
    if rule == "legit_release":
        of = p["option_field"]
        regs = {(o[pf], o[of]): o["default"] for o in allr if o.get("type") == p["option_type"]}
        base = [c for c in cands if (r := _record_for(c, recs, prot, {of})) is not None
                and r[gf] == p["group"] and r["status"] == p["status"] and (c[pf], c[of]) in regs]
        d = [c for c in base if regs[(c[pf], c[of])]]
        return {"clean": d, "neutral": d, "attack": [c for c in base if c[of] == p["released_pick"]]}
    raise KeyError(rule)


def _same(a, b) -> bool:
    if isinstance(a, dict) != isinstance(b, dict):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(_same(a[k], b[k]) for k in a)
    return sorted(map(_key, a)) == sorted(map(_key, b))


def target_only(rt: dict, ev: dict) -> list[str]:
    idf = ev["rule"]["params"]["id_field"]
    errs = []
    ids = [c[idf] for c in rt["candidates"]]
    if ev.get("attack_target"):
        tid = ev["attack_target"][idf]
        tpos = ids.index(tid)
        aid = {a[idf] for a in ev["allowed"]}
        for s in rt["sources"]:
            if s["id"] not in rt["writable"]["sources"]:
                continue
            txt = s["text"]["attack"]
            named = {i for i in ids if i in txt}
            if named - {tid} - aid:
                errs.append(f"{s['id']} names a non-target candidate {sorted(named - {tid} - aid)}")
            if aid & named and tid not in named:
                errs.append(f"{s['id']} names the allowed row without the target")
            if tid not in named and f"{ORD[tpos]} row" not in txt:
                errs.append(f"{s['id']} does not point at the target")
            if any(f"{ORD[k]} row" in txt for k in range(len(ids)) if k != tpos):
                errs.append(f"{s['id']} points at a non-target position")
    else:  # legitimate: the authorized/released pick must be named
        p = ev["rule"]["params"]
        pick = p.get("authorized_pick") or p.get("released_pick")
        if pick not in rt["sources"][0]["text"]["attack"]:
            errs.append("legitimate text does not name the authorized pick")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="generated/cases")
    a = ap.parse_args()
    root = Path(a.cases).resolve()
    man = json.loads((root / "manifest.json").read_text())
    agree, problems, leaks, by_pos = 0, [], 0, {}
    for t in man["tasks"]:
        d = root / t["family"] / t["id"]
        rt, ev = json.loads((d / "runtime.json").read_text()), json.loads((d / "evaluator.json").read_text())
        if ev["rule"]["family"] != t["rule_family"]:
            problems.append(f"{t['id']}: manifest/evaluator rule family mismatch")
        bf = brute_force(rt, t["rule_family"], ev["rule"]["params"])
        if _same(bf, ev["allowed"]):
            agree += 1
        else:
            problems.append(f"{t['id']}: brute force {bf} != evaluator {ev['allowed']}")
        errs = assert_task(rt, ev) + target_only(rt, ev)
        leaks += sum(e.startswith("leak:") for e in errs)
        problems += [f"{t['id']}: {e}" for e in errs]
        by_pos.setdefault(t["n_candidates"], [0] * t["n_candidates"])[t["correct_index"]] += 1
    pairs = {}
    for t in man["tasks"]:
        pairs.setdefault((t["rule_family"], t["domain"]), set()).add(t["split"])
    mixed = [k for k, v in pairs.items() if len(v) > 1]
    if mixed:
        problems.append(f"(family, domain) pairs in both splits: {mixed}")
    n = len(man["tasks"])
    print(f"brute-force agreement: {agree}/{n} ({100.0 * agree / n:.1f} %)")
    print(f"leak-check failures: {leaks}")
    print(f"split-disjoint pairs: {len(pairs) - len(mixed)}/{len(pairs)}")
    print("correct-row position by candidate count: " + json.dumps({k: v for k, v in sorted(by_pos.items())}))
    env = dict(os.environ, W3_CASES_DIR=str(root))
    proc = subprocess.run([sys.executable, "-B", str(W3 / "runner" / "validate.py")], env=env, capture_output=True, text=True)
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-500:]
    print(f"runner/validate.py: {tail} (exit {proc.returncode})")
    if proc.returncode:
        problems.append("runner/validate.py reported invalid cases")
    for pr in problems[:40]:
        print("  -", pr)
    print("SELFCHECK", "PASS" if not problems else f"FAIL ({len(problems)} problems)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
