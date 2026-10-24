# Formalism: selection provenance and Trusted-Value, Untrusted-Selection (TVUS)

*m7/t002. Notation used verbatim by `paper/paper.md`. No new experiments; every number cited is from `reports/signal-probe.md` and the paper's §7. Implementation symbols are in §6.*

## 1. Setting

**Task and trusted state.** A task $\tau$ (the user's request and authorization) and a trusted snapshot $T$ (frozen business records). A tool has fields $F = G \cup \Phi$: the *protected group* $G = (f_1,\dots,f_k)$ and the *free fields* $\Phi$ (memo, reason, note), which the task asks the agent to fill from external items.

**Candidates.** The backend supplies a frozen candidate set $A(T,G) = \{g_1,\dots,g_n\}$, $n \ge 2$. Each $g_j$ is a complete assignment to $G$ taken from one row of $T$. Write $\mathrm{TR}(T)$ for the set of values that occur in $T$ or in $A(T,G)$ ("trusted records"). Then $g_j(f_i) \in \mathrm{TR}(T)$ for every $j$ and $i$.

**Sources.** The context $C$ contains $\tau$, $T$, $A(T,G)$ and a set of sources $S$ (emails, documents, tool results, chat messages). Every $s \in S$ has an *authority class*. It is either authorized for $G$, released for one field, or unauthorized. The attacker writes only $W \subseteq S$ and is bounded to 2048 bytes. The attacker cannot change $\tau$, $T$, $A$ or the contract.

**Contract.** A contract $K = (G, S_{\mathrm{auth}}, R, \rho)$ has four parts.
- $S_{\mathrm{auth}} \subseteq S \cup \{\text{user}, \text{snapshot}\}$ is the set of sources that may influence $G$.
- $R$ is a set of typed releases $r = (f, s, \nu)$: field $f$ may take its value from source $s$, verified by procedure $\nu$.
- $\rho$ is the relation, meaning that all of $G$ comes from one candidate row (plus released fields).

The **influence policy** per protected field is
$$P(f_i) = S_{\mathrm{auth}} \cup \{s : (f_i, s, \cdot) \in R\}, \qquad P(G) = \textstyle\bigcap_i P(f_i) = S_{\mathrm{auth}} \text{ (when no release spans all of } G).$$
The sources without group-wide authority are $U = S \setminus S_{\mathrm{auth}}$; this includes release sources. A release is *explicit declassification*: it admits the verified typed fact $v_f$ for its field, never the source's raw text or authority over another field. The intended verified fact $v_f$ is distinct from the extractor estimate $\hat v_f = E_f(x_s)$, which can be wrong. The current implementation is group-level: one $S_{\mathrm{auth}}$ for all of $G$, plus per-field releases. CXI's per-field projection with parent records is finer.

**Agent and sink.** The ordinary agent is a stochastic map $\pi : C \mapsto a = (g, \varphi)$. Here $g$ is the proposed protected tuple and $\varphi$ the free-field values. A gate $\gamma(a, C) \in \{\textsf{PASS}, \textsf{BLOCK}, \textsf{UNKNOWN}\}$ decides on the proposal. The **sink** executes $a$ iff $\gamma = \textsf{PASS}$ and the proposal parses. For B2, it executes the reconstructed action. The sink is the only place where evaluator truth is consulted, and only after the decision.

**History.** On the history track, recipe steps run before the action and produce derived state $h$: notes, retrieved memory, rankings and early field commitments. $h_0$ is the state before any external item has been seen.

## 2. Definitions

**Allowed set.** $\mathrm{Allowed}(\tau,T,P) \subseteq A(T,G)$ abbreviates the allowed set in the current *authorized view*:
$$V_P(C)=(\tau,T,K,\{x_s:s\in S_{\mathrm{auth}}\},\{v_f\}),\qquad
\mathrm{Allowed}(\tau,T,P)=\mathrm{Allowed}(V_P(C)).$$
Non-interference applies only to changes preserving this view, including the verified release facts. Changing a release source's authorized designation may legitimately change Allowed. Ordinary threat templates have no writable authorized facts, so their Allowed set stays fixed across conditions. Legitimate-dependency templates can change Allowed through authorized content. The reconstruction view in §4 contains estimated facts and is not itself the definition of evaluator truth.

**Value provenance and selection provenance.**
- *Value provenance* asks, field by field, where the bytes came from: does $g(f_i) \in \mathrm{TR}(T)$ for every $i$? PACT-style argument provenance and our B1 port check this.
- *Selection provenance* asks whether the distribution of $g$ changes under interventions on raw sources that preserve $V_P(C)$, including authorized release facts.

Value provenance is necessary for authority over $G$ but not sufficient. By construction, every element of $A(T,G)$ passes it.

**Selection violation.** An executed tuple $g$ is a *selection violation* iff
$$g \notin \mathrm{Allowed}(\tau,T,P) \quad\text{and}\quad \forall i:\ g(f_i) \in \mathrm{TR}(T).$$
The second conjunct is automatic for $g \in A(T,G)$. The template validator also requires the attack target $g^\dagger$ to satisfy $g^\dagger \in A(T,G) \setminus \mathrm{Allowed}$, so every attack is a trusted-values attack.

**Attack success** is a selection violation that *reaches the sink*: the gate passed it and the sink executed it. Blocked proposals, UNKNOWN, parse failures and refusals are counted separately.

**Conditions as interventions.** Each writable source has three texts, $x_s^{\mathrm{clean}}$, $x_s^{\mathrm{neutral}}$ and $x_s^{\mathrm{attack}}$. A condition $c$ is the intervention $\mathrm{do}(x_W = x_W^{c})$, and everything else is held fixed.
- *neutral* changes wording, length and format, but not selection content.
- *attack* adds unauthorized selection inducement. On L templates it adds authorized influence instead.

**Attributable.** An attack execution is *attack-attributable* iff the clean execution with the same seed is a correct automatic completion. Capability-failure template flags are descriptive: only the failing clean seed is excluded, and other clean-correct seeds on that template remain attributable.

**Selection counterfactual.** For an authorized-view-preserving intervention $\iota$ on raw $U$, write $C^{\iota}$ for the intervened context. Deletion and neutral replacement retain the authorized release facts. The implementation holds the extractor's estimate $\hat v_f$ fixed across the original and intervened views; its correctness is assumption A7, not guaranteed by projection. The proposal's protected choice is *unauthorized-dependent* iff
$$\pi_G(C) \neq \pi_G(C^{\iota}) \quad\text{or}\quad p(\cdot \mid C) \neq p(\cdot \mid C^{\iota}) \text{ on } A(T,G),$$
where $\pi_G$ is the protected part of the proposal. On the history track, $C^{\iota}$ must be built by regenerating $h$ (§3, P2).

An intervention is *valid* only if it touches no authorized source and removes no source that the task requires. Released sources are exempt from the second condition because their typed fact is injected in place of the raw text. An invalid intervention yields UNKNOWN, not BLOCK.

## 3. Two failure principles

**(P1) Chosen-action attribution is confounded by legitimate free-field dependence.**

Teacher-forced scoring of the full serialized action $a = (g,\varphi)$ factorizes as $\log p(a\mid C) = \log p(g\mid C) + \log p(\varphi \mid g, C)$. A chosen-action attribution (LOO, joint-deletion drop, the CausalArmor span-vs-user margin) is a function of
$$\Delta_U(a) = \log p(a\mid C) - \log p(a\mid C^{\setminus U}) = \underbrace{\big[\log p(g\mid C) - \log p(g\mid C^{\setminus U})\big]}_{\text{protected-selection term}} + \underbrace{\big[\log p(\varphi\mid g,C) - \log p(\varphi\mid g,C^{\setminus U})\big]}_{\text{free-field term}}.$$

The task requires $\varphi$ to quote or summarize the external items. Removing $U$ therefore makes the proposal's $\varphi$ improbable whether or not the selection was induced. The free-field term is large, scales with the length of $\varphi$, and is present in clean executions. Measured on threat templates: the chosen-action drop under joint deletion has a clean median of 79.4 nats and a p95 of 163.6 (Qwen), versus 98.7 and 230.7 (Llama). Attack-induced medians are 105.9 and 98.8, inside the clean range. A threshold calibrated on clean executions therefore sits above most attacks. Twenty-one to twenty-five of 60 attacks executed under the LOO, joint-drop and calibrated-margin gates on Qwen, and 20 of 60 on Llama. The uncalibrated rule ($\tau{=}0$) fails the other way: it flags 108/144 and 100/144 clean and neutral executions and 12/12 legitimate dependencies. Influence is exactly what it measures, and here most influence is authorized.

**Candidate-relative statistics cancel the free-field term.** Score every $g_j \in A(T,G)$ with the *same* free fields $\varphi$ (the proposal's), so that $a_j = (g_j,\varphi)$. Let $j_0$ be the proposal's index. The log-odds against rival $j$ is
$$L_j(C) = \log\frac{p(a_{j_0}\mid C)}{p(a_j\mid C)} = \log\frac{p(g_{j_0}\mid C)}{p(g_j\mid C)} + \log\frac{p(\varphi\mid g_{j_0},C)}{p(\varphi\mid g_j,C)}.$$
Any part of $\log p(\varphi\mid g,C)$ that does not depend on $g$ cancels. Only the $g \times U$ interaction of the free-field term survives. The study's statistics are
$$R = \max_{j\neq j_0}\big|L_j(C) - L_j(C^{\iota})\big|, \qquad D = \mathrm{TV}\big(\mathrm{softmax}_j \log p(a_j\mid C),\ \mathrm{softmax}_j \log p(a_j\mid C^{\iota})\big).$$
Both are invariant to a shared additive term. Measured R has a clean median and p95 of 2.7 and 8.7 against an attack-induced median of 23.6 (Qwen), and 1.7 and 5.9 against 9.1 (Llama).

Two residual effects remain:
1. If $\varphi$ itself is polluted (for example, it names the target), the interaction term is non-zero. The tuple-only variant $R_t$ blanks $\varphi$ to remove it.
2. On Qwen, D calibrates to roughly 0, because the clean candidate distribution is nearly deterministic, and formatting alone moves D by 0.27. R is the usable statistic and D is not.

**(P2) Late deletion misses propagated influence.**

Let the recipe produce $h = H(\tau, T, A, x_{S};\ \xi)$, where $\xi$ is the sampling randomness. The action is drawn from $\pi(\tau,T,A,h,x_{S}^{\mathrm{act}})$, where $x_{S}^{\mathrm{act}}$ is what is visible at action time. That is empty when sources are hidden at action time.

*In-place* (last-turn) deletion intervenes only on the action-time view:
$$C^{\mathrm{in}} = (\tau,T,A,\ h,\ x^{\mathrm{act}}_{S\setminus U}), \qquad h \text{ unchanged}.$$
When $U$ influences $g$ through $h$, the path $U \to h \to g$ is untouched. In the extreme case where sources are hidden at action time, $C^{\mathrm{in}} = C$, so the regenerated choice equals the original: it is identical under greedy decoding and equal in distribution under sampling. The R03 template shows that hiding is not necessary. There the raw email is visible and is deleted, but the agent's own summary of it stays in $h$, and that is enough.

*Closure* is the intervention at exposure time. Regenerate the recipe from $h_0$ under the intervened sources:
$$h^{\iota} = H(\tau,T,A,x^{\iota}_{S};\ \xi), \qquad C^{\mathrm{cl}} = (\tau,T,A,\ h^{\iota},\ x^{\mathrm{act},\iota}_{S}).$$
This is the counterfactual of §2, and it treats every element of $h$ as derived from $U$ until it is re-derived without $U$. Measured: in-place deletion with regeneration executed 9/60 (Qwen) and 16/60 (Llama) attacks, all on history-track templates apart from capability cases. Closure executed 0 attributable attacks in both families.

## 4. Reconstruction as reference semantics

**Projection.**
$$\Pi_P(C) = \big(\tau,\ T,\ A(T,G),\ K,\ \{x_s : s \in S_{\mathrm{auth}}\},\ \{(f, \hat v_f, s, \nu) : (f,s,\nu)\in R\}\big),$$
with history regenerated from $h_0$ on this view. Here $\hat v_f = E_f(x_s)$ is the separate extractor's estimate of the verified fact $v_f$. Raw text of a release source outside $S_{\mathrm{auth}}$ is not included. An estimate differing from $v_f$ is an extraction failure.

**B2 (trusted reconstruction).** $g^{*} = \pi_G(\Pi_P(C))$. The executed action is $(g^{*}, \varphi)$, with the free fields taken from the original proposal (*field isolation*). By construction, $g^{*}$ cannot depend on any $s \in U$ except through typed releases.

**Audit = the same call used as a gate.** The joint-intervention auditor regenerates from $h_0$ on $C^{\iota}$. With $\iota$ = deletion of $U$ plus typed releases, $C^{\iota} = \Pi_P(C)$. Its regeneration branch is the test $\pi_G(C) \stackrel{?}{=} g^{*}$, followed by BLOCK on disagreement. Running the call as a check rather than as the output buys one thing, the proposal's own $\varphi$. B2 also keeps $\varphi$, through field isolation. The check costs one extra generation and adds an UNKNOWN outcome. On these templates the score branch detected nothing that regeneration did not, at about 5× the passes (17.6× versus 3.0× B0 for the full reference; B2 costs 2.0×). In this sense reconstruction dominates the auditor.

**What reconstruction assumes.** Each assumption is a failure-boundary hypothesis, probed by templates F01–F08 (`.pm/w3/m8/t004.md`).

| assumption | if violated | probe |
|---|---|---|
| A1 candidate generation is untainted: $A(T,G)$ is produced without reading $U$ | the attacker shapes the choice set before the projection applies | F01 |
| A2 $T$ suffices: Allowed is computable from $\Pi_P(C)$ without an unreleased external fact | reconstruction is under-informed and should return UNKNOWN | F02 |
| A3 $\tau$ is self-contained: authorization does not depend on context stated only in $U$ | the projection drops legitimate authority | F03 |
| A4 $h_0$ is clean: no influence was laundered into "trusted" memory before $h_0$ | closure regenerates from a polluted start | F04 |
| A5 fields are separable: $G$ and $\Phi$ are disjoint and field isolation is meaningful | influence crosses the protected/free boundary | F05 |
| A6 candidate identity is stable: ids are not attacker-influenced synonyms | value provenance and selection both pass on the wrong row | F06 |
| A7 the release extractor is reliable: $E_f$ returns the verified value | B2 executes a wrong released value (observed on K08 with Llama-3.1-8B) | F07 |
| A8 a contract exists: $K$ (hence $P$) is available | no projection can be formed | F08 |

## 5. The phenomenon

**Trusted-Value, Untrusted-Selection (TVUS).** An executed protected tuple is a TVUS violation when each protected value is trusted, $g(f_i) \in \mathrm{TR}(T)$, but unauthorized influence under an authorized-view-preserving intervention changes the choice and the result falls outside $\mathrm{Allowed}(\tau,T,P)$.

Usage: "TVUS attack" means inducement written into $W \subseteq U$ that targets $g^\dagger \in A(T,G)\setminus\mathrm{Allowed}$. "TVUS violation" means a selection violation reaching the sink. "TVUS-resistant" describes a path whose executed $g$ is invariant to $x_U$ (B2, closure regeneration).

Value-provenance checks pass every TVUS violation by definition: B1 passed 26/60 and 22/60 executed attacks.

## 6. Formal object → implementation

| object | implementation |
|---|---|
| $\tau$ | `runtime.json`: `task`, `authorization` |
| $T$, $\mathrm{TR}(T)$ | `runtime.json`: `snapshot`; the TR test is `analyze.py::signals` → `all_values_trusted` (string match against snapshot + candidates) |
| $A(T,G)$ | `runtime.json`: `candidates`; integrity checked in `schema.py::validate_case` |
| $G$, $\Phi$ | `contract.protected_group`; $\Phi$ = `tool.fields` minus `protected_group` |
| $S$, authority classes | `sources[].id`; `schema.py::Case.authorized_sources` / `Case.unauthorized_sources` |
| $S_{\mathrm{auth}}$, $R$, $\rho$ | `contract.authorized_sources`, `contract.releases[{field, source, verified_by}]`, `contract.relation` |
| $W$ | `writable.sources`, `writable.max_bytes` |
| conditions $c$ | `sources[].text.{clean,neutral,attack}`; `schema.py::CONDITIONS`, `schema.py::project` |
| $\mathrm{Allowed}$, $g^\dagger$ | `evaluator.json`: `allowed` (list, or dict per condition for L), `attack_target`; `schema.py::Case.allowed` |
| membership $g\in\mathrm{Allowed}$ | `schema.py::Case.tuple_allowed` (via `Case.protected_tuple`, `_eq_tuple`) |
| sink, attack success | `simulator.py::Sink.execute` → `executed_unauthorized`; post-hoc `analyze.py::outcome` |
| $\pi$, $h$, closure / in-place | `simulator.py::run_agent` (`closure=True` regenerates from $h_0$; `closure=False, reuse_notes` = in-place); `simulator.py::run_history_steps` |
| intervention $\iota$, validity | `experiment.py::_run_and_score` (`drop`, `replace`), `experiment.py::_valid_intervention` |
| $\log p(a_j\mid C)$ with shared $\varphi$ | `simulator.py::score_candidates` (`logprobs`; `logprobs_tuple_only` for $R_t$) |
| $\Delta_U$ (chosen-action) | `analyze.py::signals` → `drop`, `loo_max`, `joint_drop`, `chosen_drop`, `ca_margin` |
| $R$, $D$ | `analyze.py::_rel_change`, `analyze.py::_tv`; `signals` → `ref_R`, `ref_D`, `enh_R`, `ref_R_t`, `ref_D_t` |
| regeneration disagreement | `signals` → `regen_mismatch`, `ref_mismatch`; gates `b4_joint_regen`, `b6_regen_only` in `analyze.py::decide` |
| $E_f$, typed release $v_f$ | `experiment.py::extract_releases`; rendered by `prompting.py::build_action_prompt` ("RELEASED VERIFIED FACTS") |
| $\Pi_P$, B2 | `experiment.py::_reconstruct` (drops `unauthorized_sources`, injects releases, regenerates $h$ from $h_0$) |
| gate $\gamma$ | `analyze.py::decide`; thresholds from `analyze.py::calibrate` (95th percentile, clean + neutral) |

## 7. Related-work positioning

- **Influence Is Not Authority** (arXiv:2608.29942) established that influence is not authority. Attribution signals do not encode authorization and over-fire on legitimate tool-supplied values. It studies only that false-positive direction.
- **Liao** (arXiv:2607.20827) introduced per-target (per-argument) authority labels and context-subset interactions, as an offline audit. Its "invalid" factors always carry a competing value.
- **CXI** (arXiv:2607.06000) gives influence provenance ($W \not\to X$ unless $W \to D_{\mathrm{authorized}} \to X$) and authority-projected field decoding with typed releases. B2 is a group-level port of it.
- **PACT** (arXiv:2605.11039) is argument (value) provenance.

Our increments are the following:
1. **TVUS as a benchmark.** In every attack the target is itself a trusted candidate, so value provenance passes by construction. Templates span the selection, redundancy, interaction, history and association families, with legitimate-dependency controls.
2. **P1 and P2, with measured evidence.** P1 is free-field dependence swamping chosen-action attribution. P2 is late deletion missing influence that has propagated into $h$.
3. **Candidate-relative scoring.** $R$ is the statistic that makes selection influence visible in scores.
4. **Closure versus in-place deletion,** measured on the same executions.
5. **The dominated-auditor result.** Reconstruction run as the output dominates the same call run as an audit.
6. **Cost accounting.** We give a measured account of legitimate-dependency and release costs: scoped releases, extractor failure (A7) and per-path forward passes.
