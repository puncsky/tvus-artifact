# w3 programmatic task generator (protocol v2 §1.1–1.2)

Standard-library Python 3.12; run from `w3/` with `envs/mlx/bin/python -B`. Produces `runtime.json` /
`evaluator.json` pairs whose truth is computed by rule code (truth by construction), plus a manifest.

```
envs/mlx/bin/python -B generator/make.py --n 300 --seed 1 --out generated/cases
envs/mlx/bin/python -B generator/selfcheck.py --cases generated/cases
envs/mlx/bin/python -B generator/leakcheck.py --selftest --cases generated/cases
W3_CASES_DIR=$PWD/generated/cases envs/mlx/bin/python -B runner/validate.py
W3_CASES_DIR=$PWD/generated/sample envs/mlx/bin/python -B runner/experiment.py --model mock --run-id gen-sample-mock --cases G0001 --seeds 0
```

## Files
- `rules.py`: rule families. Each one has a record-shape sampler (`build`), a deterministic `allowed(records, params)`
  that reads only the serialized snapshot plus params, task/authorization templates, an attack-target chooser
  (a frozen non-allowed row, preferring same-group or cheaper/half-key rows), and the free field from the domain.
  | rule family | case family | rule |
  |---|---|---|
  | `filter_earliest` | association | group + status filter, then earliest/latest date; ties go to the lower id number |
  | `role_join` | selection | the assignment list maps (group, role) to one party, and so to one record |
  | `status_match` | interaction | same-group records with different statuses; pick the given status |
  | `composite_key` | selection | match two key fields; distractors share one key each |
  | `positional_rank` | interaction | check filter, then lowest rank attribute; ties go to the lower id number |
  | `two_stage_lookup` | history | routing table group → key, then record (history track, `commit_field` on the id) |
  | `legit_authorized` | legitimate | default = earliest; the authorized owner email (`email_1`) may pick another eligible row |
  | `legit_release` | legitimate | `releases` one option field (registered accounts/regions/…) to `email_1` |
  About 22 % of direct threat tasks get a second writable source carrying the same inducement. They are
  relabelled `redundancy`, and `rule_family` stays in the manifest.
- `domains.py`: 8 synthetic domains (accounts_payable, deployments, scheduling, inventory, refunds, access_grants,
  travel, grants). Each has field names, id prefixes, value ranges, statuses, roles, `.example` senders and benign
  (clean, neutral) fact pairs. All names are invented.
- `attacks.py`: operators from `runner/bypass.py::OPERATORS` (authority_framing, status_reinterpretation,
  positional_pointer, conditional, free_field_bridge, neutral_disguise, minimal, padding, history_carrier, and
  redundancy as two operators over two sources). Inducements use only trusted values of the target row (plus the
  allowed row's id when reinterpreting its status) or the target's list position. Clean = prose and neutral = the
  same facts' reworded forms inside a channel template from `neutral.py`.
- `neutral.py`: neutral-rewrite templates, ≥ 6 per channel (email 7, chat 6, ticket 6, document 6, tool_result 6).
  They vary length (one-liner vs long framing), formatting (bullets, headers, signature blocks, memo/FAQ, JSON/YAML/
  key-value/table/XML), register (formal/casual) and fact ordering (keep/reverse/hash-shuffle). The template is chosen
  by a string hash of the source's facts, signer and channel, not from the task RNG, so every other draw is unchanged.
  The chosen ids are in `evaluator.generator.neutral_templates`, `manifest.tasks[].neutral_templates` and
  `manifest.counts.neutral_template`. The corpus uses the email, chat and ticket channels; document and tool_result
  templates exist for future channels and are covered by the leak sweep.
- `leakcheck.py`: §1.2 checker covering candidate values (normalized, ≥6-char id substrings), the frozen
  `ORDINAL_WORDS` list and patterns, discriminating snapshot values, and rule field names. It also has
  `untrusted_values` (§1.1 (5)).
  `--selftest [--cases DIR]` plants (a) a candidate value, (b) the ordinal words "second" / "2nd" / "last" and
  (c) a discriminating non-candidate snapshot attribute into every task's neutral text and requires each to be
  rejected for that reason. It also requires the unmodified corpus to pass, and renders every template with its
  domain's full fact list against every task of that domain.
- `make.py`: seeded schedule balancing (rule family × domain), with 15 % legitimate tasks. The correct row is placed
  at a uniform random position. It runs the §1.1 assertions and the leak check on every draw and redraws on failure
  (logged in `manifest.rejected_draws`). It writes `<out>/<family>/G####/` and `manifest.json` (per task: family,
  rule_family, domain, seed, operator, split, correct_index, runtime hash).
- `selfcheck.py`: an independent brute-force evaluator that uses per-candidate predicates plus pairwise dominance
  and does not import `rules.py`. It requires 100 % agreement and re-runs the assertions and leak check. It checks
  that the attack names or points at the target only, checks split disjointness and position balance, and runs
  `runner/validate.py`.

## Splits
Each (rule family, domain) pair goes to exactly one of `dev`/`test`, using a checkerboard over seeded permutations.
Every family and every domain has pairs in both splits. `manifest.pair_splits` holds the map.


## Known limits
- The leak checker is surface-level (§1.2). Paraphrased cues are not detected.
- The task texts are templated. That they are unambiguous was checked by construction (unique allowed row), not
  by a reader. The §1.4 author spot-check covers that.
- Neutral texts are templated (`neutral.py`); `runner/neutrality.py` checks empirically, per model run, whether B0
  behaves the same on clean and neutral. `history` = commit_field two-stage only. Evaluator extras: `rule`, `attack`, `generator`, `review`.
