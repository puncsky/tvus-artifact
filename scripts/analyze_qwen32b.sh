#!/bin/sh
# Analyze the six Qwen2.5-32B runs of reports/qwen32b-evidence/run-plan.json from their raw records (no model calls).
# Each harness's development run calibrates the thresholds (the file must equal the hash the plan froze before
# collection); every other run of that harness is analyzed with them.
# Usage: scripts/analyze_qwen32b.sh [python]
cd "$(dirname "$0")/.." || exit 1
P=${1:-${W3_PY:-envs/torch-cuda/bin/python}}
mkdir -p tmp
"$P" -B - reports/qwen32b-evidence/run-plan.json <<'PY' > tmp/qwen32b-analysis-plan.txt || exit 1
import json, sys
runs = [r for r in json.load(open(sys.argv[1]))["runs"] if r["evidence"]]
calib = {r["harness"]: r for r in runs if r["role"].endswith("dev")}
for r in sorted(runs, key=lambda r: r is not calib[r["harness"]]):   # calibration runs first
    print(r["run_id"], r["cases_dir"], calib[r["harness"]]["run_id"], r["primary_thresholds"]["sha256"])
PY
while read -r RUN CASES CAL SHA; do
  if [ "$RUN" = "$CAL" ]; then
    W3_CASES_DIR=$PWD/$CASES "$P" -B runner/analyze.py --run "$RUN" --calibrate --out "reports/$RUN" > /dev/null || exit 1
    GOT=$(sha256sum "reports/$RUN/thresholds.json" | cut -d' ' -f1)
    [ "$GOT" = "$SHA" ] || { echo "reports/$RUN/thresholds.json differs from the plan's frozen hash" >&2; exit 1; }
  else
    W3_CASES_DIR=$PWD/$CASES "$P" -B runner/analyze.py --run "$RUN" --thresholds "reports/$CAL/thresholds.json" --out "reports/$RUN" > /dev/null || exit 1
  fi
  echo "analyzed $RUN"
done < tmp/qwen32b-analysis-plan.txt
