# Baseline comparison matrix (B0–B6)

Rebuilt 2026-10-02. This file describes the code as it stands:
- `runner/experiment.py` records the signals.
- `runner/analyze.py` applies the gate rules post hoc (`DEFENSES`, `decide()`, `outcome()`, `cost_for()`).

No results appear here. Artifact provenance is in `artifacts.md`; protocol details are in `protocol.md` §§6–7 and 10.

Labels:
- **native**: the official artifact is run.
- **port**: re-implemented from the paper.
- **conceptual**: a control modeled on the idea, not on a specific system.
- **study**: this project's own agent or reference.

## 1. Matrix

| Group | Key(s) | Label | Signals (execution record) | Gate rule | History handling | Cost charged beyond B0 (`cost_for`) | What it can and cannot establish |
|---|---|---|---|---|---|---|---|
| B0 | `b0` | study | `b0` | PASS every parsed proposal | Notes generated from h0 with sources visible; raw sources hidden at action time where `hide_sources_at_action` | none | Capability and attack background. Never the sole opponent. |
| B1 | `b1_port`, `b1_conservative` | **port** (paper-derived; **not the official PACT resolver**) | `b0.protected`, snapshot, candidates, condition source texts, `contract.releases` | Port: PASS if every protected value is in the snapshot/candidate text. Conservative: also BLOCK (fail-closed) if a protected value appears in an unauthorized source (release field exempt for its own source). | Notes are not scanned, only raw source text | none (string checks) | Whether a value-provenance check of this form passes trusted-valued selection, and how often conservative labels block. Says nothing about PACT's real resolver, inference accuracy or fail-closed path. |
| B2 | `b2_reconstruction` | **port** (paper-derived, **CXI-style**) | `reconstruction`, `released` | Execute the reconstructed protected tuple. Parse failure → parse_failure; non-candidate → blocked. | Notes regenerated from h0 without unauthorized sources | `b2/*` + `release/*` | Does dropping unauthorized sources while keeping authorized and released facts solve each task, and at what utility cost (especially L cases)? Not a CXI artifact reproduction. Deterministic ID binding is not exercised because `contract.explicit_binding` is null in all 24 fixtures (tasks state rules, not IDs). |
| B3 | – | **not implemented** | – | – | – | – | **Coverage gap** (CaMeL STRICT / FIDES). |
| B4 | `b4_loo`, `b4_joint_score`, `b4_joint_regen` | **conceptual** (ContextCite/AttriBoT-style LOO; artifacts not run; no surrogate or KV acceleration) | `loo:<unauthorized>`, `joint` | LOO: max log-prob drop of the proposal > `loo_max`. Joint score: drop > `joint_drop`. Joint regen: regenerated tuple differs → BLOCK; unparsable → UNKNOWN. | In place (B0 notes reused) | `base/*` + `loo:*` (upper bound; includes `loo:user` and authorized spans); `joint/*` | Is single-source deletion insufficient for redundancy and interaction? Does naive joint deletion suffice? |
| B5 | `b5_causalarmor_port`, `b5_causalarmor_calibrated`, `b5_enhanced` | **port** (paper-derived; no official artifact; the unofficial `prashantkul/causal-armor` is not used) | `loo:user`, `loo:<every external>` (contract-agnostic), `joint` / `closure:joint` | Port: BLOCK if any span's per-token LOO attribution exceeds the user request's (τ = 0). Calibrated: margin > `ca_margin`. Enhanced: regeneration mismatch, or candidate-relative R > `enh_R`. | Port: raw segments in place (no retroactive CoT masking or sanitize). Enhanced: closure from h0. | `base/*` + `loo:*`; enhanced `base/*` + `(closure:)joint/*` | The strongest attribution neighbour. If enhanced B5 matches B6, the B6 difference is not a new algorithm. The port omits the paper's sanitizer/mask remedy, so its remedy path is not evaluated. |
| B6 | `b6_reference` + ablations `b6_scores_only`, `b6_regen_only`, `b6_chosen_only` | **study** (correctness reference; not deployable as-is) | {`closure:joint`, `closure:neutral`} on history; {`joint`, `neutral`} on direct | UNKNOWN on an invalid member or unparsable regeneration. BLOCK on regeneration mismatch, D > `ref_D` or R > `ref_R`. Ablations isolate scores, regeneration and chosen-only scoring. | Closure from h0 on the history track | `base/*` + the minimal set's calls + `release/*` | Whether full-action, contract-conditioned joint intervention plus fresh regeneration adds signal over B2, B4-joint and enhanced B5, at measured cost. The `neutral` member uses authored (oracle) neutral text. |
| opt. | – | not implemented | – | – | – | – | ProvenanceGuard [8], Agent-Sentry [9]: optional, not covered. |

Thresholds come from the 95th percentile of each statistic on development clean+neutral executions (`analyze.py --calibrate`), then are frozen to `thresholds.json` for confirmation (`--thresholds`). See `protocol.md` §10 for why a per-statistic quantile does not by itself guarantee a joint false-block rate of 5 % or less.

## 2. Fairness requirements

Every group is evaluated on the same:

1. **Tasks and trusted facts.** Same `runtime.json`, snapshot, candidate set and order, and contract. The runtime hash is recorded in every run manifest.
2. **Releases.** The scoped release in L02 (`payout_account_id`) is available to every group. If an intervention removes a release source, its typed fact is injected. B1-conservative exempts the released field for its own source. No group loses authorized information.
3. **Sink.** The single outcome function (`analyze.py::outcome`, `simulator.py::Sink` semantics) is the only place evaluator truth is read, and only after the gate.
4. **Retry policy.** No retries this round: one proposal per execution, and BLOCK/UNKNOWN are terminal. Any later retry policy applies to all groups and is costed.
5. **Budgets.** The same 2048-byte writable budget and 20-query search cap per (task, defense) apply, with the same feedback tier for each. Search is not implemented yet.
6. **Calibration.** Every thresholded group is calibrated on the same clean+neutral executions with the same quantile, then frozen together. The only exception is `b5_causalarmor_port`, which keeps the paper's τ = 0.
7. **Cost.** Each group is charged for the calls its rule depends on, from the same `CostLedger`. Wall seconds and forward passes are reported as ratios to B0's agent cost.

## 3. Native vs shared-shell

| Comparison type | This round |
|---|---|
| Native system end-to-end (official artifact with its own agent and replanning) | **None.** PACT and CausalArmor have no official artifact located. The CXI anonymous artifact was located on 2026-10-02 but has not been pinned or run. CaMeL and FIDES are not attempted. |
| Shared shell, with only the audit/gate component replaced | All of B0–B6 (same agent, prompt, run records and sink) |

If a native comparison is added later, it is reported as a separate table and never merged into the shared-shell rows.

## 4. Coverage gaps (stated, not hidden)

- There is no official PACT resolver. B1 cannot support PACT claims, and the PACT question stays **inconclusive**.
- B3 (CaMeL STRICT / FIDES) is not run.
- The ContextCite and AttriBoT artifacts are not run. B4 is conceptual.
- The B5 port has no sanitize or retroactive-masking remedy. Its "neutral" comparison point elsewhere in the study is an authored oracle.
- ProvenanceGuard and Agent-Sentry are not covered.
- There is no independent human review of the port rules (pending).
