# Source and artifact audit

Rebuilt 2026-10-02. The original audit (2026-09-26, `evidence/artifact-audit/`) was lost along with its 17 checksummed source records and its `verify.py`. This file re-verifies every reference from scratch and carries forward the earlier findings, labelled as such.

Evidence from this session is in `evidence/artifact-audit-2026-10-02/`:
- `arxiv-verification.json` has the per-id HTTP status, fetched title, first author, citation date and a SHA-256 of each fetched page.
- `raw/` holds the fetched abstract pages, four arXiv HTML full texts, and the GitHub API response for the pinned unofficial commit.
- `anon-*-files.json` holds root file listings of two anonymized artifacts.

Method: `curl -sS -m 15 https://arxiv.org/abs/<id>`, with the title taken from `<meta name="citation_title">`. For PACT, CXI, CausalArmor and Influence Is Not Authority, `https://arxiv.org/html/<id>` was also fetched and searched for artifact links. Nothing was installed or executed. No paid API was called.

## 1. arXiv identity checks

All 12 arXiv references resolved with HTTP 200, and the fetched titles match the proposal. No id failed to verify.

| Ref | Short name | arXiv id | HTTP | Fetched title | First author / date (arXiv meta) |
|---|---|---|---|---|---|
| [1] | PACT | 2605.11039v1 | 200 | The Granularity Mismatch in Agent Security: Argument-Level Provenance Solves Enforcement and Isolates the LLM Reasoning Bottleneck | Fan, Linfeng / 2026-05-11 |
| [2] | CaMeL | 2503.18813v1 | 200 | Defeating Prompt Injections by Design | Debenedetti, Edoardo / 2025-03-24 |
| [3] | FIDES | 2505.23643 | 200 | Securing AI Agents with Information-Flow Control | Costa, Manuel / 2025-05-29 |
| [4] | CXI | 2607.06000v1 | 200 | Context-to-Execution Integrity for LLM Agents | Santos-Grueiro, Igor / 2026-07-07 |
| [5] | ContextCite | 2409.00729v1 | 200 | ContextCite: Attributing Model Generation to Context | Cohen-Wang, Benjamin / 2024-09-01 |
| [6] | AttriBoT | 2411.15102v3 | 200 | AttriBoT: A Bag of Tricks for Efficiently Approximating Leave-One-Out Context Attribution | Liu, Fengyuan / 2024-11-22 |
| [7] | CausalArmor | 2602.07918v1 | 200 | CausalArmor: Efficient Indirect Prompt Injection Guardrails via Causal Attribution | Kim, Minbeom / 2026-02-08 |
| [8] | ProvenanceGuard (misalignment) | 2607.01236v1 | 200 | Safeguarding LLM Agents from Misalignment through Provenance Analysis | She, Yining / 2026-05-01 (as reported by arXiv meta) |
| [9] | Agent-Sentry | 2603.22868 | 200 | Agent-Sentry: Bounding LLM Agents via Execution Provenance | Sequeira, Rohan / 2026-03-24 |
| [10] | AgentDojo | 2406.13352 | 200 | AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents | Debenedetti, Edoardo / 2024-06-19 |
| [11] | DoomArena | 2504.14064 | 200 | DoomArena: A framework for Testing AI Agents Against Evolving Security Threats | Boisvert, Leo / 2025-04-18 |
| [12] | vLLM Automatic Prefix Caching (docs, not arXiv) | – | 200 | `https://docs.vllm.ai/en/stable/design/prefix_caching/` | – |
| [13] | Influence Is Not Authority | 2608.29942v1 | 200 | Influence Is Not Authority: When Causal Guardrail Signals Make Legitimate Tool Use Look Like an Attack in Tool-Using LLM Agents | Ahad, Tanzim / 2026-08-30 |
| (disambiguation) | ProvenanceGuard (factuality), **not** ref [8] | 2606.18037 | 200 | ProvenanceGuard: Source-Aware Factuality Verification for MCP-Based LLM Agents | Alvarez, Ander / 2026-06-16 |

## 2. Code artifacts

"Located" means a link was found on the arXiv abstract page or, where marked, in the HTML full text. Located does not mean inspected, pinned or run. Nothing listed here has been run.

| Ref | Official artifact located? | Evidence / status |
|---|---|---|
| [1] PACT | **No** | The HTML full text (v1) describes an "anonymized supplementary artifact" containing the PACT runtime monitor, contract examples, provenance-inference scripts and evaluation scripts (paper Table 15), but gives no URL. The abstract page has no code link. Matches the 2026-09-26 audit. Official commit, licence and entrypoint are **UNKNOWN**. |
| [2] CaMeL | Not established this session | No code link on the abstract page. Not searched further this session. |
| [3] FIDES | Link on abstract page | `https://github.com/microsoft/fides`. Not inspected, pinned or run. |
| [4] CXI | **Conflicting evidence, see §3** | The 2026-09-26 audit did not locate an official artifact. This session, the HTML full text (v1, "Open Science") states: "An anonymous review artifact is available at https://anonymous.4open.science/r/cxi. The primary entry point is submission_artifact/." The anonymizer API returns HTTP 200 with a root listing (`ARTIFACT.md`, `LICENSE` (Apache-2.0 header), `REPRODUCING.md`, `RESULTS.md`, `submission_artifact/`, …). `ARTIFACT.md` lists `make smoke` / `make comparative-evaluation` checks and an H100 host for open-weight collection. Not downloaded beyond the listing and `ARTIFACT.md`, not pinned (anonymized mirrors expose no stable commit id), not run. |
| [5] ContextCite | Link on abstract page | `https://github.com/MadryLab/context-cite`. Not inspected or run. |
| [6] AttriBoT | Not established this session | No code link on the abstract page. |
| [7] CausalArmor | **No official artifact** | No own-code link on the abstract page or in the HTML full text (v1). The HTML links only to other works (DRIFT, MELON, AgentDojo, vLLM). Matches the 2026-09-26 audit. The paper's sanitizer prompt is in Appendix D.1 (earlier audit). |
| [7] CausalArmor, unofficial | Third-party, **unofficial** | `prashantkul/causal-armor` pinned at commit `97442c6ee7dec1b803828c81ec4c497b0d91f5cc` (MIT), carried over from the 2026-09-26 audit. Re-checked via the GitHub API this session: HTTP 200, the commit exists (committer date 2026-02-23T22:39:52Z, "Add glass-box demo with --live vLLM mode and HTML exports"), repo licence MIT, not a fork. It is not authored by the paper's authors as far as is known, is not fully audited, and is not run. It is **not used** by the B5 port. |
| [8] ProvenanceGuard | Not established this session | No code link on the abstract page. Optional comparison only. |
| [9] Agent-Sentry | Not established this session | No code link on the abstract page. Optional comparison only. |
| [10] AgentDojo | Link on abstract page | `https://github.com/ethz-spylab/agentdojo`. Benchmark, for later task porting (out of first-round scope). |
| [11] DoomArena | Link on abstract page | `https://github.com/ServiceNow/DoomArena`. Benchmark, for later use (out of scope). |
| [12] vLLM docs | n/a | Documentation only. No vLLM is used; this study uses no prefix caching. |
| [13] Influence Is Not Authority | Anonymous artifact located | The HTML full text links `https://anonymous.4open.science/r/influence-is-not-authority-artifact-A674/README.md`. The API returns 200 with a root listing (`README.md`, `CLAIM_TO_ARTIFACT.md`, `RUN_END_TO_END.sh`, `SHA256SUMS.txt`, `studies/`, `third_party/`, …). No root `LICENSE` file is listed. Not downloaded or run, so its results are **not** independently reproduced here. |

## 3. Discrepancy: CXI artifact

The earlier audit said that no official CXI artifact was located "in inspected sources/searches" and called this bounded availability evidence. Today the paper's own HTML names an anonymous review artifact that resolves. The earlier evidence is gone, so the reason for the difference cannot be checked: the artifact might have been missed, or it might not have been reachable then.

Consequences:

- The B2 baseline in this study is still a **paper-derived, CXI-style** reconstruction (`runner/experiment.py::_reconstruct`), not the CXI artifact. Nothing in this round can be called a CXI reproduction.
- Porting or running the CXI artifact is a separate, decomposed follow-up. It needs a mirrored snapshot with a recorded hash, licence review, an isolated environment, and an adapter to this study's fixtures and sink. Until that work is done, "CXI field isolation solves case X" can only be claimed for the port.

## 4. Implications for the baselines

| Baseline | What this study runs | Label |
|---|---|---|
| B1 (PACT) | Value-provenance check plus conservative reference labels, written against the paper description | **Paper-derived port.** Not the official PACT resolver. No statement about PACT's actual resolver, inference accuracy or fail-closed path can come from it. First-round.md requires the real pinned resolver for PACT claims, so any PACT-specific conclusion stays **inconclusive** until the supplement is obtained. |
| B2 (CXI) | Trusted reconstruction with field isolation and typed scoped releases | **Paper-derived, CXI-style.** An artifact exists (see §3) but is not used. |
| B3 (CaMeL STRICT / FIDES) | Nothing | **Not covered.** This is a coverage gap. |
| B4 (ContextCite / AttriBoT / LOO / joint deletion) | Single-source LOO, joint deletion and all-external deletion using the same adapter | **Conceptual controls.** Neither the ContextCite nor the AttriBoT artifact is run. |
| B5 (CausalArmor) | Per-token LOO attribution of each external span compared with the user request's (τ = 0 as ported, plus a calibrated-margin variant), and a contract-conditioned enhanced variant. No sanitize/mask remedy. | **Paper-derived port.** No official artifact exists. The unofficial repo is recorded but not used. |
| B6 | This study's joint-intervention reference | Study reference, not a baseline. |
| ProvenanceGuard, Agent-Sentry | Nothing | Optional. Not covered this round. |

Every comparison in this round is a **shared-shell** comparison (same agent, prompt and sink). None is a native-system comparison.

## 5. Influence Is Not Authority (arXiv:2608.29942v1): novelty check

Assessed from the abstract only; the artifact has not been run. The paper audits 96 conditions derived from 24 base cases. In matched comparisons, moving a required value from the user to a legitimate tool result, with the action unchanged, shifts a causal-guardrail signal toward the attack region in all 24 cases under Llama and Gemma scorers. That benign shift is larger on average than the shift caused by an actual change in authorization. The paper then shows how the mismatch propagates through guardrail architectures (semantic monitor, shadow-based guardrail).

Overlap with this study:

- The authority-versus-influence distinction is already established there and cannot be claimed here. Our L01–L04 controls test the same failure class (legitimate dependence falsely flagged) for B5 and B6.
- Its fixed-intervention, bounded constructed-case design resembles ours, so it is a direct precedent for the method.

What this study could add, and must demonstrate rather than assert:

- **Trusted-valued selection.** Every attack target here is a frozen candidate built from trusted snapshot values, so a value-provenance check is expected to pass it by construction.
- **Contract-conditioned joint and h0-closure interventions** compared against single-source LOO and in-place deletion.
- **Full-candidate relative scores** compared against scoring only the chosen action.
- **A direct comparison with trusted reconstruction (B2)** at matched utility and cost.

If those comparisons show nothing beyond its authority distinction and benign utility cost, the novelty rationale fails.

## 6. Open dependencies

- PACT supplement or resolver configuration, needed for any empirical PACT claim.
- A pinned and reviewed snapshot of the CXI anonymous artifact, needed if B2 is to be upgraded from port to native.
- A faithful-port note for B5: normalization, dominance rule, sanitize/mask path.
- An isolated, reviewed environment before any third-party code is run.
- Independent human review of the port notes. None is available; status is pending.
