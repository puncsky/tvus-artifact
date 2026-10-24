# Results and evidence map

The reported manuscript is `paper/workshop/main.pdf`. This release contains 40 authored templates (24 development, 8 confirmation, 8 failure-boundary) and 300 generated tasks, with a fixed held-out split. Some generated pilot experiments use only the recorded 48-task development slice.

| Paper result | Evidence |
| --- | --- |
| Main safety/utility table | `reports/{dev,conf}-*/summary.json`, `reports/h2-{dev,conf}-*/summary.json`, `reports/h3-{dev,conf}-*/summary.json`, `reports/gen-*/summary.json`; verdicts in corresponding `rows.jsonl` |
| Qwen2.5-32B held-out 52/55 chosen-action misses versus 0/55 regeneration | `reports/gen-test-qwen32b-bf16/{summary.json,rows.jsonl}`, frozen `reports/dev-qwen32b-bf16/thresholds.json`, task IDs in `generated/test-split.txt` |
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
- Original raw logs are shipped where locally available. All main-table runs have derived verdicts and summaries. Qwen2.5-32B raw execution files/manifests were not available for this release; `RELEASE.json` enumerates that coverage. The release supports recounting their published results, but not independently rebuilding their raw signals without a new model run.
- Historical model and provider identifiers, revisions, seeds, costs and protocol freeze status are preserved. The artifact does not redistribute weights or promise continued hosted-model availability.
- Original run manifests bind the collection-time source hashes. The public export has a separate checksum manifest and does not reconstruct every historical source revision. Metadata path redactions are listed in `RELEASE.json`; fixtures, evaluator data and query texts are copied unchanged.
