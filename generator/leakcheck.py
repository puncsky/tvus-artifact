"""Neutral-text leak checker (protocol v2 §1.2).

``check_text`` fails a clean/neutral/non-attack text if it contains
  * a candidate value (any protected-field value of any candidate), after normalization
    (case-fold, NFKC, whitespace/punctuation stripped, digit-group separators removed),
    including any >= 6-character substring of an identifier-like value;
  * an ordinal/position/rank word from the frozen ORDINAL_WORDS list or a "#2" / "option 2" pattern;
  * a discriminating attribute: any snapshot attribute value that differs across records, or the
    name of a field the rule function reads.
Alphabetic values and field names are matched as whole token sequences (a trailing plural "s"/"es"
also matches); values containing digits are matched on the separator-free normalized string.
"""
from __future__ import annotations

import re
import unicodedata

ORDINAL_WORDS = frozenset("""
first second third fourth fifth last final top bottom above below former latter previous prior next
earliest latest lowest highest cheapest dearest oldest newest earlier later lower higher upper
primary secondary initial preceding following leftmost rightmost penultimate option row position rank ranked
""".split())
ORDINAL_PATTERNS = [re.compile(p, re.I) for p in (r"#\s*\d", r"\b(?:option|item|row|entry|number|no\.?|line)\s*\d",
                                                  r"\b\d+(?:st|nd|rd|th)\b")]


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text)).casefold()


def squash(text: str) -> str:
    """Normalized form with whitespace, punctuation and digit-group separators removed."""
    return "".join(ch for ch in nfkc(text) if ch.isalnum())


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", nfkc(text))


def _has_seq(toks: list[str], seq: list[str]) -> bool:
    if not seq:
        return False
    n = len(seq)
    for i in range(len(toks) - n + 1):
        win = toks[i:i + n]
        if win[:-1] == seq[:-1] and win[-1] in (seq[-1], seq[-1] + "s", seq[-1] + "es"):
            return True
    return False


def value_hit(value, text: str) -> bool:
    sv = str(value)
    if any(ch.isdigit() for ch in sv):
        nv, nt = squash(sv), squash(text)
        if not nv:
            return False
        if sv.replace(".", "").replace(",", "").isdigit():  # pure number: whole-number match only
            nums = {squash(m) for m in re.findall(r"\d[\d,.\s]*\d|\d", nfkc(text))}
            return nv in nums or nv.lstrip("0") in {x.lstrip("0") for x in nums}
        if nv in nt:
            return True
        return len(nv) >= 6 and any(nv[i:i + 6] in nt for i in range(len(nv) - 5))
    return _has_seq(tokens(text), tokens(sv))


def discriminating_values(runtime: dict) -> set:
    by_key: dict[str, set] = {}
    for rec in runtime["snapshot"]["records"]:
        for k, v in rec.items():
            if k == "type" or isinstance(v, bool):
                continue
            by_key.setdefault(k, set()).add(str(v))
    return {v for vals in by_key.values() if len(vals) > 1 for v in vals}


def check_text(text: str, runtime: dict, read_fields: list[str]) -> list[str]:
    problems = []
    cand_vals = {str(v) for c in runtime["candidates"] for v in c.values()}
    for v in sorted(cand_vals):
        if value_hit(v, text):
            problems.append(f"candidate value {v!r}")
    toks = tokens(text)
    for w in sorted(set(toks) & ORDINAL_WORDS):
        problems.append(f"ordinal word {w!r}")
    for pat in ORDINAL_PATTERNS:
        if pat.search(text):
            problems.append(f"ordinal pattern {pat.pattern!r}")
    for v in sorted(discriminating_values(runtime) - cand_vals):
        if value_hit(v, text):
            problems.append(f"discriminating attribute {v!r}")
    for f in sorted(set(read_fields)):
        if _has_seq(toks, tokens(f.replace("_", " "))) or squash(f) in squash(text).split():
            problems.append(f"rule field name {f!r}")
    return problems


def check_case(runtime: dict, read_fields: list[str]) -> list[str]:
    """Check every clean and neutral text, and every non-writable attack text."""
    writable = set(runtime["writable"]["sources"])
    out = []
    for s in runtime["sources"]:
        conds = ("clean", "neutral") if s["id"] in writable else ("clean", "neutral", "attack")
        for cond in conds:
            for p in check_text(s["text"][cond], runtime, read_fields):
                out.append(f"{s['id']}.{cond}: {p}")
    return out


VALUE_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-.:/][A-Za-z0-9]+)*")


def untrusted_values(text: str, runtime: dict) -> list[str]:
    """Value-like tokens (containing a digit) in ``text`` that are not trusted snapshot/candidate values
    (protocol v2 §1.1 (5): the attack shifts the choice, never introduces a value)."""
    trusted = set()
    for rec in runtime["snapshot"]["records"] + runtime["candidates"]:
        for v in rec.values():
            if not isinstance(v, bool):
                trusted.add(squash(v))
    return [tok for tok in VALUE_TOKEN.findall(text) if any(ch.isdigit() for ch in tok) and squash(tok) not in trusted]


# ---------------------------------------------------------------------------
# planted-leak self-test
# ---------------------------------------------------------------------------

PLANTED_ORDINALS = ("second", "2nd", "last")
KIND_PREFIX = {"candidate": "candidate value", "ordinal": "ordinal", "attribute": "discriminating attribute"}


def _load_corpus(root):
    import json
    man = json.loads((root / "manifest.json").read_text())
    for t in man["tasks"]:
        d = root / t["family"] / t["id"]
        yield t, json.loads((d / "runtime.json").read_text()), json.loads((d / "evaluator.json").read_text())


def selftest(cases: str) -> int:
    """Prove the checker rejects planted leaks and passes the clean corpus.

    For every task: (a) the neutral text plus one candidate value (the attack target's or a non-reference
    candidate's id field), (b) the neutral text plus each of "second", "2nd", "last" in a sentence, and
    (c) the neutral text plus a discriminating, non-candidate snapshot attribute must each be rejected for that reason;
    the unmodified corpus (check_case) must pass; and every neutral template of every channel, rendered
    with its domain's full fact list, must pass against every task of that domain.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from generator import neutral
    from generator.domains import DOMAINS, GENERIC_FACTS, SIGN_NAMES
    from generator.rules import FAMILIES

    root = Path(cases).resolve()
    c = {k: [0, 0] for k in ("candidate", "ordinal", "attribute", "corpus_tasks", "corpus_texts", "templates")}
    fails = []
    no_attr = 0
    tasks = list(_load_corpus(root))
    for t, rt, ev in tasks:
        reads = FAMILIES[ev["rule"]["family"]].reads(ev["rule"]["params"])
        base = rt["sources"][0]["text"]["neutral"]
        idf = ev["rule"]["params"]["id_field"]
        cand = (ev.get("attack_target") or rt["candidates"][-1])[idf]
        planted = {"candidate": [f"{base}\nPlease use {cand}."],
                   "ordinal": [f"{base}\nPlease go with the {w} one." for w in PLANTED_ORDINALS]}
        attrs = sorted(discriminating_values(rt) - {str(v) for cd in rt["candidates"] for v in cd.values()})
        if attrs:
            planted["attribute"] = [f"{base}\nThis concerns {attrs[len(attrs) // 2]}."]
        else:
            no_attr += 1
        for kind, texts in planted.items():
            for txt in texts:
                c[kind][1] += 1
                if any(p.startswith(KIND_PREFIX[kind]) for p in check_text(txt, rt, reads)):
                    c[kind][0] += 1
                else:
                    fails.append(f"{t['id']}: planted {kind} not rejected: {txt[-60:]!r}")
        probs = check_case(rt, reads)
        c["corpus_tasks"][1] += 1
        c["corpus_tasks"][0] += not probs
        n_texts = sum(2 if s["id"] in rt["writable"]["sources"] else 3 for s in rt["sources"])
        c["corpus_texts"][1] += n_texts
        c["corpus_texts"][0] += n_texts - len({p.split(":", 1)[0] for p in probs})
        fails += [f"{t['id']}: corpus {p}" for p in probs]
    # every template x every domain's full fact list x every task of that domain
    by_dom: dict[str, list] = {}
    for t, rt, ev in tasks:
        by_dom.setdefault(t["domain"], []).append((t, rt, ev))
    for dom_name, items in sorted(by_dom.items()):
        dom = DOMAINS[dom_name]
        facts = [f[1] for f in dom["facts"] + GENERIC_FACTS]
        for k, tid in enumerate(neutral.template_ids()):
            for j, org in enumerate(dom["orgs"]):
                name = SIGN_NAMES[(k + j) % len(SIGN_NAMES)]
                txt = neutral.render(tid, facts, name, org)
                for t, rt, ev in items:
                    c["templates"][1] += 1
                    probs = check_text(txt, rt, FAMILIES[ev["rule"]["family"]].reads(ev["rule"]["params"]))
                    if probs:
                        fails.append(f"{t['id']}: template {tid} ({org}/{name}): {probs}")
                    else:
                        c["templates"][0] += 1
    per_chan = {ch: len(neutral.template_ids(ch)) for ch in neutral.CHANNELS}
    print(f"corpus: {root} ({len(tasks)} tasks)")
    print(f"templates per channel: {per_chan}")
    print(f"(a) planted candidate value rejected: {c['candidate'][0]}/{c['candidate'][1]}")
    print(f"(b) planted ordinal word {'/'.join(PLANTED_ORDINALS)} rejected: {c['ordinal'][0]}/{c['ordinal'][1]}")
    print(f"(c) planted discriminating attribute rejected: {c['attribute'][0]}/{c['attribute'][1]}"
          f" ({no_attr} tasks have no non-candidate discriminating value)")
    print(f"clean corpus passes: {c['corpus_tasks'][0]}/{c['corpus_tasks'][1]} tasks, "
          f"{c['corpus_texts'][0]}/{c['corpus_texts'][1]} clean/neutral/non-writable texts")
    print(f"template sweep passes: {c['templates'][0]}/{c['templates'][1]} renders "
          f"(every template x domain org, full domain fact list, every task of that domain)")
    for f in fails[:30]:
        print("  -", f)
    print("SELFTEST", "PASS" if not fails else f"FAIL ({len(fails)} problems)")
    return 1 if fails else 0


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="Neutral-text leak checker (§1.2)")
    ap.add_argument("--selftest", action="store_true", help="planted-leak self-test over a generated corpus")
    ap.add_argument("--cases", default="generated/cases")
    a = ap.parse_args()
    if not a.selftest:
        ap.error("use --selftest (the checker itself is a library used by make.py / selfcheck.py)")
    sys.exit(selftest(a.cases))
