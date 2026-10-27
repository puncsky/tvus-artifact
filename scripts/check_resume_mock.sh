#!/bin/sh
# Mock-pipeline check of the durable recorder (research .pm/w1/m1/t002, re-run by t010 from the export):
# hard kill mid-execution -> torn trailing record -> resume -> second hard kill -> resume to completion, then
# mismatch refusal. Asserts: manifest bytes never change, earlier ledger/trace/attempt records survive, no duplicate
# execution keys, interrupted attempts are recorded, the torn bytes are kept, and the result equals an
# uninterrupted run. Mock outputs are pipeline transport only, never evidence.
# Usage: scripts/check_resume_mock.sh [python]
cd "$(dirname "$0")/.." || exit 1
P=${1:-${W3_PY:-envs/torch-cuda/bin/python}}
RUN=w1-mock-resume-check REF=w1-mock-resume-ref
ARGS="--model mock --cases S01 P01 H02 L01 --seeds 0 11"
rm -rf "runs/$RUN" "runs/$REF"
mkdir -p tmp
fail() { echo "FAIL: $*"; exit 1; }
"$P" -B runner/experiment.py $ARGS --run-id "$REF" > /dev/null || fail "reference run"

"$P" -B runner/experiment.py $ARGS --run-id "$RUN" --abort-after-calls 50 > /dev/null; [ $? -eq 137 ] || fail "first kill did not happen"
M0=$(sha256sum "runs/$RUN/manifest.json" | cut -d' ' -f1)
L0=$(wc -l < "runs/$RUN/ledger.jsonl"); T0=$(wc -l < "runs/$RUN/trace.jsonl"); E0=$(wc -l < "runs/$RUN/executions.jsonl")
head -c 4000 "runs/$RUN/ledger.jsonl" > "tmp/$RUN.ledger-head"
printf '{"case": "S01", "condition": "att' >> "runs/$RUN/executions.jsonl"      # torn write of a record
"$P" -B runner/experiment.py $ARGS --run-id "$RUN" --abort-after-calls 60 > /dev/null; [ $? -eq 137 ] || fail "second kill did not happen"
"$P" -B runner/experiment.py $ARGS --run-id "$RUN" > /dev/null || fail "final resume"

M1=$(sha256sum "runs/$RUN/manifest.json" | cut -d' ' -f1)
[ "$M0" = "$M1" ] || fail "manifest changed on resume"
[ "$(wc -l < "runs/$RUN/ledger.jsonl")" -gt "$L0" ] && [ "$(wc -l < "runs/$RUN/trace.jsonl")" -gt "$T0" ] || fail "sidecars did not grow"
head -c 4000 "runs/$RUN/ledger.jsonl" | cmp -s - "tmp/$RUN.ledger-head" || fail "earlier ledger records altered"
ls "runs/$RUN"/executions.torn-s1.jsonl.txt > /dev/null 2>&1 || fail "torn bytes not preserved"

"$P" -B - "$RUN" "$REF" "$E0" <<'EOF' || fail "consistency checks"
import json, sys
from pathlib import Path
run, ref, e0 = Path("runs") / sys.argv[1], Path("runs") / sys.argv[2], int(sys.argv[3])
rd = lambda p: [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
ex, ex_ref = rd(run / "executions.jsonl"), rd(ref / "executions.jsonl")
keys = [(r["case"], r["condition"], r["seed"]) for r in ex]
assert len(keys) == len(set(keys)) == 24, ("duplicates or missing", len(keys), len(set(keys)))
att = rd(run / "attempts.jsonl")
starts = {a["attempt"] for a in att if a["event"] == "start"}
commits = {a["attempt"] for a in att if a["event"] == "commit"}
incomplete = starts - commits
assert len(incomplete) == 2, ("expected 2 interrupted attempts", incomplete)
res = rd(run / "resumes.jsonl")
assert [r["session"] for r in res] == [1, 2] and all(r["incomplete_attempts"] for r in res), res
assert res[0]["torn_tails"] and res[0]["torn_tails"][0]["file"] == "executions.jsonl", res[0]["torn_tails"]
assert incomplete <= {t["attempt"] for t in rd(run / "trace.jsonl")}, "interrupted attempts lost their trace"
led = rd(run / "ledger.jsonl")
assert {e["session"] for e in led} == {0, 1, 2}, "ledger lost a session"
assert json.loads((run / "ledger.json").read_text()) == led, "ledger.json is not the cumulative ledger"
strip = lambda r: {k: v for k, v in r.items() if k not in ("attempt", "started", "finished", "wall_seconds")}
a = {(r["case"], r["condition"], r["seed"]): strip(r) for r in ex}
b = {(r["case"], r["condition"], r["seed"]): strip(r) for r in ex_ref}
assert a == b, "resumed run differs from the uninterrupted run"
print(f"ok: 24 unique executions ({e0} before the first kill), 2 interrupted attempts recorded, sessions 0-2 in ledger, torn tail preserved")
EOF

# mismatch refusal: a different schedule (seeds) and a different condition list must be rejected without writing anything
S0=$(cd "runs/$RUN" && ls -la --time-style=full-iso | sha256sum)
"$P" -B runner/experiment.py --model mock --cases S01 P01 H02 L01 --seeds 0 --run-id "$RUN" > "tmp/$RUN.refuse1" 2>&1; R1=$?
"$P" -B runner/experiment.py --model mock --cases S01 P01 H02 L01 --seeds 0 11 --conditions clean attack --run-id "$RUN" > "tmp/$RUN.refuse2" 2>&1; R2=$?
S1=$(cd "runs/$RUN" && ls -la --time-style=full-iso | sha256sum)
[ $R1 -eq 3 ] && [ $R2 -eq 3 ] || fail "mismatched resume not refused ($R1, $R2)"
grep -q "run_specs" "tmp/$RUN.refuse1" && grep -q "conditions" "tmp/$RUN.refuse2" || fail "refusal does not name the mismatch"
[ "$S0" = "$S1" ] || fail "refused resume modified the run dir"
echo "ok: incompatible resumes refused (exit 3) and the run dir is untouched"
rm -rf "runs/$REF" "tmp/$RUN.ledger-head"
echo "PASS check_resume_mock"
