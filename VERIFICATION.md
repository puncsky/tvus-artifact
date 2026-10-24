# Release verification

The v1.0.0 artifact was exported and tested from a fresh ZIP extraction before publication. No model experiments or hosted API calls were performed during this verification.

| Check | Result |
| --- | --- |
| File checksums | Every exported file matches `MANIFEST.sha256` |
| Authored development / confirmation / failure-boundary fixtures | 24 / 8 / 8 valid |
| AgentDojo port fixtures | 17 valid |
| Generated benchmark independent self-check | 300/300 evaluator agreement; no leak-check failures; split checks pass |
| Main paper table versus summaries | All 18 rows and 220 fractions match |
| Independent verdict recount | 1,620 summary metrics match |
| Hash-bound release-search audit | L02 1/11, K08 3/11, F07 0/1 B2 wrong effects |
| H1 and H2 mock collection and analysis | Pass, 9 scheduled executions per mock run |
| Qwen-14B development and confirmation raw-log reanalysis | Both regenerated summaries exactly equal the saved summaries |
| Adaptive pilot curve reanalysis | Pass |
| Standard-library-only environment | Quick-start checks, generated self-check and mock collection pass in a fresh venv without installed packages |
| Scientific fixture export | Runtime/evaluator JSON files copied byte-identically |
| Publication scan | No credential-like strings detected; private directories, local environments and monorepo history excluded |
| Paper layout | 8 total pages, references start on page 7; no overfull boxes or undefined citations |

The Qwen2.5-32B raw-log limitation is recorded in `RESULTS.md` and `RELEASE.json`; its derived verdicts and summaries were included in the independent recount.
