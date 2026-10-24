"""Validate all case fixtures (schema, truth isolation, budgets)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.schema import load_all, validate_case, project, CONDITIONS, canonical_json

def main(ids: list[str]) -> int:
    cases = load_all(ids or None)
    bad = 0
    for c in cases:
        errs = validate_case(c)
        # projection invariants: snapshot/candidates/task identical across conditions, no truth
        projs = {cond: project(c, cond) for cond in CONDITIONS}
        base = projs["clean"]
        for cond, pj in projs.items():
            for k in ("task", "snapshot", "candidates", "contract", "tool"):
                if canonical_json(pj[k]) != canonical_json(base[k]):
                    errs.append(f"projection {cond}: {k} differs from clean")
            if "attack_target" in canonical_json(pj) or "allowed" in canonical_json(pj):
                errs.append(f"projection {cond} leaks truth keys")
        status = "ok" if not errs else "FAIL"
        bad += bool(errs)
        print(f"{c.id:4} {c.family:12} {c.track:8} cands={len(c.candidates)} srcs={len(c.sources())} unauth={len(c.unauthorized_sources())} {status}")
        for e in errs:
            print("     -", e)
    print(f"{len(cases)} cases, {bad} invalid")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
