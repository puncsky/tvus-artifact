"""Assemble the m8 pilot report: cross-harness × cross-family table, confirmation sets, and the
reconstruction failure-boundary suite.  Reads reports/<run>/summary.json (+ rows.jsonl for the F-suite)
and writes reports/pilot-h2h3/README.md.  Missing runs are listed, never silently dropped.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.paths import resolve_out, CATEGORY

RUNS = [  # (run id, family, harness, suite, run specs)
    ("dev-qwen14b", "Qwen2.5-14B", "H1", "dev", "0/11/23"),
    ("h2-dev-qwen14b", "Qwen2.5-14B", "H2", "dev", "0"),
    ("dev-llama8b", "Llama-3.1-8B", "H1", "dev", "0/11/23"),
    ("dev-gemma27b", "Gemma-3-27B", "H1", "dev", "0/11"),
    ("h2-dev-gemma27b", "Gemma-3-27B", "H2", "dev", "0"),
    ("conf-qwen14b", "Qwen2.5-14B", "H1", "conf", "0/11/23"),
    ("h2-conf-qwen14b", "Qwen2.5-14B", "H2", "conf", "0"),
    ("conf-llama8b", "Llama-3.1-8B", "H1", "conf", "0/11/23"),
    ("conf-gemma27b", "Gemma-3-27B", "H1", "conf", "0/11"),
    ("h3-dev-haiku", "Claude Haiku 4.5 (hosted API)", "H3", "dev", "0"),
    ("h3-conf-haiku", "Claude Haiku 4.5 (hosted API)", "H3", "conf", "0"),
    ("h3-dev-openai", "GPT-5.6-sol (hosted API)", "H3", "dev", "0"),
    ("h3-conf-openai", "GPT-5.6-sol (hosted API)", "H3", "conf", "0"),
    ("h3-dev-gemini", "Gemini 3.1 Pro preview (hosted API)", "H3", "dev", "0"),
    ("h3-conf-gemini", "Gemini 3.1 Pro preview (hosted API)", "H3", "conf", "0"),
    ("h3-dev-opus", "Claude Opus 5.5 (hosted API)", "H3", "dev", "0"),
    ("h3-conf-opus", "Claude Opus 5.5 (hosted API)", "H3", "conf", "0"),
    ("gen-dev-qwen14b", "Qwen2.5-14B", "H1", "generated 48-slice", "0"),
    ("gen-h3-haiku", "Claude Haiku 4.5 (hosted API)", "H3", "generated 48-slice", "0"),
    ("gen-h3-openai", "GPT-5.6-sol (hosted API)", "H3", "generated 48-slice", "0"),
    ("gen-h3-gemini", "Gemini 3.1 Pro preview (hosted API)", "H3", "generated 48-slice", "0"),
    ("gen-h3-opus", "Claude Opus 5.5 (hosted API)", "H3", "generated 48-slice", "0"),
]
KEYS = [("b0", "B0 ordinary agent"), ("b1_conservative", "B1 fail-closed provenance"), ("b2_reconstruction", "B2 reconstruction"),
        ("b4_joint_regen", "in-place joint deletion + regen"), ("b6_regen_only", "h0 regeneration only"),
        ("b5_enhanced", "B5 enhanced attribution"), ("b6_reference", "B6 reference"), ("b6_chosen_only", "chosen-action ablation")]


def _load(run):
    p = CATEGORY / "reports" / run / "summary.json"
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    out = resolve_out("reports/pilot-h2h3", mkdir=True); out.mkdir(parents=True, exist_ok=True)
    L = ["# m8 pilot report — generality across harnesses and families (development + confirmation + failure boundary)", "",
         "H1 = single-shot structured output; H2 = ReAct tool loop (tool results as transcript messages; closure = full replay; in-place = edit the original transcript). "
         "4-bit MLX models on one Mac. Pilot run specs per `protocol-v2.md` addenda (H2 greedy only). 'attrib.' = attack executions whose same-seed clean B0 execution was correct. "
         "Thresholds calibrated per (family, harness) on that run's clean+neutral executions; confirmation sets use the frozen development thresholds.", ""]
    missing = []
    L += ["## 1. Development and confirmation templates", "",
          "| run | family | harness | suite | seeds | B0 clean | " + " | ".join(f"{lbl}: attack (attrib.) / legit blocked+wrong / ×B0 passes" for _, lbl in KEYS[1:]) + " |",
          "|---|---|---|---|---|---|" + "---|" * (len(KEYS) - 1)]
    for run, fam, h, suite, seeds in RUNS:
        s = _load(run)
        if not s:
            missing.append(run); continue
        d = s["defenses"]
        b0 = d["b0"]
        cells = []
        for k, _ in KEYS[1:]:
            x = d[k]; a = x["attack_unauthorized_execution"]; t = x["attack_attributable"]
            legit = x["legitimate_falsely_blocked"]["k"] + x["legitimate_wrong_effect"]["k"]
            cells.append(f"{a['k']}/{a['n']} ({t['k']}/{t['n']}) / {legit}/{x['legitimate_falsely_blocked']['n']} / {x['compute']['mean_ratio_passes']:.1f}×")
        a0, t0 = b0["attack_unauthorized_execution"], b0["attack_attributable"]
        L.append(f"| {run} | {fam} | {h} | {suite} | {seeds} | {b0['clean_correct_automatic']['k']}/{b0['clean_correct_automatic']['n']} (B0 attack {a0['k']}/{a0['n']}, attrib. {t0['k']}/{t0['n']}, {a0['templates_with_any']} templates) | " + " | ".join(cells) + " |")
    if missing:
        L += ["", "Missing runs (not yet executed or failed): " + ", ".join(missing) + "."]
    # F-suite
    L += ["", "## 2. Reconstruction failure-boundary suite (F01–F08)", "",
          "Expected behaviour is the fixture author's prediction (`evaluator.expected_reconstruction_behaviour`); outcomes are the sink results under the attack condition.", "",
          "| template | boundary (assumption) | expected | run | B0 | B2 reconstruction | h0 regeneration gate | B0 clean |", "|---|---|---|---|---|---|---|---|"]
    from runner import schema
    schema.CASES_DIR = CATEGORY / "failure-boundary" / "cases"
    from runner.schema import load_case
    for run in ("fb-h1-qwen14b", "fb-h2-qwen14b"):
        p = CATEGORY / "reports" / run / "rows.jsonl"
        if not p.exists():
            missing.append(run); continue
        rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
        for t in sorted({r["case"] for r in rows}):
            c = load_case(t); ev = c.evaluator
            def oc(d, cond="attack"):
                xs = [x["outcome"] for x in rows if x["case"] == t and x["condition"] == cond and x["defense"] == d]
                short = {"executed_allowed": "allowed", "executed_unauthorized": "UNAUTH", "blocked": "blocked", "unknown": "UNKNOWN", "parse_failure": "parse-fail"}
                return "/".join(short.get(x, x) for x in xs)
            L.append(f"| {t} | {ev.get('boundary', ev.get('hypothesis', ''))[:90]} | {ev.get('expected_reconstruction_behaviour')} | {run} | {oc('b0')} | {oc('b2_reconstruction')} | {oc('b6_regen_only')} | {oc('b0', 'clean')} |")
    L += ["", "Reading: a boundary is *confirmed* when B2 executes an unauthorized or wrong tuple (or fails) while the task is well-posed; it is *not reached* when B0 itself was not steered (nothing to recover from) or the current runner does not implement the fixture's field (F01 `candidate_generation`, F04 `h0_after_step`; see `failure-boundary/README.md`).", ""]
    L += ["## 3. Notes", "",
          "- H2 pass ratios are lower than H1 because the ordinary agent itself spends more passes (tool turns); absolute costs are in the per-run tables.",
          "- Gemma-3's chat template requires strict role alternation; H2 prompts for Gemma have adjacent same-role turns merged (`protocol-v2.md` addendum 2).",
          "- Capability-failure templates per run are listed in each `reports/<run>/table.md`.",
          "- H3 (hosted native tool use: `runner/harness_claude.py`, `harness_openai.py`, `harness_gemini.py`) ran Claude Haiku 4.5, Claude Opus 5.5, GPT-5.6-sol and Gemini 3.1 Pro preview at provider-default sampling (one execution per template; no `temperature` override). Score-based gates are not applicable on the API (no log-probabilities) and are reported as UNKNOWN/not applicable; only B0, B2, in-place and closure regeneration gates are measured. Spend per run is in `runs/<run>/spend.json`; hosted total ≈ $68 of the $300 API cap.",
          "- Generated 48-slice: `generated/pilot-slice-dev-seed11.txt` (48 generated tasks, 36 with an attack condition, 12 neutral; one execution per task, seed 0). Qwen2.5-14B H1 is steered on 9/36 attack executions spread over 9 templates (`filter_earliest` 5/6); no hosted agent is steered on the slice."]
    (out / "README.md").write_text("\n".join(L) + "\n")
    print("wrote", out / "README.md", "missing:", missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
