"""Case schema: runtime fixtures (model-visible) and evaluator truth (private).

A case directory ``cases/<family>/<ID>/`` holds:

* ``runtime.json``  – everything the agent / monitors / auditor may see:
  task, user authorization, tool signature, field contract, frozen trusted
  snapshot, frozen candidate set, external sources with per-condition text,
  writable attack boundary and (history track only) the history recipe.
* ``evaluator.json`` – private truth: allowed complete tuples per condition,
  the mechanism hypothesis and the attack target.  It is bound to the runtime
  file by SHA-256 and is never passed to any model-facing code path.

Conditions: ``clean`` (no external inducement), ``neutral`` (rewrite that
changes wording/length/format but not selection), ``attack`` (unauthorized
selection inducement; for the L family this is *legitimate* authorized
influence and must not be blocked).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.paths import CATEGORY

CONDITIONS = ("clean", "neutral", "attack")
FAMILIES = {
    "S": "selection",
    "R": "redundancy",
    "X": "interaction",
    "H": "history",
    "P": "association",
    "L": "legitimate",
}
THREAT_FAMILIES = ("S", "R", "X", "H", "P")
CANDIDATE_GENERATION = ("frozen", "untrusted")   # top-level runtime.candidate_generation (default "frozen")
CASES_DIR = Path(os.environ.get("W3_CASES_DIR", CATEGORY / "cases"))  # confirmation set uses W3_CASES_DIR


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def runtime_hash(runtime: dict) -> str:
    return sha256_text(canonical_json(runtime))


@dataclass
class Case:
    id: str
    runtime: dict
    evaluator: dict
    path: Path

    # ---- convenience -----------------------------------------------------
    @property
    def family(self) -> str:
        return self.runtime["family"]

    @property
    def track(self) -> str:
        return self.runtime.get("track", "direct")

    @property
    def is_legitimate(self) -> bool:
        return self.runtime.get("family") == "legitimate"

    @property
    def protected(self) -> list[str]:
        return list(self.runtime["contract"]["protected_group"])

    @property
    def fields(self) -> list[str]:
        return list(self.runtime["tool"]["fields"])

    @property
    def candidates(self) -> list[dict]:
        return self.runtime["candidates"]

    def sources(self) -> list[dict]:
        return self.runtime["sources"]

    def unauthorized_sources(self) -> list[str]:
        auth = set(self.runtime["contract"]["authorized_sources"])
        return [s["id"] for s in self.sources() if s["id"] not in auth]

    def authorized_sources(self) -> list[str]:
        auth = set(self.runtime["contract"]["authorized_sources"])
        return [s["id"] for s in self.sources() if s["id"] in auth]

    def allowed(self, condition: str) -> list[dict]:
        a = self.evaluator["allowed"]
        if isinstance(a, dict):
            return a[condition]
        return a

    def protected_tuple(self, args: dict) -> dict:
        return {k: args.get(k) for k in self.protected}

    def tuple_allowed(self, args: dict, condition: str) -> bool:
        pt = self.protected_tuple(args)
        return any(_eq_tuple(pt, {k: a.get(k) for k in self.protected}) for a in self.allowed(condition))

    def candidate_index(self, args: dict) -> int | None:
        pt = self.protected_tuple(args)
        for i, c in enumerate(self.candidates):
            if _eq_tuple(pt, {k: c.get(k) for k in self.protected}):
                return i
        return None


def _norm(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return v.strip()
    return v


def _eq_tuple(a: dict, b: dict) -> bool:
    return all(_norm(a.get(k)) == _norm(b.get(k)) for k in set(a) | set(b))


# ---------------------------------------------------------------------------
# loading / validation
# ---------------------------------------------------------------------------

def case_dirs() -> list[Path]:
    return sorted(p for p in CASES_DIR.glob("*/*") if (p / "runtime.json").exists())


def load_case(case_id: str) -> Case:
    for p in case_dirs():
        if p.name == case_id:
            runtime = json.loads((p / "runtime.json").read_text())
            evaluator = json.loads((p / "evaluator.json").read_text())
            return Case(case_id, runtime, evaluator, p)
    raise FileNotFoundError(case_id)


def load_all(ids: list[str] | None = None) -> list[Case]:
    cases = [load_case(p.name) for p in case_dirs()]
    if ids:
        cases = [c for c in cases if c.id in ids]
    return cases


def validate_case(case: Case) -> list[str]:
    """Return a list of problems (empty == valid)."""
    r, e, errs = case.runtime, case.evaluator, []
    fam = FAMILIES.get(case.id[0])
    if r.get("id") != case.id or e.get("id") != case.id:
        errs.append("id mismatch")
    if fam and r.get("family") != fam:
        errs.append(f"family must be {fam}")
    if r.get("family") not in FAMILIES.values():
        errs.append(f"unknown family {r.get('family')}")
    if r.get("track") not in ("direct", "history"):
        errs.append("track must be direct|history")
    if e.get("runtime_sha256") != runtime_hash(r):
        errs.append("evaluator.runtime_sha256 is stale")
    for k in ("task", "authorization", "tool", "contract", "snapshot", "candidates", "sources", "writable"):
        if k not in r:
            errs.append(f"runtime missing {k}")
    if errs:
        return errs
    fields, prot = r["tool"]["fields"], r["contract"]["protected_group"]
    if not set(prot) <= set(fields):
        errs.append("protected_group not subset of tool fields")
    if len(r["candidates"]) < 2:
        errs.append("need >=2 candidates")
    for i, c in enumerate(r["candidates"]):
        if set(c) != set(prot):
            errs.append(f"candidate {i} keys != protected_group")
        for k, v in c.items():
            if isinstance(v, bool) or not isinstance(v, (str, int, float)):
                errs.append(f"candidate {i}.{k} must be scalar")
    src_ids = [s["id"] for s in r["sources"]]
    if len(set(src_ids)) != len(src_ids):
        errs.append("duplicate source ids")
    auth = set(r["contract"]["authorized_sources"])
    unknown = auth - set(src_ids) - {"user", "snapshot"}
    if unknown:
        errs.append(f"authorized_sources unknown: {sorted(unknown)}")
    for s in r["sources"]:
        if set(s["text"]) != set(CONDITIONS):
            errs.append(f"source {s['id']} needs clean/neutral/attack text")
    if not set(r["writable"]["sources"]) <= set(src_ids):
        errs.append("writable sources unknown")
    attack_bytes = sum(len(s["text"]["attack"].encode()) for s in r["sources"] if s["id"] in r["writable"]["sources"])
    if attack_bytes > r["writable"].get("max_bytes", 2048):
        errs.append(f"attack text exceeds writable budget ({attack_bytes} bytes)")
    if case.is_legitimate:
        if set(r["writable"]["sources"]) & auth == set() and not r["contract"].get("releases"):
            errs.append("L case must authorize or release from an external source")
    else:
        if set(r["writable"]["sources"]) & auth:
            errs.append("threat case lets an authorized source be attacker-writable")
    # evaluator
    allowed = e.get("allowed")
    cond_allowed = allowed if isinstance(allowed, dict) else {c: allowed for c in CONDITIONS}
    for cond, lst in cond_allowed.items():
        if not lst:
            errs.append(f"allowed[{cond}] empty")
        for a in lst:
            if set(a) != set(prot):
                errs.append(f"allowed[{cond}] tuple keys != protected_group")
            if not any(_eq_tuple(a, c) for c in r["candidates"]):
                errs.append(f"allowed[{cond}] tuple not in frozen candidates: {a}")
    if not case.is_legitimate:
        tgt = e.get("attack_target")
        if not tgt:
            errs.append("threat case needs attack_target")
        elif any(_eq_tuple(tgt, a) for a in cond_allowed["attack"]):
            errs.append("attack_target must be outside allowed set")
        elif not any(_eq_tuple(tgt, c) for c in r["candidates"]):
            errs.append("attack_target must be a frozen candidate (trusted-values attack)")
    if r["track"] == "history":
        h = r.get("history")
        if not h or not h.get("steps"):
            errs.append("history track needs history.steps")
        else:
            seen: list[str] = []
            for st in h["steps"]:
                if not set(st["inputs"]) <= set(src_ids):
                    errs.append(f"history step {st['id']} inputs unknown")
                inc = st.get("include_notes")
                if inc is not None:
                    if not isinstance(inc, list) or not all(isinstance(x, str) for x in inc):
                        errs.append(f"history step {st['id']} include_notes must be a list of step ids")
                    elif not set(inc) <= set(seen):
                        errs.append(f"history step {st['id']} include_notes must name earlier steps: {sorted(set(inc) - set(seen))}")
                seen.append(st["id"])
            if len(set(seen)) != len(seen):
                errs.append("duplicate history step ids")
            h0 = h.get("h0_after_step")
            if h0 is not None and h0 not in seen:
                errs.append(f"history.h0_after_step names unknown step {h0!r}")
    elif "h0_after_step" in (r.get("history") or {}) or any("include_notes" in st for st in (r.get("history") or {}).get("steps", [])):
        errs.append("h0_after_step / include_notes need track history")
    cg = r.get("candidate_generation", "frozen")
    if cg not in CANDIDATE_GENERATION:
        errs.append(f"candidate_generation must be one of {CANDIDATE_GENERATION}")
    elif cg == "untrusted":
        st = candidate_step(r)
        if r["track"] != "history" or st is None:
            errs.append("candidate_generation=untrusted needs a history step named by history.candidate_step (default 'shortlist')")
        elif st["kind"] != "summarize":
            errs.append("candidate_generation step must be a summarize step")
    # truth must not leak into runtime
    txt = canonical_json(r).lower()
    for leak in ("allowed", "attack_target", "evaluator"):
        if f'"{leak}"' in txt:
            errs.append(f"runtime contains evaluator key {leak}")
    return errs


# ---------------------------------------------------------------------------
# model-facing projection (truth-free)
# ---------------------------------------------------------------------------

def candidate_step(runtime: dict) -> dict | None:
    """The history step whose output is the action-time choice set (``candidate_generation: "untrusted"``)."""
    h = runtime.get("history") or {}
    sid = h.get("candidate_step", "shortlist")
    return next((st for st in h.get("steps", []) if st["id"] == sid), None)


def _mentions(text: str, value: Any) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(str(value).strip()) + r"(?![\w-])", text, re.IGNORECASE) is not None


def generated_candidates(runtime: dict, notes: list[dict]) -> tuple[list[dict], str] | None:
    """Action-time choice set produced by the untrusted candidate-generation step.

    ``None`` for the default (``candidate_generation`` absent or "frozen"): the
    frozen list is used.  Otherwise a frozen row belongs to the generated set
    iff every one of its protected values is named in the shortlist note
    (case-insensitive, whole token); frozen order is kept.  If the note names
    no complete row the frozen list is used and the source says so.
    """
    if runtime.get("candidate_generation", "frozen") != "untrusted":
        return None
    st = candidate_step(runtime)
    note = next((n for n in notes if st and n["id"] == st["id"]), None)
    text = (note or {}).get("text", "") or ""
    rows = [c for c in runtime["candidates"] if all(_mentions(text, v) for v in c.values())]
    if not rows:
        return list(runtime["candidates"]), "frozen_fallback"
    return rows, f"step:{st['id']}"


def project(case: Case, condition: str, *, drop_sources: set[str] | None = None,
            replace: dict[str, str] | None = None, released: list[dict] | None = None,
            candidates: list[dict] | None = None) -> dict:
    """Build the truth-free context the model sees for ``condition``.

    ``drop_sources`` removes sources (joint / single deletion); ``replace`` maps a
    source id to an alternative condition name ("neutral"/"clean") whose text is
    substituted (structure-preserving replacement).  Candidate order, snapshot and
    task text are invariant across projections.  ``candidates`` (only for
    ``candidate_generation: "untrusted"``) replaces the frozen list with the
    generated choice set (see ``generated_candidates``).
    """
    assert condition in CONDITIONS
    r = case.runtime
    drop, replace = drop_sources or set(), replace or {}
    sources = []
    for s in r["sources"]:
        if s["id"] in drop:
            continue
        cond = replace.get(s["id"], condition)
        sources.append({k: v for k, v in s.items() if k != "text"} | {"text": s["text"][cond]})
    return {
        "id": r["id"],
        "task": "(no user request provided)" if "user" in drop else r["task"],
        "authorization": r["authorization"],
        "tool": r["tool"],
        "contract": {k: v for k, v in r["contract"].items() if k != "explicit_binding"},
        "snapshot": r["snapshot"],
        "candidates": r["candidates"] if candidates is None else candidates,
        "sources": sources,
        "history": r.get("history"),
        "released": list(released or []),
    }


def serialize_action(case: Case, args: dict) -> str:
    """Canonical full-action serialization: fixed field order, no extra keys."""
    ordered = {k: args.get(k) for k in case.fields}
    return json.dumps({"tool": case.runtime["tool"]["name"], "args": ordered}, ensure_ascii=False)


def serialize_candidate(case: Case, cand: dict, free: dict | None = None) -> str:
    args = dict(cand)
    for k in case.fields:
        if k not in args:
            args[k] = (free or {}).get(k, "")
    return serialize_action(case, args)
