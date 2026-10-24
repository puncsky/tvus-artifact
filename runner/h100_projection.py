"""Project the H100 chain cost from the probe runs (m10/t004) and write reports/h100-projection.{md,json}.

Scheduled executions per family (protocol v2 / t004): dev 24 templates × 3 conditions × 3 seeds = 216; confirmation 8 × 3 × 3 = 72;
F-suite 8 × 3 × 1 = 24; H2 dev 72 + H2 conf 24 (greedy only); generated test split (147 tasks) × 3 conditions × 3 seeds = 1323.
Per-execution seconds are taken from the probe (3 templates, 3 conditions, seed 0 = 9 executions, H1) with a 1.6× factor for H2
executions (more agent turns) and a 0.8× factor for generated tasks (shorter snapshots). `approved` is set only when the
projection is under the cap; the operator may edit the JSON to approve a reduced plan (fewer seeds / families).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.paths import CATEGORY  # noqa: E402

PLAN = [("dev", 216, 1.0), ("conf", 72, 1.0), ("fb-h1", 24, 1.0), ("h2-dev", 72, 1.6), ("h2-conf", 24, 1.6), ("gen-test", 1323, 0.8)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, required=True, help="USD per GPU hour")
    ap.add_argument("--cap", type=float, required=True)
    ap.add_argument("--families", nargs="+", required=True)
    ap.add_argument("--setup-hours", type=float, default=1.5, help="download + env + probe overhead")
    a = ap.parse_args()
    rows, total_h = [], a.setup_hours
    for fam in a.families:
        p = CATEGORY / "runs" / f"probe-{fam}" / "executions.jsonl"
        if not p.exists():
            rows.append((fam, None, None, None)); continue
        ex = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        secs = sum(e.get("wall_seconds", 0) for e in ex) / max(1, len(ex))
        hours = sum(n * f * secs for _, n, f in PLAN) / 3600
        rows.append((fam, len(ex), secs, hours)); total_h += hours
    usd = total_h * a.rate
    out = {"rate_usd_per_hour": a.rate, "cap_usd": a.cap, "setup_hours": a.setup_hours,
           "families": {f: {"probe_executions": n, "sec_per_execution": s, "projected_hours": h} for f, n, s, h in rows},
           "projected_hours": total_h, "projected_usd": usd, "approved": bool(usd <= a.cap and all(r[3] is not None for r in rows))}
    (CATEGORY / "reports" / "h100-projection.json").write_text(json.dumps(out, indent=2))
    md = ["# H100 cost projection", "", f"rate ${a.rate}/h · cap ${a.cap} · setup {a.setup_hours} h", "",
          "| family | probe executions | s/execution | projected hours |", "|---|---|---|---|"]
    md += [f"| {f} | {n if n is not None else 'no probe'} | {f'{s:.0f}' if s else '–'} | {f'{h:.1f}' if h else '–'} |" for f, n, s, h in rows]
    md += ["", f"**Total: {total_h:.1f} h ≈ ${usd:.0f}** → {'APPROVED (under cap)' if out['approved'] else 'NOT approved: reduce seeds/families and re-run, or edit reports/h100-projection.json'}", ""]
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
