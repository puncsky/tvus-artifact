# Release verification

The checks below were run by `scripts/verify_qwen32b_release.py` on a fresh extraction of the release ZIP unless noted otherwise. They make no model or hosted API calls.

| Check | Result |
| --- | --- |
| File checksums | Every exported file matches `MANIFEST.sha256`; each Qwen2.5-32B run's `SHA256SUMS` verifies before any output is generated |
| Qwen2.5-32B schedule | All six runs: 1,731/1,731 scheduled keys of `reports/qwen32b-evidence/run-plan.json` present exactly once (development 216, confirmation 72, held-out test 1,323, H2 development 72, H2 confirmation 24, failure-boundary 24) |
| Qwen2.5-32B bindings | Each run manifest names revision `5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd`, bf16, unbatched scoring, the run-plan hash, and fixture and collection-code file hashes equal to the shipped files |
| Qwen2.5-32B reanalysis from raw | All six reports regenerated from raw executions equal the shipped summaries and verdict rows (wall-clock fields excluded); the H1 and H2 development runs recalibrate thresholds byte-identical to the shipped files, whose hashes the run plan records |
| Raw verdict recount (B0/B2) | 0 mismatches in 3,462 B0/B2 sink outcomes re-derived from raw records with the fixture evaluators |
| Main paper table versus summaries | All 18 rows and 220 fractions match; 1,620 summary metrics independently recounted |
| Interruption / resume / refusal | `scripts/check_resume_mock.sh`: two hard kills and a torn record resume to the uninterrupted result; an incompatible configuration is refused |
| H1 and H2 mock collection and analysis | Pass, 9 scheduled executions per mock run |
| Standard-library-only environment | Quick-start checks, fixture validation, generated self-check, paper tables, mock collection and analysis, and the Qwen-14B reanalysis pass in a fresh venv without installed packages |
| Authored development / confirmation / failure-boundary fixtures | 24 / 8 / 8 valid |
| AgentDojo port fixtures | 17 valid |
| Generated benchmark independent self-check | 300/300 evaluator agreement; no leak-check failures; split checks pass |
| Hash-bound release-search audit | L02 1/11, K08 3/11, F07 0/1 B2 wrong effects |
| Qwen-14B development and confirmation raw-log reanalysis | Both regenerated summaries equal the saved summaries (wall-clock fields excluded) |
| Publication scan | No credential-like strings detected; private directories, local environments, model weights and monorepo history excluded. Checksum-bound Qwen2.5-32B run files are shipped byte-identical, so their manifests keep the collection host's model-cache path |
| Paper layout | 8 total pages; non-reference content ends and references start on page 7; all fonts embedded; no overfull boxes or undefined references (checked on the build, not by the script) |

The Qwen2.5-32B runs were collected on the author's DGX Spark. These are agent-run reproducibility checks, not independent human validation.
