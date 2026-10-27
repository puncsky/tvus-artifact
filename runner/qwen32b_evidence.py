"""Qwen2.5-32B evidence recovery and replication (research ``.pm/w1/m1``).

One role map for the six workshop-paper matrices, plus the bookkeeping around them:

  inventory          historical evidence inventory -> reports/qwen32b-evidence/inventory.json (no model calls)
  plan               explicit frozen schedule -> reports/qwen32b-evidence/run-plan.json
  freeze             record protocol + plan hashes once -> reports/qwen32b-evidence/freeze.json
  argv               W3_CASES_DIR + experiment.py arguments of a role, from the frozen plan (used by the wrapper)
  freeze-thresholds  record the secondary threshold file's hash once -> threshold-freeze.jsonl
  projection         time/storage projection from the probe -> projection.json
  probe-compare      readiness probe vs the historical October rows -> probe-compare.json
  audit              coverage / provenance audit of a run dir against its frozen schedule
  checksum           write runs/<id>/SHA256SUMS over every file of the run
  backup             copy a run to a second location and verify every SHA-256 there

Historical report directories are read, never written. New runs use their own ids (``ROLES[*]["run_id"]``).

Usage:
  envs/torch-cuda/bin/python -B runner/qwen32b_evidence.py inventory
  envs/torch-cuda/bin/python -B runner/qwen32b_evidence.py audit --role gen-test
  envs/torch-cuda/bin/python -B runner/qwen32b_evidence.py backup --role gen-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.paths import CATEGORY, resolve_out  # noqa: E402
from runner.recording import checkpoint, now, read_jsonl, sha256_file, verify_sums, write_sums  # noqa: E402

MODEL = {"key": "qwen32b-bf16", "hf_repo": "Qwen/Qwen2.5-32B-Instruct",
         "revision": "5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd", "dtype": "bf16", "batch_candidates": False}
REPLICATION = "rep20261025"           # replication generation tag; frozen in reports/qwen32b-evidence/protocol.md
OUT = "reports/qwen32b-evidence"
H1_THR, H2_THR = "reports/dev-qwen32b-bf16/thresholds.json", "reports/h2-dev-qwen32b-bf16/thresholds.json"
CONDITIONS = ["clean", "neutral", "attack"]
SPECS = {0: 0.0, 11: 0.7, 23: 0.7}    # runner/experiment.py::RUN_SPECS

# role -> fixtures, harness, seeds and the historical frozen thresholds used for the primary comparison
ROLES = {
    "dev":      {"cases_dir": "cases",                   "harness": "h1", "seeds": [0, 11, 23], "thresholds": H1_THR, "n_cases": 24},
    "conf":     {"cases_dir": "confirmation/cases",      "harness": "h1", "seeds": [0, 11, 23], "thresholds": H1_THR, "n_cases": 8},
    "gen-test": {"cases_dir": "generated/cases",         "harness": "h1", "seeds": [0, 11, 23], "thresholds": H1_THR, "n_cases": 147,
                 "case_list": "generated/test-split.txt"},
    "h2-dev":   {"cases_dir": "cases",                   "harness": "h2", "seeds": [0],         "thresholds": H2_THR, "n_cases": 24},
    "h2-conf":  {"cases_dir": "confirmation/cases",      "harness": "h2", "seeds": [0],         "thresholds": H2_THR, "n_cases": 8},
    "fb-h1":    {"cases_dir": "failure-boundary/cases",  "harness": "h1", "seeds": [0],         "thresholds": H1_THR, "n_cases": 8},
}
for _r, _d in ROLES.items():
    _d["historical"] = f"{_r}-qwen32b-bf16"
    _d["run_id"] = f"{REPLICATION}-{_r}-qwen32b-bf16"
    _d["scheduled"] = _d["n_cases"] * len(CONDITIONS) * len(_d["seeds"])
HISTORICAL_RAW = ["manifest.json", "executions.jsonl", "ledger.json"]   # what every other matrix in v1.0.1 ships


def role_case_ids(role: str) -> list[str]:
    """Scheduled case ids of a role, in experiment.py's load order (sorted family/id directories)."""
    d = ROLES[role]
    ids = [p.name for p in sorted((CATEGORY / d["cases_dir"]).glob("*/*")) if (p / "runtime.json").exists()]
    if d.get("case_list"):
        keep = set((CATEGORY / d["case_list"]).read_text().split())
        ids = [i for i in ids if i in keep]
    return ids


def scheduled_keys(role: str) -> list[tuple[str, str, int]]:
    return [(c, cond, s) for c in role_case_ids(role) for cond in CONDITIONS for s in ROLES[role]["seeds"]]


def frac(d: dict) -> str:
    return f"{d['k']}/{d['n']}"


def fixture_hashes(role: str) -> dict[str, dict[str, str]]:
    """sha256 of the exact runtime (model-visible) and evaluator (private truth) files per scheduled case."""
    d, ids = ROLES[role], set(role_case_ids(role))
    out = {}
    for p in sorted((CATEGORY / d["cases_dir"]).glob("*/*")):
        if p.name in ids:
            out[p.name] = {"runtime.json": sha256_file(p / "runtime.json"), "evaluator.json": sha256_file(p / "evaluator.json")}
    return out


# ---------------------------------------------------------------------------
# inventory (t001)
# ---------------------------------------------------------------------------

def _historical_counts(rep: Path, sched: set) -> dict:
    s = json.loads((rep / "summary.json").read_text())
    rows = read_jsonl(rep / "rows.jsonl")
    keys = {(r["case"], r["condition"], r["seed"]) for r in rows}
    D = s["defenses"]
    return {
        "summary_n_executions": s["n_executions"], "summary_n_scheduled": s["n_scheduled"],
        "summary_missing_coverage": len(s["missing_coverage"]),
        "rows": len(rows), "row_execution_keys": len(keys), "defenses": len(D),
        "rows_per_execution": len(rows) / max(1, len(keys)),
        "threat_templates": len(s["threat_templates"]), "legit_templates": len(s["legit_templates"]),
        "b0_clean_correct": frac(D["b0"]["clean_correct_automatic"]),
        "b0_attack_unauthorized": frac(D["b0"]["attack_unauthorized_execution"]),
        "b0_attack_attributable": frac(D["b0"]["attack_attributable"]),
        "b2_attack_unauthorized": frac(D["b2_reconstruction"]["attack_unauthorized_execution"]),
        "regen_only_attack_unauthorized": frac(D["b6_regen_only"]["attack_unauthorized_execution"]),
        "b6_reference_attack_unauthorized": frac(D["b6_reference"]["attack_unauthorized_execution"]),
        "conditional_on_b0_steered": {k: frac(D[k]["conditional_on_b0_steered"]) for k in
                                      ("b2_reconstruction", "b6_regen_only", "b6_reference", "b6_chosen_only")},
        "steered_templates": D["b0"]["conditional_on_b0_steered"]["templates"],
        "thresholds_in_summary": dict(s["thresholds"]),
        "model": {k: v for k, v in s["model"].items() if k != "model_path"},
        "row_keys_match_schedule": keys == sched,
    }


def inventory(release_json: Path | None, searches: list[dict]) -> dict:
    rel = json.loads(release_json.read_text()) if release_json and release_json.exists() else None
    matrices = []
    for role, d in ROLES.items():
        rep = CATEGORY / "reports" / d["historical"]
        c = _historical_counts(rep, set(scheduled_keys(role)))
        thr_file = CATEGORY / d["thresholds"]
        thr = json.loads(thr_file.read_text())
        raw_dir = CATEGORY / "runs" / d["historical"]
        matrices.append({
            "role": role, "historical_run_id": d["historical"], "harness": d["harness"], "fixtures": d["cases_dir"],
            "case_list": d.get("case_list"), "seeds": d["seeds"], "temperatures": [SPECS[s] for s in d["seeds"]],
            "scheduled_executions": d["scheduled"], "scheduled_by_condition": {k: d["n_cases"] * len(d["seeds"]) for k in CONDITIONS},
            "historical_report_files": {p.name: sha256_file(p) for p in sorted(rep.iterdir()) if p.is_file()},
            "historical_dossiers": len(list((rep / "dossiers").glob("*.md"))),
            "derived_counts": c,
            "summary_counts_agree": (c["summary_n_executions"] == c["summary_n_scheduled"] == d["scheduled"] == c["row_execution_keys"]
                                     and c["summary_missing_coverage"] == 0 and c["row_keys_match_schedule"]
                                     and c["rows"] == d["scheduled"] * c["defenses"]),
            "thresholds": {"file": d["thresholds"], "sha256": sha256_file(thr_file),
                           "matches_summary": all(abs(thr[k] - c["thresholds_in_summary"][k]) < 1e-12 for k in thr if not k.startswith("_"))},
            "required_raw_files": HISTORICAL_RAW,
            "raw_files_present_locally": [f for f in HISTORICAL_RAW if (raw_dir / f).exists()],
            "public_release_raw_files": next((x["raw_files"] for x in (rel or {}).get("run_coverage", []) if x["run"] == d["historical"]), None),
            "public_release_lists_missing": (d["historical"] in (rel or {}).get("missing_raw_runs", [])) if rel else None,
            "original_manifest": "absent (code, fixture and start-time bindings of the original execution are unrecoverable)",
            "model_binding_from_summary": {k: c["model"].get(k) for k in ("hf_repo", "revision", "dtype", "batch_candidates",
                                                                       "attn_implementation", "torch", "transformers", "gpu")},
            "fixture_hashes_current": fixture_hashes(role),
        })
    dates = {"dev": "2026-10-08T16:37:25-07:00", "conf": "2026-10-08T16:37:25-07:00", "fb-h1": "2026-10-08T16:37:25-07:00",
             "h2-dev": "2026-10-09T00:51:21-07:00", "h2-conf": "2026-10-09T00:51:21-07:00", "gen-test": "2026-10-10T16:21:04-07:00"}
    commits = {"dev": "4254c6479", "conf": "4254c6479", "fb-h1": "4254c6479", "h2-dev": "aab5e7b08", "h2-conf": "aab5e7b08", "gen-test": "dbc839719"}
    for m in matrices:
        m["original_collection_time"] = {
            "exact": None,
            "derived_report_first_commit": {"commit": commits[m["role"]], "date": dates[m["role"]]},
            "window": "2026-10-08 to 2026-10-10 (DGX Spark zgx-aa67; .pm/w3/m10/t004 log 2026-10-10)",
        }
        m["disposition"] = ("reanalyze-original" if m["raw_files_present_locally"] == HISTORICAL_RAW
                            else "fresh-replication-required")
    return {
        "generated": now(),
        "task": "research .pm/w1/m1/t001", "model": MODEL,
        "model_calls": 0,
        "searches": searches,
        "public_release": {"file": str(release_json.relative_to(CATEGORY)) if release_json else None,
                           "sha256": sha256_file(release_json) if release_json and release_json.exists() else None,
                           "version": (rel or {}).get("version"), "missing_raw_runs": (rel or {}).get("missing_raw_runs")},
        "code_and_fixture_history": ("git: runner/, models/, fixtures (cases/, confirmation/, failure-boundary/, generated/cases, "
                                     "generated/test-split.txt) unchanged since 9ecac5d73 (2026-10-06), i.e. before the original runs; "
                                     "later commits touched only configs/env-cuda.json, configs/models.json, models/verify_adapter.py, "
                                     "run/artifact/audit scripts and protocol text. Uncommitted edits on the original host cannot be excluded."),
        "matrices": matrices,
        "totals": {"scheduled_executions": sum(d["scheduled"] for d in ROLES.values()),
                   "authenticated_original_executions": 0,
                   "matrices_needing_replication": [m["role"] for m in matrices if m["disposition"] != "reanalyze-original"]},
    }


# ---------------------------------------------------------------------------
# plan / freeze / argv (t002), projection / probe-compare (t003), audit / checksum / backup (t004-t006, t010)
# ---------------------------------------------------------------------------

PROBE = {"role": "probe", "run_id": f"{REPLICATION}-probe-qwen32b-bf16", "cases_dir": "cases", "harness": "h1",
         "seeds": [0], "cases": ["H02", "P01", "S01"], "evidence": False}


def plan() -> dict:
    """The frozen, explicit schedule (run-plan.json), derived from ROLES; ``experiment.py --plan`` enforces it."""
    runs = [{**PROBE, "model_spec": MODEL["key"], "conditions": CONDITIONS,
             "scheduled": len(PROBE["cases"]) * len(CONDITIONS) * len(PROBE["seeds"]),
             "cases": [c for c in role_case_ids("dev") if c in PROBE["cases"]]}]
    for role, d in ROLES.items():
        thr = CATEGORY / d["thresholds"]
        runs.append({"role": role, "run_id": d["run_id"], "historical_run_id": d["historical"], "evidence": True,
                     "label": "replication", "model_spec": MODEL["key"], "harness": d["harness"], "cases_dir": d["cases_dir"],
                     "case_list": d.get("case_list"), "cases": role_case_ids(role), "conditions": CONDITIONS, "seeds": d["seeds"],
                     "temperatures": [SPECS[s] for s in d["seeds"]], "scheduled": d["scheduled"],
                     "primary_thresholds": {"file": d["thresholds"], "sha256": sha256_file(thr)},
                     "secondary_thresholds": f"reports/{REPLICATION}-{'h2-dev' if d['harness'] == 'h2' else 'dev'}-qwen32b-bf16-secthr/thresholds.json"})
    return {"plan_id": f"{REPLICATION}-qwen32b", "model": MODEL, "protocol": f"{OUT}/protocol.md",
            "protocol_sha256": sha256_file(CATEGORY / OUT / "protocol.md"), "order": [r["role"] for r in runs], "runs": runs,
            "total_evidence_executions": sum(r["scheduled"] for r in runs if r["evidence"])}


def freeze() -> dict:
    """Record protocol + plan hashes once, before the first model call; refuse to rewrite a different freeze."""
    path = CATEGORY / OUT / "freeze.json"
    rec = {"protocol": f"{OUT}/protocol.md", "protocol_sha256": sha256_file(CATEGORY / OUT / "protocol.md"),
           "plan": f"{OUT}/run-plan.json", "plan_sha256": sha256_file(CATEGORY / OUT / "run-plan.json")}
    if path.exists():
        old = json.loads(path.read_text())
        if {k: old[k] for k in rec} != rec:
            raise SystemExit(f"freeze.json already records different hashes ({old['frozen_at']}); add a protocol addendum instead")
        return old
    rec["frozen_at"] = now()
    rec["model_calls_before_freeze"] = 0
    path.write_text(json.dumps(rec, indent=2) + "\n")
    return rec


def plan_entry(role: str) -> dict:
    pl = json.loads((CATEGORY / OUT / "run-plan.json").read_text())
    return next(r for r in pl["runs"] if r["role"] == role)


def argv(role: str) -> str:
    """Shell words for scripts/run_qwen32b_evidence.sh: W3_CASES_DIR=<dir> then experiment.py arguments from the plan."""
    r = plan_entry(role)
    words = [f"W3_CASES_DIR={CATEGORY / r['cases_dir']}", "--model", r["model_spec"], "--run-id", r["run_id"],
             "--harness", r["harness"], "--seeds", *map(str, r["seeds"]), "--cases", *r["cases"]]
    return " ".join(words)


def freeze_thresholds(role: str) -> dict:
    """Append the secondary (fresh replication-dev) threshold file's hash to threshold-freeze.jsonl, once."""
    run_id = ROLES[role]["run_id"]
    f = CATEGORY / "reports" / f"{run_id}-secthr" / "thresholds.json"
    log = CATEGORY / OUT / "threshold-freeze.jsonl"
    rec = {"harness": ROLES[role]["harness"], "calibrated_on": run_id, "file": str(f.relative_to(CATEGORY)), "sha256": sha256_file(f),
           "label": "secondary (fresh replication-development calibration; never the primary comparison)"}
    for old in read_jsonl(log):
        if old["file"] == rec["file"]:
            if old["sha256"] != rec["sha256"]:
                raise SystemExit(f"{rec['file']} changed after its freeze at {old['frozen_at']}")
            return old
    rec["frozen_at"] = now()
    rec["analyzed_before_freeze"] = [r for r in ROLES if r != role and ROLES[r]["harness"] == ROLES[role]["harness"]
                                     and (CATEGORY / "reports" / ROLES[r]["run_id"]).exists()]
    with open(log, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def _historical_exec_seconds(role: str) -> float:
    """Lower-bound mean wall seconds per historical execution (agent + LOO + B6 + B2 ledger slices of rows.jsonl)."""
    ex: dict = {}
    for r in read_jsonl(CATEGORY / "reports" / ROLES[role]["historical"] / "rows.jsonl"):
        ex.setdefault((r["case"], r["condition"], r["seed"]), {})[r["defense"]] = r["cost"]
    tot = [v["b0"]["agent"]["wall_seconds"] + sum(v[k]["defense"]["wall_seconds"] for k in ("b4_loo", "b6_reference", "b2_reconstruction"))
           for v in ex.values()]
    return sum(tot) / len(tot)


def projection() -> dict:
    """Time/storage projection for the uncovered matrices from the probe (t003); owned host => USD 0."""
    probe = CATEGORY / "runs" / PROBE["run_id"]
    recs = read_jsonl(probe / "executions.jsonl")
    old_probe = json.loads((CATEGORY / "reports" / "h100-projection.json").read_text())["families"]["qwen32b-bf16"]["sec_per_execution"]
    new_probe = sum(r["wall_seconds"] for r in recs) / len(recs)
    ratio = new_probe / old_probe
    bytes_per_exec = sum(p.stat().st_size for p in probe.rglob("*") if p.is_file()) / len(recs)
    roles = {}
    for role, d in ROLES.items():
        lb = _historical_exec_seconds(role)
        roles[role] = {"scheduled": d["scheduled"], "historical_lower_bound_s_per_exec": lb,
                       "projected_hours": d["scheduled"] * lb * ratio * 1.15 / 3600}   # +15 % for labels outside the lower bound
    hours = sum(r["projected_hours"] for r in roles.values())
    gb = bytes_per_exec * sum(d["scheduled"] for d in ROLES.values()) / 1e9
    return {"probe_run": PROBE["run_id"], "probe_executions": len(recs), "probe_s_per_exec": new_probe,
            "historical_probe_s_per_exec": old_probe, "speed_ratio_new_over_historical": ratio, "roles": roles,
            "projected_collection_hours": hours, "probe_bytes_per_exec": bytes_per_exec,
            "projected_run_storage_gb": gb, "projected_storage_with_checkpoint_and_backup_gb": 3 * gb,
            "paid": False, "projected_usd": 0.0, "gpu_cap_usd": 450.0, "gpu_spent_usd": 0.0,
            "note": "owned DGX Spark spark-71a4 (author-approved 2026-10-25); hours scale the historical per-role lower bounds by the probe speed ratio"}


def probe_compare() -> dict:
    """Readiness: probe executions vs the historical dev rows for the same (case, condition, seed 0) keys."""
    from runner.analyze import signals, THRESHOLD_STATS
    from runner.schema import load_case
    rows = {}
    for r in read_jsonl(CATEGORY / "reports" / "dev-qwen32b-bf16" / "rows.jsonl"):
        if r["case"] in PROBE["cases"] and r["seed"] == 0 and r["defense"] in ("b0", "b2_reconstruction"):
            rows[(r["case"], r["condition"], r["defense"])] = r
    out = []
    for rec in read_jsonl(CATEGORY / "runs" / PROBE["run_id"] / "executions.jsonl"):
        sig = signals(rec, load_case(rec["case"]))
        h0, h2 = rows[(rec["case"], rec["condition"], "b0")], rows[(rec["case"], rec["condition"], "b2_reconstruction")]
        out.append({"case": rec["case"], "condition": rec["condition"],
                    "b0_candidate": [h0["b0_candidate"], sig["i0"]], "b0_protected_same": h0["protected"] == rec["b0"]["protected"],
                    "b2_protected_same": h2["protected"] == rec["reconstruction"]["protected"],
                    "max_abs_stat_diff": max(abs(h0["stats"][k] - sig[k]) for k in THRESHOLD_STATS),
                    "stat_diffs": {k: sig[k] - h0["stats"][k] for k in THRESHOLD_STATS}})
    return {"compared": len(out), "b0_tuple_agreement": sum(o["b0_protected_same"] for o in out),
            "b2_tuple_agreement": sum(o["b2_protected_same"] for o in out),
            "max_abs_stat_diff": max(o["max_abs_stat_diff"] for o in out), "executions": out,
            "note": "readiness only: greedy seed-0 probe vs the historical October rows; not part of the evidence"}


def _count_records(path: Path) -> int:
    """Number of JSONL records (non-blank lines), as len(read_jsonl(path)) but without parsing."""
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def audit(role: str, run_id: str | None = None) -> dict:
    d = ROLES[role]
    run_id = run_id or d["run_id"]
    run = CATEGORY / "runs" / run_id
    recs = read_jsonl(run / "executions.jsonl")
    keys = [(r["case"], r["condition"], r["seed"]) for r in recs]
    keyset, sched = set(keys), scheduled_keys(role)
    attempts = read_jsonl(run / "attempts.jsonl")
    started = {a["attempt"]: a for a in attempts if a["event"] == "start"}
    committed = {a["attempt"] for a in attempts if a["event"] == "commit"}
    man = json.loads((run / "manifest.json").read_text()) if (run / "manifest.json").exists() else {}
    model = man.get("model") or {}
    out = {
        "role": role, "run_id": run_id, "audited": now(),
        "scheduled": len(sched), "present": len(keyset), "duplicates": len(keys) - len(keyset),
        "missing": [f"{c}/{k}/{s}" for c, k, s in sched if (c, k, s) not in keyset],
        "unscheduled": sorted(f"{c}/{k}/{s}" for c, k, s in keyset - set(sched)),
        "by_condition": {k: sum(1 for x in keys if x[1] == k) for k in CONDITIONS},
        "b0_parse_failures": sum(1 for r in recs if r["b0"]["status"] != "ok"),
        "b2_parse_failures": sum(1 for r in recs if r["reconstruction"].get("status") != "ok"),
        "attempts": {"started": len(started), "committed": len(committed & set(started)),
                     "records_without_commit": sorted(r["attempt"] for r in recs if r.get("attempt") not in committed),
                     "incomplete": sorted(f"{a['case']}/{a['condition']}/{a['seed']}#{k}" for k, a in started.items() if k not in committed)},
        "resume_events": len(read_jsonl(run / "resumes.jsonl")),
        "manifest": {"run_id": man.get("run_id"), "started": man.get("started"), "plan_sha256": man.get("plan_sha256"),
                     "read_only": bool(man) and not (run / "manifest.json").stat().st_mode & 0o222,
                     "model_revision": model.get("revision"), "dtype": model.get("dtype"), "batch_candidates": model.get("batch_candidates"),
                     "fixtures_match_current": (man.get("fixture_files") == fixture_hashes(role)) if man else None},
        "sidecars": {f: (run / f).exists() for f in ("manifest.json", "executions.jsonl", "attempts.jsonl", "ledger.jsonl",
                                                     "trace.jsonl", "inputs.jsonl", "SHA256SUMS")},
        "ledger_entries": _count_records(run / "ledger.jsonl"),
        "trace_calls": _count_records(run / "trace.jsonl"),   # 80 MB for gen-test: count lines, do not parse
        "sha256sums_mismatched": verify_sums(run) if (run / "SHA256SUMS").exists() else None,
    }
    out["complete"] = (out["present"] == out["scheduled"] and not out["duplicates"] and not out["unscheduled"]
                       and not out["attempts"]["records_without_commit"]
                       and out["manifest"]["model_revision"] == MODEL["revision"] and out["manifest"]["dtype"] == MODEL["dtype"]
                       and out["manifest"]["batch_candidates"] is False and bool(out["manifest"]["fixtures_match_current"]))
    return out


def backup(run_id: str, dest_root: str) -> dict:
    """Verified checkpoint copy of a finished run (never call on a run that is still being written)."""
    rec = checkpoint(CATEGORY / "runs" / run_id, resolve_out(f"{dest_root}/{run_id}", mkdir=True))
    with open(resolve_out(f"{OUT}/backups.jsonl", mkdir=True), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inventory")
    p.add_argument("--release-json", default="downloads/tvus-artifact-v1.0.1/RELEASE.json")
    p.add_argument("--searches", default=f"{OUT}/searches.json", help="JSON list of {location, method, outcome, at}")
    sub.add_parser("plan")
    sub.add_parser("freeze")
    for name in ("argv", "freeze-thresholds"):
        p = sub.add_parser(name)
        p.add_argument("--role", required=True, choices=list(ROLES) + ["probe"])
    sub.add_parser("projection")
    sub.add_parser("probe-compare")
    p = sub.add_parser("audit")
    p.add_argument("--role", required=True, choices=list(ROLES))
    p.add_argument("--run-id")
    p = sub.add_parser("checksum")
    p.add_argument("--run-id", required=True)
    p = sub.add_parser("backup")
    p.add_argument("--role", choices=list(ROLES))
    p.add_argument("--run-id")
    p.add_argument("--dest", default="evidence/qwen32b-backup")
    a = ap.parse_args()
    if a.cmd == "inventory":
        searches = json.loads((CATEGORY / a.searches).read_text())
        inv = inventory(CATEGORY / a.release_json, searches)
        resolve_out(f"{OUT}/inventory.json", mkdir=True).write_text(json.dumps(inv, indent=2) + "\n")
        for m in inv["matrices"]:
            print(f"{m['role']:9} sched {m['scheduled_executions']:5}  counts-agree {m['summary_counts_agree']}  "
                  f"thr-ok {m['thresholds']['matches_summary']}  raw-local {m['raw_files_present_locally']}  -> {m['disposition']}")
    elif a.cmd == "plan":
        pl = plan()
        resolve_out(f"{OUT}/run-plan.json", mkdir=True).write_text(json.dumps(pl, indent=2) + "\n")
        print(f"run-plan.json: {len(pl['runs'])} runs, {pl['total_evidence_executions']} evidence executions")
    elif a.cmd == "freeze":
        print(json.dumps(freeze(), indent=1))
    elif a.cmd == "argv":
        print(argv(a.role))
    elif a.cmd == "freeze-thresholds":
        print(json.dumps(freeze_thresholds(a.role)))
    elif a.cmd in ("projection", "probe-compare"):
        res = projection() if a.cmd == "projection" else probe_compare()
        resolve_out(f"{OUT}/{a.cmd}.json", mkdir=True).write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps({k: v for k, v in res.items() if k != "executions"}, indent=1))
    elif a.cmd == "audit":
        res = audit(a.role, a.run_id)
        resolve_out(f"{OUT}/coverage-{res['run_id']}.json", mkdir=True).write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps({k: v for k, v in res.items() if k not in ("missing",)}, indent=1))
        return 0 if res["complete"] else 1
    elif a.cmd == "checksum":
        print(write_sums(CATEGORY / "runs" / a.run_id))
    elif a.cmd == "backup":
        rec = backup(a.run_id or ROLES[a.role]["run_id"], a.dest)
        print(json.dumps(rec))
        return 0 if rec["verified"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
