# Results and evidence map

The reported manuscript is `paper/workshop/main.pdf`. This release contains 40 authored templates (24 development, 8 confirmation, 8 failure-boundary) and 300 generated tasks, with a fixed held-out split. Some generated pilot experiments use only the recorded 48-task development slice.

| Paper result | Evidence |
| --- | --- |
| Main safety/utility table | `reports/{dev,conf}-*/summary.json`, `reports/h2-{dev,conf}-*/summary.json`, `reports/h3-{dev,conf}-*/summary.json`, `reports/gen-*/summary.json`; verdicts in corresponding `rows.jsonl` |
| Qwen2.5-32B held-out 52/55 chosen-action misses versus 0/55 regeneration (22/375 all scheduled) | Replication raw records `runs/rep20261025-gen-test-qwen32b-bf16/`, verdicts `reports/rep20261025-gen-test-qwen32b-bf16/{summary.json,rows.jsonl}` (historical frozen `reports/dev-qwen32b-bf16/thresholds.json`), task IDs in `generated/test-split.txt` |
| All Qwen2.5-32B rows and text numbers | Replication: `runs/rep20261025-<role>-qwen32b-bf16/` + `reports/rep20261025-<role>-qwen32b-bf16/`; secondary thresholds in `reports/*-secthr/`; index `reports/qwen32b-evidence/role-index.json` |
| Original-versus-replication comparison | `reports/qwen32b-evidence/comparison.{md,json}` (side-by-side metrics, per-execution agreement, raw-to-verdict recount); original-derived October reports `reports/<role>-qwen32b-bf16/` unchanged |
| Candidate-relative versus chosen-action attribution | `reports/separability/`, `reports/main/auroc.csv`, per-execution `stats` in `reports/*/rows.jsonl` |
| Cost comparison | `reports/main/cost*.csv`, per-run `summary.json` and per-execution `cost` entries |
| Failure-boundary cases, including the post-note F04 checkpoint | `failure-boundary/`, `reports/fb-h*-qwen14b/`, `reports/fb2-h*-qwen14b/`, corresponding raw `runs/` |
| Adaptive search | `runs/bypass-*/`, `runs/adaptive-pilot-qwen14b/`, `reports/adaptive-pilot-qwen14b/`, `bypass/attacker-prompt-independent.md` |
| Designation-preserving release-search counts | `review/release-search-validity.json`, `reports/bypass-extractor-audit.json`, three `runs/bypass-extractor-*/queries.jsonl` logs |
| Author validation | `review/spot-check*result.md`, signed answer files and the rendered packets |
| AgentDojo transfer | `external/agentdojo/`, `runs/adojo-h2-qwen14b/`; use the external sink's verdicts |

`python -B scripts/verify_paper_tables.py` checks all 18 main-table rows and their 220 reported fractions against the saved summaries, then independently recounts the corresponding per-execution verdicts.

## Scope and limitations

- B1, B2 and B5 are paper-derived ports within a shared harness. This release does not contain or run the official PACT, CXI or CausalArmor systems. `artifacts.md` records the historical source audit.
- Influence, attack-attributable violation and conditional misses have different denominators. A steered execution requires a same-seed correct clean B0 execution and an unauthorized attack B0 execution. Legitimate tasks are excluded from threat-attack denominators.
- The held-out 32B result is a benchmark observation. Zero observed misses is not a universal guarantee; the failure-boundary suite demonstrates broken assumptions.
- The release-search audit is a post-hoc agent review of historical queries. Retained B2 wrong effects are L02 **1/11**, K08 **3/11**, F07 **0/1**. Excluded queries still consumed the original budgets and affected feedback. Original raw summaries are preserved and should not replace the corrected audited counts.
- Original raw logs are shipped where locally available. All main-table runs have derived verdicts and summaries. The October 2026 Qwen2.5-32B raw execution files/manifests remain missing (`RELEASE.json` lists them); their published rows can be recounted but not rebuilt. The paper's 32B numbers instead come from the `rep20261025` replication, whose raw records, manifests, traces and checksums are shipped and can be re-analyzed with `runner/analyze.py` (REPRODUCING.md §3). Replication records are new executions with new timestamps, not recovered October records.
- The replication's primary analysis uses the historical frozen thresholds; a fresh calibration on the replication's own development runs is reported only as a secondary analysis (`reports/*-secthr/`). Agreement with the October counts was not an acceptance condition; `comparison.md` reports every difference. None was found: all 1,731 executions received the same verdict from every defense. Because the replication ran the same seeded decoding on the same pinned software stack and GPU type, this is a reproducibility and provenance check, not an independent sample.
- Historical model and provider identifiers, revisions, seeds, costs and protocol freeze status are preserved. The artifact does not redistribute weights or promise continued hosted-model availability.
- Original run manifests bind the collection-time source hashes. The public export has a separate checksum manifest and does not reconstruct every historical source revision. Metadata path redactions are listed in `RELEASE.json`; fixtures, evaluator data and query texts are copied unchanged.
