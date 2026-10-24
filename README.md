# TVUS: Trusted Values, Untrusted Choices

Research artifact for **Trusted Values, Untrusted Choices: A Measurement Study of Selection Provenance in Tool-Using Agents**, by Tian Pan.

An agent can choose an unauthorized action even when every argument value comes from a trusted record. This study measures that failure and examines two diagnostic traps: free-text dependence can obscure attribution of the protected choice, and deleting a source late can leave its influence in stored history.

[Paper](paper/workshop/main.pdf) · [Reproduction instructions](REPRODUCING.md) · [Results and evidence map](RESULTS.md) · [Fixed release](https://github.com/puncsky/tvus-artifact/releases/tag/v1.0.0)

On the Qwen2.5-32B held-out generated test split, the chosen-action score gate missed **52/55** steered executions; clean-checkpoint regeneration missed **0/55**. These are benchmark measurements, not a general security guarantee. B1, B2 and B5 are paper-derived ports; official defense artifacts were not run.

## Quick start

Python 3.12 or later. The following checks use only the standard library and make no model or API calls:

```bash
python -B scripts/verify_artifact.py
python -B runner/validate.py
python -B scripts/verify_paper_tables.py
python -B runner/release_search_audit.py --check
```

For the mock pipeline, re-analysis and plots, see [REPRODUCING.md](REPRODUCING.md).

## Contents

| Path | Contents |
| --- | --- |
| `cases/`, `confirmation/cases/`, `failure-boundary/cases/` | 24 development, 8 confirmation and 8 failure-boundary templates |
| `generated/`, `generator/` | 300 generated tasks, split lists, deterministic generator and independent self-check |
| `runner/`, `models/`, `configs/` | Harnesses, interventions, defense ports, analysis, model revisions and recorded environments |
| `reports/` | Per-execution verdicts, frozen thresholds, summaries, score statistics and dossiers |
| `runs/` | Available original model outputs, query logs, run manifests and cost ledgers |
| `review/` | Author validation packets and signed answers; hash-bound agent annotations for the release-search audit |
| `external/agentdojo/` | 17 task ports, checker integration and upstream MIT notice |
| `paper/workshop/` | Paper PDF, LaTeX source and vector figure |
| `protocol*.md`, `preregistration*.json` | Historical protocol and changes; preserve their recorded freeze status |
| `MANIFEST.sha256`, `RELEASE.json` | Checksums, publication metadata and per-run evidence coverage |

**Evidence coverage:** all paper main-result runs have per-execution verdicts and summaries. The Qwen2.5-32B runs have derived verdicts, signals and costs, but their complete raw `executions.jsonl` and original run manifests are absent from this release. Available raw logs for the other runs are included. [RESULTS.md](RESULTS.md) distinguishes re-analysis from rerunning models.

The fixtures are synthetic. Original code and fixtures are MIT-licensed; the paper is CC BY 4.0. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md). Model weights and third-party packages are obtained separately under their respective licenses.
