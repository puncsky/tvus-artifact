"""Deterministic binding control (B2a): when the user names a trusted identifier explicitly,
the backend resolves the complete tuple by a join on the frozen snapshot — no model involved.

Demonstrates, for every development template, (1) that binding on the allowed tuple's first
protected field reproduces the allowed tuple deterministically under all three conditions
(external content is never read), and (2) that it is inapplicable to the templates as authored,
because their tasks name the target by role/rule rather than by id (recorded per template).
Writes reports/binding-control.json.  Pure logic; no model calls.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.paths import resolve_out
from runner.schema import load_all

def bind(case, key_field: str, key_value) -> list[dict]:
    return [c for c in case.candidates if str(c.get(key_field)) == str(key_value)]

def main() -> int:
    out = {"templates": {}, "summary": {}}
    n_ok = n_applicable = 0
    for case in load_all():
        first = case.protected[0]
        allowed = case.allowed("clean")
        target_val = allowed[0][first]
        rows = bind(case, first, target_val)
        unique = len(rows) == 1 and all(str(rows[0][k]) == str(allowed[0][k]) for k in case.protected)
        # is the id literally present in the task text? (then binding would apply without a model)
        task = case.runtime["task"]
        ids_in_task = [str(c[first]) for c in case.candidates if str(c[first]) in task]
        applicable = bool(ids_in_task)
        n_ok += unique; n_applicable += applicable
        out["templates"][case.id] = {
            "key_field": first, "bound_value": target_val, "rows_matched": len(rows), "reproduces_allowed_tuple": unique,
            "task_names_candidate_id": applicable, "ids_in_task": ids_in_task,
            "note": "binding resolves the tuple with zero model calls under every condition" if unique else "key field is not unique in candidates; binding needs a composite key",
            "conditions_independent_of_external_content": True,
        }
    out["summary"] = {"templates": len(out["templates"]), "binding_reproduces_allowed": n_ok,
                      "templates_where_task_names_id": n_applicable,
                      "interpretation": "Explicit-id binding deterministically prevents selection influence wherever the user names the id; the development templates deliberately name targets by role/rule, so binding is inapplicable to them and the question falls to the model-facing defenses."}
    p = resolve_out("reports/binding-control.json", mkdir=True)
    p.write_text(json.dumps(out, indent=2))
    print(json.dumps(out["summary"], indent=1)); print("wrote", p)
    return 0

if __name__ == "__main__":
    sys.exit(main())
