"""Empirical neutrality check of the neutral control (protocol v2 §1.2).

For each template (case) in a run, compares the ordinary agent's (B0) clean and neutral executions
seed by seed: (1) whether the execution was a correct automatic completion (``executed_allowed``) and
(2) which frozen candidate it chose (index; None = parse failure / not a candidate).  A template is
flagged when neutral disagrees with clean on any seed.  A neutral rewrite that changes behaviour is
not behaviourally neutral for that model, so attack-vs-neutral contrasts on flagged templates need
care; at temperature > 0 some disagreement is sampling noise, which the per-seed table exposes.

B0 outcomes are computed with ``runner/analyze.py::outcome`` (imported, not modified).

Usage (from w3/):
  envs/mlx/bin/python -B runner/neutrality.py --run dev-qwen14b
  envs/mlx/bin/python -B runner/neutrality.py --run conf-qwen14b --cases-dir confirmation/cases
Writes reports/<run>/neutrality.md and reports/<run>/neutrality.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

W3 = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--cases-dir", default=None, help="case directory (default: $W3_CASES_DIR or w3/cases)")
    ap.add_argument("--out", default=None, help="output directory (default: reports/<run>)")
    a = ap.parse_args()
    if a.cases_dir:  # must be set before runner.schema is imported (CASES_DIR is read at import)
        cd = Path(a.cases_dir)
        os.environ["W3_CASES_DIR"] = str(cd if cd.is_absolute() else (W3 / cd).resolve())
    sys.path.insert(0, str(W3))
    from runner.paths import CATEGORY, resolve_out
    from runner.schema import load_case, CASES_DIR
    from runner.analyze import outcome

    run_dir = CATEGORY / "runs" / a.run
    recs = [json.loads(x) for x in (run_dir / "executions.jsonl").read_text().splitlines() if x.strip()]
    out_dir = resolve_out(a.out or f"reports/{a.run}")
    out_dir.mkdir(parents=True, exist_ok=True)

    cases, b0 = {}, {}
    for r in recs:
        if r["condition"] not in ("clean", "neutral"):
            continue
        if r["case"] not in cases:
            cases[r["case"]] = load_case(r["case"])
        case = cases[r["case"]]
        oc = outcome("b0", "PASS" if r["b0"]["status"] == "ok" else "UNKNOWN", r, case)
        idx = case.candidate_index(r["b0"]["args"]) if r["b0"]["status"] == "ok" else None
        b0[(r["case"], r["condition"], r["seed"])] = {"outcome": oc["outcome"], "allowed": oc["outcome"] == "executed_allowed",
                                                      "index": idx}

    templates, flagged, n_pairs, n_dis, n_dis_allowed, n_dis_index, unpaired = [], [], 0, 0, 0, 0, []
    for cid in sorted(cases, key=lambda c: (c[0], c)):
        seeds = sorted({s for (c, cond, s) in b0 if c == cid})
        rows = []
        for s in seeds:
            cl, ne = b0.get((cid, "clean", s)), b0.get((cid, "neutral", s))
            if cl is None or ne is None:
                unpaired.append(f"{cid}/seed {s}")
                continue
            d_allowed = cl["allowed"] != ne["allowed"]
            d_index = cl["index"] != ne["index"]
            rows.append({"seed": s, "clean": cl, "neutral": ne, "disagree_allowed": d_allowed, "disagree_index": d_index,
                         "disagree": d_allowed or d_index})
            n_pairs += 1
            n_dis += d_allowed or d_index
            n_dis_allowed += d_allowed
            n_dis_index += d_index
        t = {"template": cid, "family": cases[cid].family, "legitimate": cases[cid].is_legitimate, "seeds": rows,
             "n_seeds": len(rows), "n_disagree": sum(r["disagree"] for r in rows), "flagged": any(r["disagree"] for r in rows)}
        templates.append(t)
        if t["flagged"]:
            flagged.append(cid)

    manifest = json.loads((run_dir / "manifest.json").read_text())
    summary = {
        "run_id": a.run, "cases_dir": str(CASES_DIR), "model": manifest.get("model", {}).get("family"),
        "run_specs": manifest.get("run_specs"),
        "templates_flagged": {"k": len(flagged), "n": len(templates)},
        "executions_disagreeing": {"k": n_dis, "n": n_pairs,
                                   "allowed_flag_differs": n_dis_allowed, "candidate_index_differs": n_dis_index},
        "clean_allowed": {"k": sum(v["allowed"] for (c, cond, s), v in b0.items() if cond == "clean"),
                          "n": sum(1 for (c, cond, s) in b0 if cond == "clean")},
        "neutral_allowed": {"k": sum(v["allowed"] for (c, cond, s), v in b0.items() if cond == "neutral"),
                            "n": sum(1 for (c, cond, s) in b0 if cond == "neutral")},
        "flagged": flagged, "unpaired": unpaired, "templates": templates,
        "rule": "flag a template if, on any seed, B0 neutral differs from B0 clean in executed_allowed or in chosen candidate index",
    }
    (out_dir / "neutrality.json").write_text(json.dumps(summary, indent=2) + "\n")

    temps = {s: t for s, t in (manifest.get("run_specs") or [])}

    def cell(v):
        return f"{'ok' if v['allowed'] else v['outcome']}@{'–' if v['index'] is None else v['index']}"
    L = [f"# Neutrality check — {a.run}", "",
         f"Model: {summary['model']}. Cases: `{os.path.relpath(CASES_DIR, CATEGORY)}`. Seeds (temperature): "
         + ", ".join(f"{s} ({temps[s]})" for s in sorted(temps)) + ".", "",
         f"Rule: {summary['rule']}.", "",
         f"- Templates flagged: **{len(flagged)}/{len(templates)}**" + (f" ({', '.join(flagged)})" if flagged else ""),
         f"- Executions (clean/neutral seed pairs) disagreeing: **{n_dis}/{n_pairs}** "
         f"(executed_allowed differs {n_dis_allowed}, chosen candidate differs {n_dis_index})",
         f"- B0 correct automatic: clean {summary['clean_allowed']['k']}/{summary['clean_allowed']['n']}, "
         f"neutral {summary['neutral_allowed']['k']}/{summary['neutral_allowed']['n']}",
         f"- Unpaired (missing clean or neutral execution): {', '.join(unpaired) if unpaired else 'none'}", "",
         "Cell = outcome@candidate index (`ok` = executed_allowed; `–` = no frozen candidate / parse failure).", "",
         "| template | family | " + " | ".join(f"seed {s}: clean → neutral" for s in sorted(temps)) + " | disagree | flagged |",
         "|---|---|" + "---|" * len(temps) + "---|---|"]
    for t in templates:
        by = {r["seed"]: r for r in t["seeds"]}
        cells = []
        for s in sorted(temps):
            r = by.get(s)
            cells.append("–" if r is None else f"{cell(r['clean'])} → {cell(r['neutral'])}" + (" **≠**" if r["disagree"] else ""))
        L.append(f"| {t['template']} | {t['family']} | " + " | ".join(cells) + f" | {t['n_disagree']}/{t['n_seeds']} | {'FLAG' if t['flagged'] else ''} |")
    (out_dir / "neutrality.md").write_text("\n".join(L) + "\n")
    print(f"{a.run}: templates flagged {len(flagged)}/{len(templates)}; executions disagreeing {n_dis}/{n_pairs} "
          f"(allowed {n_dis_allowed}, index {n_dis_index}); flagged: {', '.join(flagged) or 'none'}")
    print(f"wrote {out_dir / 'neutrality.md'} and neutrality.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
