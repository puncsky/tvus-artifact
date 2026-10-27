# Reproducing the artifact

Run commands from the repository root. Use a fresh output name when rerunning experiments. No command in the first three sections downloads weights, uses an API or spends money.

## 1. Verify the release and benchmark

Python 3.12+ is sufficient for these checks:

```bash
python -B scripts/verify_artifact.py
python -B runner/validate.py
W3_CASES_DIR="$PWD/confirmation/cases" python -B runner/validate.py
W3_CASES_DIR="$PWD/failure-boundary/cases" python -B runner/validate.py
W3_CASES_DIR="$PWD/external/agentdojo/cases" python -B runner/validate.py
python -B generator/selfcheck.py --cases generated/cases
python -B scripts/verify_paper_tables.py
python -B runner/release_search_audit.py --check
```

Expected fixture counts: 24, 8, 8 and 17; the generator self-check independently verifies all 300 tasks. The paper check matches the main results table to saved summaries and independently recounts the underlying verdicts. The release-search check verifies all 36 historical query annotations against their text hashes and reproduces the corrected counts.

`MANIFEST.sha256` covers the files as published. Check it before generating outputs. Historical run manifests retain the hashes recorded at collection time; those are not claims that current source files are byte-identical to every historical runner revision. Local machine paths in metadata were scrubbed; scientific fixture and query contents were preserved.

## 2. Set up analysis and run the mock pipeline

```bash
python3.12 -m venv envs/repro
envs/repro/bin/pip install -r requirements.txt
envs/repro/bin/python -B runner/experiment.py \
  --model mock --run-id artifact-mock-h1 --cases S01 H02 L02 --seeds 0
envs/repro/bin/python -B runner/analyze.py --run artifact-mock-h1 --calibrate
envs/repro/bin/python -B runner/experiment.py \
  --model mock --harness h2 --run-id artifact-mock-h2 --cases S01 H02 L02 --seeds 0
envs/repro/bin/python -B runner/analyze.py --run artifact-mock-h2 --calibrate
```

Each mock run schedules 9 executions: 3 templates × 3 conditions × 1 seed. The mock checks pipeline transport and produces synthetic outputs; it is not evidence for model performance. Results appear under `runs/artifact-mock-*` and `reports/artifact-mock-*`.

## 3. Re-analyze saved model executions

Use the original frozen thresholds, without recalibrating on confirmation or test data. These examples write into fresh report directories:

```bash
envs/repro/bin/python -B runner/analyze.py --run dev-qwen14b \
  --thresholds reports/dev-qwen14b/thresholds.json --out reports/reanalysis-dev-qwen14b
W3_CASES_DIR="$PWD/confirmation/cases" envs/repro/bin/python -B runner/analyze.py \
  --run conf-qwen14b --thresholds reports/dev-qwen14b/thresholds.json \
  --out reports/reanalysis-conf-qwen14b
envs/repro/bin/python -B runner/adaptive_curves.py \
  --runs adaptive-pilot-qwen14b --out reports/reanalysis-adaptive
```

Qwen2.5-32B: the paper's numbers come from the `rep20261025` replication, whose raw records are shipped. Rebuild any of its six reports from raw signals with the historical frozen thresholds (H1 roles use the dev file, H2 roles the H2 dev file; `reports/qwen32b-evidence/run-plan.json` lists the mapping), then compare with the shipped report:

```bash
W3_CASES_DIR="$PWD/generated/cases" envs/repro/bin/python -B runner/analyze.py \
  --run rep20261025-gen-test-qwen32b-bf16 --thresholds reports/dev-qwen32b-bf16/thresholds.json \
  --out reports/reanalysis-rep-gen-test
python -B scripts/verify_paper_tables.py --qwen32b replication
envs/repro/bin/python -B runner/qwen32b_compare.py      # side-by-side comparison, per-execution agreement, raw recount
```

Each replication run directory has a read-only `manifest.json` (code, fixture, plan and model bindings, host and source revision), `executions.jsonl`, per-call `trace.jsonl` with content-addressed model inputs in `inputs.jsonl`, an append-only `ledger.jsonl`, `attempts.jsonl` and `SHA256SUMS` (`cd runs/<id> && sha256sum -c SHA256SUMS`). The October original-derived reports (`reports/<role>-qwen32b-bf16/`) can still be recounted from their verdict rows (`scripts/verify_paper_tables.py --qwen32b original --tex <v1.0.1 main.tex>`), but their raw signals were lost and cannot be rebuilt.

The durable recorder's interruption/resume and mismatch-refusal behaviour can be exercised on the mock pipeline (no model): `scripts/check_resume_mock.sh envs/repro/bin/python`.

End-to-end check of a release ZIP (no model; extracts into a fresh directory next to the ZIP and runs every check listed in `VERIFICATION.md`): `envs/repro/bin/python -B scripts/verify_qwen32b_release.py tvus-artifact-v1.1.0.zip [--pdf main.pdf]`. All six Qwen2.5-32B replication reports can be rebuilt at once with `scripts/analyze_qwen32b_replication.sh envs/repro/bin/python`.

Some older report tables and protocol notes describe intermediate stages. The included workshop paper, `RESULTS.md`, final per-run summaries and designation-preservation audit identify the reported version. Spot-check answers are author review, not an independent blind annotation study.

## 4. Optional: rerun real models

Real-model collection requires hardware, separately downloaded checkpoints and additional dependencies. Hosted collection requires your own provider credentials and incurs charges. The default checks above never invoke it.

The original Apple Silicon experiments used `mlx-lm==0.32.0`; the CUDA environment is recorded in `configs/env-cuda.json` (PyTorch `2.14.1+cu130`, transformers `5.18.0`). Model repos and revisions are pinned in `configs/models.json`. Install the appropriate backend in a separate environment. See `models/README-torch.md` for adapter semantics and historical verification notes.

Download a pinned checkpoint before collection. The runner puts caches under `cache/` and sets offline mode. Example for the bf16 model, using a separate CUDA environment:

```bash
HF_HOME="$PWD/cache/hf" envs/torch-cuda/bin/python -c \
  "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-32B-Instruct', revision='5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd')"
envs/torch-cuda/bin/python -B models/verify_adapter.py qwen32b-torch --out-dir reports/reproduction-readiness
envs/torch-cuda/bin/python -B runner/experiment.py \
  --model qwen32b-bf16 --run-id reproduction-qwen32b-dev
envs/torch-cuda/bin/python -B runner/analyze.py --run reproduction-qwen32b-dev \
  --thresholds reports/dev-qwen32b-bf16/thresholds.json --out reports/reproduction-qwen32b-dev
```

`scripts/run_qwen32b_evidence.sh` is the plan-bound wrapper used for the replication (it refuses invocations that differ from `reports/qwen32b-evidence/run-plan.json`; use your own run ids and plan for a new collection).

The checkpoint needs roughly 64 GB for bf16 weights plus runtime overhead. Collection was on a DGX Spark with 121 GiB system memory. Keep candidate batching off in bf16; padding introduced measurable scoring drift. Run model processes sequentially. Seeds and conditions are in the recorded manifests/protocol; hosted API outputs and floating-point results may change across environments.

## 5. Build the paper

The compiled PDF is included. To rebuild, download the unmodified [AAAI-27 Author Kit](https://aaai.org/authorkit27/), place `aaai2027.sty` and `aaai2027.bst` in `paper/workshop/aaai/`, install the TeX packages used by `main.tex`, and run:

```bash
make -C paper/workshop
```

The style files are not redistributed in this artifact. Use pdfLaTeX and BibTeX.
