# Author spot-check, packet 2 (generated tasks) — result and disposition

Packet: `review/spot-check-generated-2026-10.md` (20 of the 300 generated tasks, stratified over the eight rule families, seed 2026, rendered by `runner/spot_check_packet.py`). Answers: `review/spot-check-generated-2026-10-answer.md` and, after the fixes, `review/spot-check-generated-2026-10-addendum-answer.md`; both signed Tian Pan, 2026-10-05. Reviewer saw fixtures and evaluator labels only.

| | first pass | after fixes |
|---|---|---|
| tasks checked | 20/20 | 20/20 (B) + 3/3 regenerated (A–E) |
| A rule unambiguous | 17/20 | 20/20 |
| B contract reflects intent | 0/20 (renderer bug: `authorized None`) | 20/20 |
| C neutral text neutral | 20/20 | 20/20 |
| D attack trusted-valued | 20/20 | 20/20 |
| E allowed tuple correct | 17/20 | 20/20 |
| disagreements remaining | – | none |

## Findings and disposition

**Renderer bug (B ×20).** The packet printed `authorized None` because the renderer read `contract.authorized` while generated contracts use `contract.authorized_sources`. The reviewer explicitly scored this as a disclosure problem, not a fixture claim. Fixed in `runner/spot_check_packet.py`; with the real contract lines B is 20/20 yes.

**Generator defect (A/E on G0060, G0231, G0257; `legit_release` family, 23/300 tasks).** The release ("the party's verified email may select the option") named an identity check whose reference — the party's registered contact — did not exist in the snapshot, so the attack-condition allowed tuple could not be justified from the fixture; and the task's "all protected fields from that one record" clause contradicted the option field coming from `registered_option` rows. Fix: `generator/rules.py::LegitRelease` adds a `registered_contact` row per eligible party, sets email_1's sender to it, and states the option source in the task text; `generator/make.py` names the check precisely. Regenerated with the original seed: exactly the 23 `legit_release` tasks changed, 277 byte-identical (protocol-v2 addendum 8). The reviewer re-read the three regenerated fixtures: A–E all yes. The six affected tasks in the 48-slice were re-run on Qwen2.5-14B H1 and the four hosted agents with their original run specs and frozen thresholds.

**Reviewer's scope note (verbatim intent):** the review covers the packets as rendered; it does not independently verify the generator implementation, the byte-identity of the other tasks, or the agent re-runs. Those are established by `tmp/hashes-before.json` vs the regenerated manifest, `generator/selfcheck.py`, `runner/validate.py` and the re-run logs.

## What the two packets establish together

40 fixtures (20 hand-written across all suites, 20 generated across all rule families) read by the author from the fixture alone: 39/40 allowed tuples confirmed as rendered (the exception, F02, is a deliberate incomplete-state boundary whose nominal tuple the reviewer rejected — the fixture's own thesis); 40/40 attack texts introduce only trusted values; one generator family defect found and fixed before any test-split run.
