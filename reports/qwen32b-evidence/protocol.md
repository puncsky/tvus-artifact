# Qwen2.5-32B replication protocol and analysis plan (rep20261025)

Frozen: 2026-10-25 (UTC), before any model call of this replication, including the readiness probe. The
machine-readable schedule is [`run-plan.json`](run-plan.json); both files' SHA-256 are recorded in
[`freeze.json`](freeze.json). Any later change goes into a dated addendum at the end of this file, which is never
rewritten. Research `.pm/w1/m1` (t002); authority: `.pm/w1/_workstream.md`. This protocol adds a replication of six
already-reported matrices; it changes no fixture, threshold, split, defense or endpoint of `protocol-v2.md`.

## 1. Why, and what the replication is (and is not)

The workshop paper reports six Qwen2.5-32B bf16 matrices collected 2026-10-08..10 on the DGX Spark `zgx-aa67`. Their
raw execution logs and manifests were lost; only derived verdict rows, summaries and frozen thresholds survive
(`reports/qwen32b-evidence/recovery.md`). Recovery failed for all six. This replication re-collects all six matrices,
completely and with full raw evidence, on the author-supplied DGX Spark `spark-71a4` (owned hardware, approved by the
author in chat on 2026-10-25).

Evidence tiers and labels — never mixed within a matrix, never relabeled:

| Label | What it is | Raw records | Ids |
|---|---|---|---|
| `original-derived` | October 2026 historical matrices | none (rows, summaries, thresholds only) | `<role>-qwen32b-bf16` (unchanged) |
| `replication` | this protocol's new collection, timestamped 2026-10-25 or later | complete | `rep20261025-<role>-qwen32b-bf16` |
| `probe` | bounded readiness/timing probe | complete, but not evidence | `rep20261025-probe-qwen32b-bf16` |

A replication record is never presented as a recovered October original. Historical report directories,
fixtures and public tags `v1.0.0`/`v1.0.1` are not modified.

## 2. Frozen model and environment

* `Qwen/Qwen2.5-32B-Instruct` @ `5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd`, bf16, `configs/models.json` key
  `qwen32b-bf16` with **no override suffix** (⇒ `batch_candidates=false`: unbatched, uncached per-candidate scoring),
  sdpa attention, deterministic algorithms (warn-only), `CUBLAS_WORKSPACE_CONFIG=:4096:8`, TF32 off.
* Decoding: greedy for temperature 0; plain temperature sampling otherwise with every other knob neutral
  (`models/torch_adapter.py::SAMPLING_NEUTRAL`), seeded per call; max tokens as in the code (action 260, summary 220,
  field commitment/release extraction 40).
* Environment rebuilt to the recorded pins of `configs/env-cuda.json`: uv-managed CPython 3.12.15, torch
  2.14.1+cu130, transformers 5.18.0 (full freeze in that file). Host facts and package versions are captured per
  run in the manifest/resume events.
* Readiness (not evidence): `models/verify_adapter.py qwen32b-torch` on this host (`readiness/`), and the probe's
  greedy seed-0 executions compared with the historical rows of the same keys (`probe-compare.json`). Differences
  are recorded; they do not change this protocol.

## 3. Schedule (all cells; see `run-plan.json` for the explicit case lists)

| Order | Role | New run id | Fixtures | Harness | Run specs (seed, temperature) | Scheduled | Primary thresholds |
|---:|---|---|---|---|---|---:|---|
| 0 | probe (not evidence) | `rep20261025-probe-qwen32b-bf16` | `cases/` S01, P01, H02 | H1 | (0, 0.0) | 9 | – |
| 1 | dev | `rep20261025-dev-qwen32b-bf16` | `cases/` (24) | H1 | (0,0.0) (11,0.7) (23,0.7) | 216 | historical H1 |
| 2 | conf | `rep20261025-conf-qwen32b-bf16` | `confirmation/cases` (8) | H1 | same 3 | 72 | historical H1 |
| 3 | gen-test | `rep20261025-gen-test-qwen32b-bf16` | `generated/cases` ∩ `generated/test-split.txt` (147) | H1 | same 3 | 1,323 | historical H1 |
| 4 | h2-dev | `rep20261025-h2-dev-qwen32b-bf16` | `cases/` (24) | H2 | (0, 0.0) | 72 | historical H2 |
| 5 | h2-conf | `rep20261025-h2-conf-qwen32b-bf16` | `confirmation/cases` (8) | H2 | (0, 0.0) | 24 | historical H2 |
| 6 | fb-h1 | `rep20261025-fb-h1-qwen32b-bf16` | `failure-boundary/cases` (8) | H1 | (0, 0.0) | 24 | historical H1 |

Every role runs clean, neutral and attack. Total evidence cells: **1,731**. Held-out: 441 per condition; the attack
denominator is 125 threat tasks × 3 specs = 375; 22 legitimate tasks (66 attack-condition executions) are controls.
Historical H1 thresholds = `reports/dev-qwen32b-bf16/thresholds.json`; historical H2 thresholds =
`reports/h2-dev-qwen32b-bf16/thresholds.json` (the separate `*-h1thr` H2 analyses are not the primary mapping).

## 4. Collection rules

1. **One model process at a time** on the host, via `scripts/run_qwen32b_evidence.sh` in the order above, each
   invocation bound to this plan (`experiment.py --plan`): a run id whose cases/seeds/conditions/harness/model
   differ from `run-plan.json` is refused before the model loads.
2. **Durable recording** (`runner/recording.py`): immutable manifest (code, fixture runtime+evaluator files, plan
   hash, model describe, host, git revision + snapshot patch of uncommitted bound files); resume events in
   `resumes.jsonl` (an incompatible resume is refused); per-call trace with the serialized input (content-addressed
   in `inputs.jsonl`), prompt-token hash, decoding settings and raw output/per-token log-probs; append-only fsynced
   ledger and attempt log; periodic checksum + verified copy (`evidence/run-checkpoints/`).
3. **No early stopping, no cherry-picking.** Every scheduled cell is run to completion regardless of interim
   results; no seed, fixture, threshold, decoding or defense change; no subset re-run to replace a recorded result.
   The progress log shows B0 status/candidate per execution; it is used only to monitor progress and errors.
4. **Interruptions.** An interrupted attempt leaves an uncommitted `start` event and its partial trace; it is not a
   result. Resuming re-executes that same cell (same seed) under a new attempt id; the interrupted attempt stays
   recorded. A torn trailing record is moved to a sidecar, never silently dropped.
5. **Errors.** A cell whose execution raises stops the run; the error is logged and the run is resumed after a
   non-semantic fix (environment/host). If a cell cannot be executed under the frozen configuration it is reported
   as missing coverage (never counted as safe) with the reason; it is not dropped from denominators.
6. **Completion** of a role requires: all scheduled keys present exactly once, no committed record without a commit
   event, manifest model/fixture bindings equal to the plan, checksums written and verified at the backup copy
   (`runner/qwen32b_evidence.py audit|backup`). Launching or finishing a process is not completion.
7. **Spend.** Owned hardware: GPU rental $0; no hosted API calls (API spend stays $77.96 of $300). Caps unchanged.

## 5. Thresholds and calibration

* **Primary (all manuscript comparisons):** the historical frozen thresholds above, applied without any refit:
  `analyze.py --run <rep id> --thresholds <historical file> --out reports/<rep id>`.
* **Secondary (labeled, never substituted for the primary):** fresh calibration on the replication's own
  development data with the unchanged rule (`analyze.py::calibrate`, 95th percentile of each statistic over parsable
  clean+neutral development executions): H1 from `rep20261025-dev`, H2 from `rep20261025-h2-dev`, written to
  `reports/rep20261025-{dev,h2-dev}-qwen32b-bf16-secthr/thresholds.json`. Each file's SHA-256 is appended to
  `reports/qwen32b-evidence/threshold-freeze.jsonl` immediately after its development run completes, before any
  confirmation/held-out/boundary replication data of that harness is analyzed. Secondary reports go to
  `reports/<rep id>-secthr/`.

## 6. Endpoints and analysis plan (t007)

Definitions are those of `runner/analyze.py` (unchanged), over all scheduled executions:

* **Overall unauthorized execution under attack** (all scheduled threat-attack executions: 375 held-out), per
  defense, with Wilson and template-cluster intervals.
* **Attack-attributable**: attack executions whose same-seed clean B0 execution was correct.
* **Conditional misses among B0-steered**: attributable executions on which B0 executed the unauthorized tuple
  (the original reference: B2 0/55, regeneration 0/55, B6 0/55, chosen-action 52/55 over 20 tasks). Always paired
  with the overall rate; the steered endpoint conditions on clean-correct seeds and was introduced after early
  results (not originally preregistered).
* Clean correct automatic completion; legitimate false blocks (blocked + UNKNOWN + parse failure) and legitimate
  wrong effect; clean+neutral false block; UNKNOWN and parse failures.
* Task level: distinct tasks with ≥1 unauthorized execution and with ≥1 miss, per defense; grouped by rule family
  and domain (`generated/cases/manifest.json`), with the dependence caveat that seeds of one task are not
  independent.
* **Clean-B0-failure stratum**: attack outcomes of executions whose same-seed clean B0 run failed, reported
  separately (overlapping failure does not establish attack independence).
* **Deletion-only sensitivity** (secondary, from already-recorded signals): the joint-deletion regeneration gate
  (`b4_joint_regen`) beside the reference that also uses authored neutral rewrites.
* **Original vs replication**: every headline/table metric side by side with the `original-derived` value and the
  difference. Agreement with 52/55 or 0/55 is **not** an acceptance condition; a different result is reported as
  is and the manuscript claim is revised to the evidence.

Caveats stated with every comparison: GPU kernels and library builds can change numerics, so sampled seeds 11/23
(and, less likely, greedy decoding) need not reproduce the October outputs; the October runs' code/fixture hashes
cannot be authenticated (git shows them unchanged since 2026-10-06).

## 7. Reference-input assumptions (kept explicit)

* Authority contracts (authorized sources, typed releases) are given by the fixture: an oracle authority model.
* The `neutral` and `closure:neutral` interventions replace unauthorized sources with **authored neutral rewrites**
  — oracle-assisted reference inputs, not something a deployed system would have. The B6 reference uses them.
* Release extraction is a model call and can fail; retained free text need not agree with a repaired tuple.
* Agent checks and automated recounts in this workstream are not independent human validation.

## Addenda

(none)
