# Qwen2.5-32B evidence recovery — inventory and disposition (w1/m1/t001)

Date: 2026-10-25 UTC. Machine-readable inventory: [`inventory.json`](inventory.json); search log: [`searches.json`](searches.json).
No model calls, rentals or public writes were made by this task.

## Outcome

**No authentic original raw records for any of the six Qwen2.5-32B matrices could be recovered.** All six need a
separately labeled, complete replication (1,731 scheduled executions). The historical derived evidence (per-defense
verdict rows, summaries, frozen thresholds, dossiers) is intact and reconciles exactly with its schedule; it stays
unchanged and remains the "original" evidence tier, with its coverage limit (no proposals, inputs, manifests or ledgers).

| Role | Historical id | Fixtures / harness | Seeds | Scheduled | Derived rows reconcile | Raw records | Disposition |
|---|---|---|---|---:|---|---|---|
| dev | `dev-qwen32b-bf16` | `cases/` (24) / H1 | 0, 11, 23 | 216 | yes (3,240 rows = 216 × 15) | absent | fresh replication |
| conf | `conf-qwen32b-bf16` | `confirmation/cases` (8) / H1 | 0, 11, 23 | 72 | yes | absent | fresh replication |
| gen-test | `gen-test-qwen32b-bf16` | `generated/cases` ∩ `test-split.txt` (147) / H1 | 0, 11, 23 | 1,323 | yes | absent | fresh replication |
| h2-dev | `h2-dev-qwen32b-bf16` | `cases/` (24) / H2 | 0 | 72 | yes | absent | fresh replication |
| h2-conf | `h2-conf-qwen32b-bf16` | `confirmation/cases` (8) / H2 | 0 | 24 | yes | absent | fresh replication |
| fb-h1 | `fb-h1-qwen32b-bf16` | `failure-boundary/cases` (8) / H1 | 0 | 24 | yes | absent | fresh replication |

"Reconcile" means: `summary.n_executions == n_scheduled ==` the role's schedule, zero missing coverage, the set of
`(case, condition, seed)` keys in `rows.jsonl` equals the schedule computed from the current fixtures, 15 defense rows per
execution, and the frozen threshold file equals the thresholds embedded in the summary. Headline counts read back from
the saved summaries match the manuscript's original reference: held-out B0 82/375 (attributable 55/348), B2 25/375,
regeneration-only 22/375, B6 11/375, chosen-action 52/55, 20 steered tasks.

## Where we looked (see `searches.json`)

1. **Original DGX Spark `zgx-aa67`** — reachable only over the tailnet; `tailscale status` reports it offline
   (last seen 13 days ago) and one bounded SSH attempt timed out (2026-10-25T04:17Z). Not retried.
2. **This host `spark-71a4`** (new location) — whole-filesystem search: no 32B runs, no handoff/state archive; the
   neighbouring `../spark` project holds Qwen3.8 checkpoints only.
3. **Public artifact v1.0.1** — the author's local zip matches the published release asset hash; it ships the same
   32B derived files (byte-identical except the redacted `model_path` user) and no 32B run directory;
   `RELEASE.json.missing_raw_runs` lists all six.
4. **Mac checkout + 2026-10-06 handoff bundle** — searched 2026-10-24, not repeated (predates the 32B runs).

## Bindings of the original collection

* **Model:** summaries record `Qwen/Qwen2.5-32B-Instruct` @ `5ede1c97…`, bf16, `batch_candidates=false`, sdpa,
  torch 2.14.1+cu130, transformers 5.18.0, GB10 — identical to the frozen replication pin.
* **Thresholds:** H1 roles (dev/conf/gen-test/fb-h1) use `reports/dev-qwen32b-bf16/thresholds.json`
  (144 calibration executions); H2 roles use `reports/h2-dev-qwen32b-bf16/thresholds.json` (48).
* **Code and fixtures:** original manifests are lost, so the executed code/fixture hashes cannot be authenticated.
  Git shows `runner/`, `models/` and every fixture set unchanged since `9ecac5d73` (2026-10-06), before the runs;
  uncommitted edits on the old host cannot be excluded. Current fixture hashes are recorded per case in `inventory.json`.
* **Collection time:** not recoverable exactly. Window 2026-10-08 → 2026-10-10 on `zgx-aa67`; first commits of the
  derived reports: dev/conf/fb-h1 `4254c6479` (2026-10-08 16:37 −07:00), H2 `aab5e7b08` (2026-10-09 00:51 −07:00),
  gen-test `dbc839719` (2026-10-10 16:21 −07:00).

## Consequences for the rest of m1

* Every matrix takes the replication branch (t004–t006); none can be satisfied by recovery.
* The historical report directories and public tags stay unchanged; the replication uses new run ids
  (`rep20261025-<role>-qwen32b-bf16`) and is never labeled as October original evidence.
* The manuscript must keep disclosing that the original 32B raw records are missing; complete raw evidence will exist
  only for the replication.
