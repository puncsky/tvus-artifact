# Qwen2.5-32B replication — machine runbook (spark-71a4)

Operator notes for collecting the frozen schedule (`protocol.md`, `run-plan.json`) on the author-supplied DGX Spark.
Paths are relative to `projects/tvus-research/`. Never print or commit credentials; none are needed (public checkpoint).

## Host and environment

| | |
|---|---|
| Host | `spark-71a4`, NVIDIA GB10 (sm_12.1), 121 GiB unified memory, aarch64, Ubuntu 24.04, driver 580.178.04 / CUDA 13.0 |
| Ownership / cost | author's own machine (approved in chat 2026-10-25); no rental, GPU spend $0 |
| Python env | `envs/torch-cuda` (uv-managed CPython 3.12.15, torch 2.14.1+cu130, transformers 5.18.0); rebuilt by `tmp/build_torch_env.sh` from `configs/env-cuda.json` |
| Checkpoint | `cache/hf/hub/models--Qwen--Qwen2.5-32B-Instruct/snapshots/5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd` (bf16, ~65.5 GB) |
| Shared machine | other projects (`../spark`) may use the GPU; the wrapper refuses to start while another GPU compute process runs or < 80 GiB is available |

## Commands

```bash
scripts/run_qwen32b_evidence.sh readiness   # verify_adapter on the frozen checkpoint -> reports/qwen32b-evidence/readiness/
scripts/run_qwen32b_evidence.sh probe       # 9 non-evidence executions + probe-compare.json + projection.json
# go/no-go recorded in reports/qwen32b-evidence/go-no-go.json ("go": true) before:
tmux new-session -d -s tvus-collect 'scripts/run_qwen32b_evidence.sh run'   # dev conf gen-test h2-dev h2-conf fb-h1
```

* **Progress:** `runs/logs/qwen32b-evidence.log` (chain), `runs/logs/<run-id>.log` (one line per execution).
  The B0 status/candidate printed per line is for monitoring only (protocol §4.3).
* **Resume after any interruption** (crash, reboot, guard refusal): re-run the same `run` command; finished roles
  are skipped by their audit and executed keys by the recorder. An incompatible configuration is refused (exit 3).
* **Single role:** `scripts/run_qwen32b_evidence.sh run gen-test`.
* **Stop:** `tmux kill-session -t tvus-collect` (an interrupted attempt stays recorded and is redone on resume).
* **Audit / backup by hand:** `envs/torch-cuda/bin/python -B runner/qwen32b_evidence.py audit --role <role>`;
  `... backup --role <role>` (finished runs only).

## Storage and backups

* Primary records: `runs/rep20261025-<role>-qwen32b-bf16/` (manifest read-only; JSONL sidecars append-only).
* Rolling checkpoint every 50 executions: `evidence/run-checkpoints/<run-id>/` with `SHA256SUMS` verified at the copy
  (`evidence/run-checkpoints/checkpoints.jsonl`).
* Per finished role: verified backup `evidence/qwen32b-backup/<run-id>/` (`reports/qwen32b-evidence/backups.jsonl`).
* All three copies are on this host's NVMe; an off-host copy is a separate author decision (none is made here).

## Expected duration and size (probe 2026-10-25, `projection.json`)

| Role | Executions | Projected hours |
|---|---:|---:|
| dev | 216 | 11.2 |
| conf | 72 | 3.5 |
| gen-test | 1,323 | 52.0 |
| h2-dev | 72 | 4.8 |
| h2-conf | 24 | 1.6 |
| fb-h1 | 24 | 1.1 |
| **total** | **1,731** | **≈74 h** (+ ~5–8 min model load per role) |

Probe: 172.7 s/execution (October: 170.7 s); history-track cases take ~5–6 min, direct cases ~1–1.5 min.
Raw records ≈125 KB/execution → ≈0.22 GB in total, ≈0.65 GB with the rolling checkpoint and the backup copy.
Peak unified memory ≈66 GB plus the OS: avoid starting other large GPU jobs on this host while collection runs
(the guard only checks at the start of each role; running out of unified memory can take the machine down).
