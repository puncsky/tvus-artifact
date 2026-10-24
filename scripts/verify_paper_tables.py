"""Verify the paper's main results against saved summaries and execution verdicts.

This reads released data only. It does not download weights or invoke a model.
"""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
hosted = lambda prefix: [f"{prefix}-{name}" for name in ["haiku", "openai", "gemini", "opus"]]
RUN_GROUPS = [
    ["dev-qwen14b"], ["h2-dev-qwen14b"], ["dev-llama8b"], ["dev-gemma27b"],
    ["h2-dev-gemma27b"], ["dev-qwen32b-bf16"], ["h2-dev-qwen32b-bf16"], hosted("h3-dev"),
    ["conf-qwen14b"], ["h2-conf-qwen14b"], ["conf-llama8b"], ["conf-gemma27b"],
    ["conf-qwen32b-bf16"], ["h2-conf-qwen32b-bf16"], hosted("h3-conf"),
    ["gen-dev-qwen14b"], hosted("gen-h3"), ["gen-test-qwen32b-bf16"],
]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    source = (ROOT / "paper/workshop/main.tex").read_text()
    end = source.index(r"\label{tab:gap}")
    begin = source.rfind(r"\begin{tabular}", 0, end)
    table = source[begin:source.index(r"\end{tabular}", begin)]
    rows = [line for line in table.splitlines() if re.match(r"(Qwen|Llama|Gemma|4 hosted)", line)]
    require(len(rows) == len(RUN_GROUPS), "Unexpected paper row count")
    count = 0
    for line, group in zip(rows, RUN_GROUPS, strict=True):
        summaries = [json.loads((ROOT / f"reports/{run}/summary.json").read_text())["defenses"] for run in group]
        def pair(defense, key):
            return tuple(sum(summary[defense][key][part] for summary in summaries) for part in ["k", "n"])
        expected = [pair("b0", key) for key in ["clean_correct_automatic", "attack_unauthorized_execution", "attack_attributable"]]
        for defense in ["b1_conservative", "b2_reconstruction", "b4_joint_regen", "b6_regen_only", "b6_chosen_only"]:
            if len(group) > 1 and defense == "b6_chosen_only":
                continue
            conditional = pair(defense, "conditional_on_b0_steered")
            if conditional[1]:
                expected.append(conditional)
            expected.append(pair(defense, "attack_unauthorized_execution"))
        actual = [tuple(map(int, value)) for value in re.findall(r"(\d+)/(\d+)", line)]
        require(actual == expected, f"Paper/summary mismatch: {group}")
        count += len(actual)
    # Independently recount k/n from one verdict per defense and execution.
    checked = 0
    for run in sorted({r for group in RUN_GROUPS for r in group}):
        verdicts = [json.loads(s) for s in (ROOT / f"reports/{run}/rows.jsonl").read_text().splitlines() if s.strip()]
        summary = json.loads((ROOT / f"reports/{run}/summary.json").read_text())["defenses"]
        by_defense = defaultdict(list)
        seen = set()
        for row in verdicts:
            key = (row["case"], row["condition"], row["seed"], row["defense"])
            require(key not in seen, f"Duplicate execution verdict: {run} {key}")
            seen.add(key)
            by_defense[row["defense"]].append(row)
        clean_ok = {(r["case"], r["seed"]) for r in by_defense["b0"] if r["condition"] == "clean" and r["outcome"] == "executed_allowed"}
        steered = {(r["case"], r["seed"]) for r in by_defense["b0"] if r["condition"] == "attack" and not r["legit"] and r["outcome"] == "executed_unauthorized"} & clean_ok
        for defense, items in by_defense.items():
            attack = [r for r in items if r["condition"] == "attack" and not r["legit"]]
            selections = {
                "clean_correct_automatic": ([r for r in items if r["condition"] == "clean"], "executed_allowed"),
                "attack_unauthorized_execution": (attack, "executed_unauthorized"),
                "attack_attributable": ([r for r in attack if (r["case"], r["seed"]) in clean_ok], "executed_unauthorized"),
                "conditional_on_b0_steered": ([r for r in attack if (r["case"], r["seed"]) in steered], "executed_unauthorized"),
            }
            for metric, (subset, outcome) in selections.items():
                expected = summary[defense][metric]
                require((sum(r["outcome"] == outcome for r in subset), len(subset)) == (expected["k"], expected["n"]),
                        f"Verdict/summary mismatch: {run}/{defense}/{metric}")
                checked += 1
    print(f"PASS: {len(rows)} paper rows, {count} fractions, {checked} independently recounted summary metrics")


if __name__ == "__main__":
    main()
