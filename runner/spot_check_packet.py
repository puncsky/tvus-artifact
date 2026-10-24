"""Render an author spot-check packet for a stratified sample of cases (m10/t007).

Usage: W3_CASES_DIR=generated/cases python runner/spot_check_packet.py --n 20 --seed 2026 --strata rule_family --out review/spot-check-generated-2026-10.md
Questions A–E are the same as the first packet; C is clarified: for *legitimate* templates the authorized source may carry
selection content by design, and a neutral text may restate values that are already in the trusted snapshot as long as it does
not point at a candidate (the generated set is leak-checked for candidate values, ordinals and discriminating attributes).
"""
from __future__ import annotations
import argparse, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner import schema  # noqa: E402
from runner.schema import load_case, CASES_DIR  # noqa: E402

Q = ("For each template answer A–E with yes/no and a note. (A) the task text makes the selection rule unambiguous from the snapshot alone "
     "(or from the authorized input for legitimate templates); (B) the contract's authorized sources / releases plausibly reflect the user's intent as written; "
     "(C) the neutral text does not point at any candidate (restating a value that is already in the trusted snapshot is allowed; for legitimate templates the "
     "authorized source may carry selection content by design); (D) the attack text introduces only a trusted-valued inducement (never a new value); "
     "(E) the listed allowed tuple(s) are the correct answer. Sign at the end.")


def render(case) -> list[str]:
    rt, ev = case.runtime, case.evaluator
    rule = ev.get("rule"); rule = rule.get("family", "?") if isinstance(rule, dict) else (rule or "?")
    L = [f"## {case.id} ({rt.get('family')}, {rt.get('domain', '?')}, {rt.get('track')}; rule {rule})", "",
         f"**Task:** {rt['task']}", "", f"**Authorization:** {rt['authorization']}", "",
         f"**Contract:** protected {case.protected}; authorized {rt['contract'].get('authorized') or rt['contract'].get('authorized_sources')}; releases {rt['contract'].get('releases') or 'none'}", "",
         "**Snapshot records:**", "```", json.dumps(rt['snapshot']['records'], indent=0, ensure_ascii=False), "```",
         "**Candidates:** " + "; ".join(json.dumps(c, ensure_ascii=False) for c in case.candidates), ""]
    for s in rt["sources"]:
        L.append(f"**Source {s['id']}** ({s.get('channel')}; writable: {s['id'] in rt.get('writable', {}).get('sources', [])}; required: {s.get('required_for_task', False)})")
        L.append("")
        for cond in ("clean", "neutral", "attack"):
            if cond in s["text"]:
                L.append(f"- {cond}: {s['text'][cond]}")
        L.append("")
    L.append(f"**Allowed (evaluator):** `{json.dumps(ev.get('allowed'), ensure_ascii=False)}`  **Attack target:** `{json.dumps(ev.get('attack_target'), ensure_ascii=False)}`")
    L += ["", "| A unambiguous | B contract reflects intent | C neutral is neutral | D attack trusted-valued | E allowed correct | note |", "|---|---|---|---|---|---|", "|  |  |  |  |  |  |", ""]
    return L


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20); ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--strata", default="family"); ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", default=None, help="generated/cases/manifest.json for rule_family/domain/split strata")
    a = ap.parse_args()
    ids = [p.name for p in schema.list_cases()] if hasattr(schema, "list_cases") else [p.name for p in sorted(CASES_DIR.glob("*/*")) if (p / "runtime.json").exists()]
    meta = {}
    if a.manifest:
        meta = {t["id"]: t for t in json.loads(Path(a.manifest).read_text())["tasks"]}
    strata: dict[str, list[str]] = {}
    for i in ids:
        key = meta.get(i, {}).get(a.strata) or load_case(i).runtime.get(a.strata, "?")
        strata.setdefault(str(key), []).append(i)
    rng = random.Random(a.seed)
    picks: list[str] = []
    keys = sorted(strata)
    while len(picks) < a.n:
        for k in keys:
            pool = [i for i in strata[k] if i not in picks]
            if pool and len(picks) < a.n:
                picks.append(rng.choice(pool))
    picks.sort()
    L = [f"# Author spot-check packet — {len(picks)} cases from `{CASES_DIR}` (stratified by {a.strata}; seed {a.seed})", "", Q, ""]
    for i in picks:
        L += render(load_case(i))
    L += ["---", "Reviewer: ________   Date: ________   Signature: ________", "",
          "Summary (fill in): templates checked ___/" + str(len(picks)) + "; disagreements: ___ (list ids and the issue)."]
    Path(a.out).write_text("\n".join(L) + "\n")
    print("wrote", a.out, picks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
