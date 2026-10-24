"""P03 serialization-sensitivity probe (proposal §5.4, template P03).

Scores every frozen candidate under the attack and clean contexts with three
serializations of the same action: canonical field order, reversed field order,
and a "loose" JSON style (spaces after separators, numbers quoted).  Reports the
candidate distribution pi, its argmax and the TV distance between serializations,
so that score movements caused by formatting are not mistaken for influence.
Writes reports/serialization-probe-<model>.json.  ~20 forward passes.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.paths import resolve_out
from runner.schema import load_case, project
from runner.prompting import build_action_prompt
from models.adapter import load_adapter


def softmax(lp):
    m = max(lp); z = [math.exp(x - m) for x in lp]; s = sum(z); return [x / s for x in z]


def tv(p, q):
    return 0.5 * sum(abs(a - b) for a, b in zip(p, q))


def ser(case, cand, free, style):
    fields = case.fields if style != "reversed" else list(reversed(case.fields))
    args = {k: (cand.get(k, free.get(k, "")) ) for k in fields}
    if style == "loose":
        args = {k: (str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in args.items()}
        return json.dumps({"tool": case.runtime["tool"]["name"], "args": args}, ensure_ascii=False, indent=None, separators=(", ", ": "))
    return json.dumps({"tool": case.runtime["tool"]["name"], "args": args}, ensure_ascii=False)


def main(spec: str, case_id: str = "P03") -> int:
    ad = load_adapter(spec)
    case = load_case(case_id)
    free = {k: "see note" for k in case.fields if k not in case.protected}
    out = {"model": ad.describe(), "case": case_id, "conditions": {}}
    for cond in ("clean", "attack"):
        msgs = build_action_prompt(project(case, cond))
        res = {}
        for style in ("canonical", "reversed", "loose"):
            conts = [ser(case, c, free, style) for c in case.candidates]
            sc = ad.score(msgs, conts, label=f"serprobe/{cond}/{style}")
            lps = [s.logprob for s in sc]
            res[style] = {"logprobs": lps, "pi": softmax(lps), "argmax": max(range(len(lps)), key=lambda i: lps[i]),
                          "n_tokens": [s.n_tokens for s in sc]}
        base = res["canonical"]["pi"]
        res["tv_vs_canonical"] = {s: tv(base, res[s]["pi"]) for s in ("reversed", "loose")}
        res["argmax_stable"] = len({res[s]["argmax"] for s in ("canonical", "reversed", "loose")}) == 1
        out["conditions"][cond] = res
    out["interpretation"] = ("Formatting artefacts: TV between serializations under the same context is the floor below which "
                             "score movement must not be interpreted as influence; compare with ref_D thresholds in the run report.")
    p = resolve_out(f"reports/serialization-probe-{spec}.json", mkdir=True)
    p.write_text(json.dumps(out, indent=2))
    for cond, r in out["conditions"].items():
        print(cond, {s: round(v, 4) for s, v in r["tv_vs_canonical"].items()}, "argmax stable:", r["argmax_stable"])
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], *(sys.argv[2:3])))
