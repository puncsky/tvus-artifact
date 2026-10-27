#!/bin/sh
# Research .pm/w1/m1 — Qwen2.5-32B replication (protocol: reports/qwen32b-evidence/protocol.md, plan: run-plan.json).
# Isolated from the historical scripts/run_h100.sh: new run ids, no batching suffix, historical thresholds by reference,
# every experiment.py invocation bound to the frozen plan, one model process at a time.
# Usage: scripts/run_qwen32b_evidence.sh readiness      # adapter checks on the frozen checkpoint (no evidence)
#        scripts/run_qwen32b_evidence.sh probe          # 9-execution timing probe + projection (no evidence)
#        scripts/run_qwen32b_evidence.sh run [role ...] # evidence collection in plan order; needs go-no-go.json "go": true
cd "$(dirname "$0")/.." || exit 1
P=${W3_PY:-envs/torch-cuda/bin/python}
export HF_HOME=$PWD/cache/hf TMPDIR=$PWD/tmp CUBLAS_WORKSPACE_CONFIG=:4096:8 HF_HUB_OFFLINE=1
E=reports/qwen32b-evidence PLAN=reports/qwen32b-evidence/run-plan.json LOG=runs/logs/qwen32b-evidence.log
mkdir -p runs/logs
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "$(stamp) $*" | tee -a "$LOG"; }
guard() {   # no other GPU compute process; enough unified memory for 32B bf16 (~66 GB peak) plus headroom
  apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | grep -c .)
  avail=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
  [ "$apps" -eq 0 ] && [ "$avail" -ge 80 ] && return 0
  say "guard: $apps GPU compute process(es), ${avail} GiB available -> not starting"; return 1
}
frozen() { $P -B runner/qwen32b_evidence.py freeze > /dev/null || { say "protocol/plan differ from freeze.json"; exit 1; }; }
run_id() { $P -B runner/qwen32b_evidence.py argv --role "$1" | sed 's/.*--run-id \([^ ]*\).*/\1/'; }   # from the frozen plan
collect() {   # $1 = role; resumable, plan-bound
  ARGS=$($P -B runner/qwen32b_evidence.py argv --role "$1") || exit 1
  RUN=$(run_id "$1")
  guard || exit 1
  say "collect $1 -> runs/$RUN"
  # shellcheck disable=SC2086
  env ${ARGS%% *} $P -B runner/experiment.py ${ARGS#* } --plan "$PLAN" --checkpoint-every 50 \
      --checkpoint-dest evidence/run-checkpoints >> "runs/logs/$RUN.log" 2>&1
  rc=$?; [ $rc -eq 0 ] || { say "collect $1 exited $rc (resume by re-running this command)"; exit 1; }
}
case "$1" in
readiness)
  guard || exit 1
  $P -B models/verify_adapter.py qwen32b-torch --out-dir "$E/readiness" >> runs/logs/qwen32b-readiness.log 2>&1
  say "readiness verify exit $? (expected: every check passes except batched-vs-single; batching stays off)"
  ;;
probe)
  frozen; collect probe
  $P -B runner/qwen32b_evidence.py probe-compare >> "$LOG" 2>&1
  $P -B runner/qwen32b_evidence.py projection | tee -a "$LOG"
  ;;
run)
  shift; frozen
  $P -c "import json,sys;sys.exit(0 if json.load(open('$E/go-no-go.json')).get('go') else 1)" 2>/dev/null || { say "no go decision ($E/go-no-go.json)"; exit 1; }
  ROLES=${*:-"dev conf gen-test h2-dev h2-conf fb-h1"}
  for R in $ROLES; do
    if $P -B runner/qwen32b_evidence.py audit --role "$R" > /dev/null 2>&1; then say "role $R already complete; not reloading the model"
    else
      collect "$R"
      $P -B runner/qwen32b_evidence.py audit --role "$R" > /dev/null || { say "audit $R incomplete"; exit 1; }
    fi
    $P -B runner/qwen32b_evidence.py backup --role "$R" >> "$LOG" 2>&1 || { say "backup $R failed verification"; exit 1; }
    if [ "$R" = dev ] || [ "$R" = h2-dev ]; then   # secondary thresholds: frozen before any other replication role of the harness is analyzed
      RUN=$(run_id "$R")
      [ -f "reports/$RUN-secthr/thresholds.json" ] || $P -B runner/analyze.py --run "$RUN" --calibrate --out "reports/$RUN-secthr" >> "$LOG" 2>&1
      $P -B runner/qwen32b_evidence.py freeze-thresholds --role "$R" >> "$LOG" 2>&1 || exit 1
    fi
    say "role $R complete, audited and backed up"
  done
  say "collection chain done: $ROLES"
  ;;
*) echo "usage: $0 readiness|probe|run [role ...]"; exit 2;;
esac
