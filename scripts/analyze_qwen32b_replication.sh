#!/bin/sh
# Research .pm/w1/m1/t007 — analyze the rep20261025 Qwen2.5-32B replication (no model calls).
# Primary: historical frozen thresholds (hash-checked against run-plan.json). Secondary: the replication-dev
# thresholds frozen in threshold-freeze.jsonl (hash-checked). Then the original-vs-replication comparison.
# Usage: scripts/analyze_qwen32b_replication.sh [python]
cd "$(dirname "$0")/.." || exit 1
P=${1:-${W3_PY:-envs/torch-cuda/bin/python}}
E=reports/qwen32b-evidence
mkdir -p tmp
"$P" -B - "$E" <<'EOF' > tmp/qwen32b-analysis-plan.txt || exit 1
import hashlib, json, sys
from pathlib import Path
E = Path(sys.argv[1])
plan = json.loads((E / "run-plan.json").read_text())
frozen = {r["file"]: r["sha256"] for r in map(json.loads, filter(str.strip, (E / "threshold-freeze.jsonl").read_text().splitlines()))}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
for r in plan["runs"]:
    if not r["evidence"]:
        continue
    prim, sec = r["primary_thresholds"], r["secondary_thresholds"]
    assert sha(prim["file"]) == prim["sha256"], f"primary thresholds changed: {prim['file']}"
    assert sec in frozen and sha(sec) == frozen[sec], f"secondary thresholds not frozen or changed: {sec}"
    print(r["run_id"], r["cases_dir"], prim["file"], sec)
EOF
while read -r RUN CASES PRIM SEC; do
  W3_CASES_DIR=$PWD/$CASES "$P" -B runner/analyze.py --run "$RUN" --thresholds "$PRIM" --out "reports/$RUN" > /dev/null || exit 1
  case "$RUN" in   # dev roles' secondary report was written by their calibration; analyze every other role with it
    *-dev-qwen32b-bf16) ;;
    *) W3_CASES_DIR=$PWD/$CASES "$P" -B runner/analyze.py --run "$RUN" --thresholds "$SEC" --out "reports/$RUN-secthr" > /dev/null || exit 1 ;;
  esac
  echo "analyzed $RUN"
done < tmp/qwen32b-analysis-plan.txt
"$P" -B runner/qwen32b_compare.py
