# Release verification

The v1.1.0 artifact replaces the Qwen2.5-32B evidence with an auditable replication (`rep20261025`): the six October 2026 32B matrices could not be recovered (`reports/qwen32b-evidence/recovery.md`), so the frozen schedule was collected again on the same checkpoint revision, bf16 and unbatched scoring under a protocol and run plan frozen before collection (`reports/qwen32b-evidence/protocol.md`, `freeze.json`). Every 32B number in the paper and `RESULTS.md` is now computed from the shipped replication raw records. The original October summaries remain in the artifact, labeled as originals, for comparison only. All other fixtures, runs and results are unchanged from v1.0.1. The checks below were run by `scripts/verify_qwen32b_release.py` on a fresh extraction of the release ZIP unless noted otherwise.

| Check | Result |
| --- | --- |
| File checksums | Every exported file matches `MANIFEST.sha256`; each replication run's `SHA256SUMS` verifies before any output is generated |
| Replication schedule | All six runs: 1,731/1,731 scheduled keys present exactly once (development 216, confirmation 72, held-out test 1,323, H2 development 72, H2 confirmation 24, failure-boundary 24); every started attempt committed; no resumes; no B0/B2 parse failures |
| Replication bindings | Each run manifest names revision `5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd`, bf16, unbatched scoring, the frozen run-plan hash, and fixture and collection-code file hashes equal to the shipped files |
| Replication reanalysis from raw | All six reports regenerated from raw executions with their declared thresholds equal the shipped summaries and verdict rows (wall-clock fields excluded) |
| Raw verdict recount (B0/B2) | 0 mismatches in 3,462 B0/B2 sink outcomes re-derived from raw records with the fixture evaluators |
| Main paper table versus replication summaries | All 18 rows and 220 fractions match; 1,620 summary metrics independently recounted (`--qwen32b replication`, the default; the original-derived mode also passes) |
| Original versus replication comparison | `reports/qwen32b-evidence/comparison.md` (every metric identical; 1,731/1,731 executions receive the same verdict from all 15 defenses; the replication-development thresholds are byte-identical to the historical files) |
| Interruption / resume / refusal | `scripts/check_resume_mock.sh`: two hard kills and a torn record resume to the uninterrupted result; an incompatible configuration is refused |
| H1 and H2 mock collection and analysis | Pass, 9 scheduled executions per mock run |
| Standard-library-only environment | Quick-start checks, fixture validation, generated self-check, mock collection and analysis, and the Qwen-14B reanalysis pass in a fresh venv without installed packages |
| Authored development / confirmation / failure-boundary fixtures | 24 / 8 / 8 valid |
| AgentDojo port fixtures | 17 valid |
| Generated benchmark independent self-check | 300/300 evaluator agreement; no leak-check failures; split checks pass |
| Hash-bound release-search audit | L02 1/11, K08 3/11, F07 0/1 B2 wrong effects |
| Qwen-14B development and confirmation raw-log reanalysis | Both regenerated summaries equal the saved summaries (wall-clock fields excluded) |
| Publication scan | No credential-like strings detected; private directories, local environments, model weights and monorepo history excluded. Replication raw records are shipped byte-identical (bound by `SHA256SUMS`) and may contain host paths of the collection machine |
| Paper layout | 8 total pages; non-reference content ends on page 7 and references start on page 8; all fonts embedded; no overfull boxes or undefined references |

Replication raw records were collected on the author's DGX Spark (`reports/qwen32b-evidence/runbook.md`); collection checks are agent-run reproducibility checks, not independent human validation.
