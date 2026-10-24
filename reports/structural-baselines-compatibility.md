# Structural baselines: CaMeL, FIDES and CXI vs. selection influence

Scope: m3/t005 compatibility note for baseline group B2/B3 (proposal §8.2; first-round
"Four required comparison groups"). Sources read: CaMeL arXiv:2503.18813 (v1 and v2 HTML, full
text incl. §4.4, §6, Appendix D), FIDES arXiv:2505.23643 (HTML full text, §4–6, Appendix),
CXI arXiv:2607.06000v1 (HTML full text, §2.3, §3.4, §3.7, Tables 3/7). Fetched copies are in
`evidence/structural-baselines/` (all HTTP 200). No framework was installed or executed in this
study; everything below is a reading of the papers against our 24 templates. The first draft of
this note was begun by a subagent that was interrupted before writing; the text here was written
from its fetched evidence.

## 1. What each framework does about *selection* influence

**CaMeL** (capability-tagged dual-LLM planner). The privileged P-LLM writes Python from the user
query alone; a quarantined Q-LLM may only parse untrusted data into typed values. Every value
carries provenance tags (User / CaMeL / tool, plus inner source) and the interpreter tracks a data-
and control-flow graph (§4.3–4.4). A policy on a side-effecting tool, e.g. the banking suite's
`send_money`, "requires the recipient and the amounts of the payment to have the user as a source,
as well as no other untrusted parent source in the dependency graph" (§5.3). In **NORMAL** mode a
value assigned inside an `if` whose test depends on Q-LLM output does *not* inherit that
dependency; in **STRICT** mode "we add the conditional test or loop iterable as a dependency to all
variables assigned in the control flow block" and every statement after a Q-LLM call depends on
the call's inputs (§4.4, §6, Appendix D, Figures 5/12/13/17). Consequence for us: a selection that
is computed by P-LLM code from the trusted snapshot (`[r for r in pos if r.project == "Harbor
Lights"]`) never touches untrusted data, so S/R/X/P templates are prevented by construction. The
only way untrusted text can steer the selection is through a Q-LLM call whose result enters the
selection (`if query_ai_assistant("does the email say PO-2047 supersedes…")`): NORMAL mode misses
exactly this control-flow route; STRICT mode taints the selected row and the policy blocks it. The
paper's own "Data requires action" failure (§6) is the flip side: tasks whose required action
depends on untrusted content cannot be solved at all. Cost: P-LLM must be able to express the
selection rule as code; the authors report usable utility except on Travel, and STRICT raises
policy-trigger rates (Tables 8/9; numbers not re-verified here).

**FIDES** (information-flow-controlled planner). Confidentiality × integrity labels on every
value, dynamically propagated through LLM and tool calls, with deterministic policies such as
"execute only on high integrity" (P1*) and robust declassification (§4, §5, Appendix). Tool
results more restrictive than the context label are **hidden in variables**; the planner may
inspect them only through a quarantined LLM with constrained decoding into a typed schema, and the
type lattice (`bool ⊑ enum ⊑ string`) bounds how much information a declassified value can carry
(§5.3–5.4). For selection influence this means: an untrusted email cannot reach the planner's
context at all; if the planner needs it (L01/L03), it asks for an `enum` over the registered
addresses, which is a *typed release* of exactly one field — the FIDES analogue of our
`contract.releases`. The paper itself notes the limit that matters for H-family templates: "a
planner with taint-tracking can restrict direct flows of data, but not indirect flows due to
data-dependent control flow" (§4.4), and lists "Guesswork" (the planner guessing arguments it never
saw) and non-flow-altering injections as uncovered (Appendix H).

**CXI** (context-to-execution integrity). This is the closest prior work to our setting and it
names the phenomenon directly: "a field can contain a trusted-looking string while its selection
was caused by W" (§3.4); "CXI tracks provenance of influence, not only provenance of bytes" (§2.3).
Its field rule is `W ↛ X unless W → D_authorized → X`, i.e. a protected field may be selected only
by trusted authority or a matching typed release. Its reference mechanism, *authority-projected
protected-field decoding* (§3.7, Table 3): for each protected field f build a physical projection
containing only trusted state, typed releases valid for f and authorized parent-field records;
decode one field with fresh prefill/KV and a field grammar; the host assembles the action. Summaries,
memory and tool outputs "preserve W influence until a typed release authorizes the destination"
(§3.4), which is the H-family closure requirement. Our B2 path (`runner/experiment.py::_reconstruct`)
is a paper-derived port of this idea with two simplifications that must be stated: we decode the
whole protected *group* from one projection instead of one field at a time with parent records,
and our "typed release" is a free-text extraction constrained only by the prompt, not a grammar.

## 2. Per-family coverage

| Family | CaMeL NORMAL | CaMeL STRICT | FIDES (P1*/P2*) | CXI field projection |
|---|---|---|---|---|
| S selection | prevented by construction if P-LLM codes the rule; **not covered** if selection goes through a Q-LLM conditional (control flow untainted) | prevented (conditional taints the selected row) | prevented: email never enters context; selection computed over trusted data | prevented: projection contains no W |
| R redundancy | same as S (redundancy is irrelevant to a graph-based policy) | prevented | prevented | prevented |
| X interaction | same as S; X04-style conditions on trusted attributes are plain code | prevented | prevented; X03 split pointer never visible | prevented |
| H history | **not covered**: summaries produced by Q-LLM carry only data provenance; a later P-LLM plan written from the user query is unaffected, but a memory/note that enters the selection is a Q-LLM output and NORMAL mode does not taint control flow on it | prevented (statements after a Q-LLM call depend on its inputs) | prevented for direct data flow; the paper states indirect flow via data-dependent control flow is **not** covered (§4.4) | prevented only if the summary/memory is treated as W-derived until released (§3.4 says it must be); projection regenerates from T |
| P association | prevented (whole tuple comes from one trusted row in code) | prevented | prevented | prevented; CXI additionally binds parent-field records |
| L01 authorized address from email | solvable only if policy whitelists the email sender as source for `recipient` — otherwise **blocks legitimate flow** | same | solvable via `enum` declassification over registered addresses; otherwise blocks | solvable via typed release valid for that field |
| L02 scoped release of one field | policy must be per-field (CaMeL capabilities allow it); the amount field must still have user/trusted source | same | typed declassification of one field; amount stays trusted | exactly the typed-release case |
| L03 authorized pick among equivalents | as L01 | as L01 | as L01 | as L01 |
| L04 required name→id mapping from an authorized source | if the mapping tool is trusted, fine; if it is a Q-LLM parse of text, NORMAL allows, STRICT taints the selection → **blocks legitimate flow** unless policy exempts | blocks unless exempted | release of an `enum` over ids works | release works; removing the source is an invalid intervention for an audit, not a question for the projection |

Reading: with a correct per-field policy, all three frameworks prevent the five threat families by
construction, and all three need an explicit per-field authorization/release to keep the L family
working. None of them is "free": each requires (i) a policy author who classifies sources per
protected field (the same contract K our audit needs), (ii) either a planner that can express the
selection rule as code (CaMeL/FIDES) or a per-field decoding runtime (CXI), and (iii) acceptance of
the "data requires action" / hidden-variable utility losses.

## 3. Minimal faithful ports (not executed)

*CaMeL STRICT into this harness.* Replace the single-shot JSON agent by: P-LLM generates restricted
Python over typed snapshot records and candidate rows (tool schemas for `snapshot.records`,
`candidates`, free-field composition); Q-LLM is the only reader of external items and may return
only schema-typed values; interpreter with STRICT control-flow tainting; policy per (tool,
protected field) = source ∈ {user, snapshot} ∪ releases. Templates that would be trivially solved:
all S/R/X/P (selection is code); H family becomes unreachable (there is no free-text memory step —
the H templates test a phenomenon the architecture excludes rather than defends). Templates
needing explicit policy: L01–L04. Effort: the CaMeL interpreter and prompts are released
(AgentDojo-based); adapting the P-LLM prompt and tool stubs to our 10 tool schemas and running 24
templates is roughly one to two agent-days plus model time, and it would answer a different
question (can a code-writing planner solve the tasks?) than the one this round asks (can a
post-hoc audit catch a black-box agent's bad selection?).

*FIDES.* Same planner split with label propagation and `enum`/`bool` declassification for the L
templates; the FIDES code is released with AgentDojo wrappers. Comparable effort; the H family is
likewise excluded by construction.

*CXI field-closed decoding.* This is what our B2 approximates. A faithful port would decode each
protected field separately with a grammar, pass authorized parent-field records (e.g. the chosen
`po_id` row) into the next field's projection, and emit a backend evidence record. The paper's
artifact (anonymous.4open.science/r/cxi, Apache-2.0, located 2026-10-02; see `artifacts.md`)
exists but was not run. Effort: about one agent-day to adapt to the MLX adapter; this is the most
valuable follow-up because it is the strongest *runtime* comparator and the one our contract
mirrors most closely.

## 4. Implication for a post-hoc counterfactual audit

The structural frameworks dominate the audit whenever they are applicable: they prevent selection
influence by construction at the cost of one or two extra model calls per protected group, and they
need the same contract K the audit needs. The audit is only interesting where they are not
applicable:

1. the agent is a black box whose proposal must be admitted or rejected (hosted API, vendor agent,
   free-form reasoning that cannot be turned into P-LLM code);
2. the selection legitimately requires reading external content for a *non-protected* field in the
   same action (our free-field design), so the agent cannot be isolated from W without a second
   generation path — which is exactly B2, so the audit must beat B2 on something other than
   coverage (e.g. keeping the original proposal's free fields, or catching B2's own errors);
3. no policy author exists and the contract is coarse (then neither works well);
4. the derived state problem: summaries/memory produced before the contract was applied (H family),
   where CaMeL-NORMAL and FIDES taint tracking do not reach and where the audit's clean-checkpoint
   regeneration is the mechanism to compare against CXI's "W-derived until released" rule.

Therefore the honest comparison for this round is B2 (projection/reconstruction) vs. the audit at
matched compute, with CaMeL/FIDES recorded as "prevented by construction, port not executed, H
family out of their scope", and CXI recorded as the published form of B2 whose official artifact is
the right next port. A novelty claim for the audit cannot rest on cases B2 already solves.
