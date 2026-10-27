"""End-to-end verification of a candidate public artifact (research .pm/w1/m1/t010). No model calls.

Run with the analysis environment's Python on a ZIP that has not been extracted yet:

    python -B scripts/verify_qwen32b_release.py artifact/tvus-artifact-v1.1.0.zip [--pdf artifact/submission/main.pdf]

Steps (each must pass; a JSON report is written next to the extraction):
  1. extract into a fresh directory; MANIFEST.sha256 and every replication run's SHA256SUMS verify before any output
  1b. secret / private-path scan of the pristine tree (replication raw records are verbatim, so host paths are listed)
  1c. in a fresh venv without packages: the documented quick start, fixture validation, generator self-check, H1/H2
      mock pipelines and the Qwen-14B dev/conf reanalysis (summaries equal the shipped ones)
  2. per run: executions keys == frozen plan schedule, no duplicates, manifest bindings (revision, bf16, unbatched,
     plan hash; fixture and collection-code file hashes equal to the shipped files)
  3. regenerate all six replication reports from raw executions with their declared thresholds; summaries and rows
     must equal the shipped ones in published form (wall-clock fields excluded, local paths redacted as by the export)
  4. scripts/verify_paper_tables.py --qwen32b replication; runner/qwen32b_compare.py regenerated into a separate
     directory: raw recount clean and comparison/role index equal to the shipped ones
  5. scripts/check_resume_mock.sh (interruption/resume/refusal on the mock pipeline); 5c. README/RESULTS headline
     numbers equal the recomputed ones
  6. optional PDF hash comparison with the canonical build
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

PLAN = "reports/qwen32b-evidence/run-plan.json"
WALL_CLOCK = re.compile(r"(seconds|wall|_at$|^started$|^finished$|^audited$)")   # the only nondeterministic summary/row fields


@functools.lru_cache(maxsize=None)
def export_rules():
    """The exporter (shipped next to this script): its SECRETS, LOCAL_PATHS and TEXT_EXT define what was published."""
    spec = importlib.util.spec_from_file_location("export", Path(__file__).resolve().parent / "make_public_artifact.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jsonl(p: Path) -> list:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def check_sums(root: Path, listing: str) -> list[str]:
    """Names in a sha256sum listing whose file is missing or differs (independent of the recorder under test)."""
    bad = []
    for line in (root / listing).read_text().splitlines():
        digest, name = line.split("  ", 1)
        if not (root / name).is_file() or sha(root / name) != digest:
            bad.append(name)
    return bad


def strip_timing(x):
    if isinstance(x, dict):
        return {k: strip_timing(v) for k, v in x.items() if not WALL_CLOCK.search(k)}
    if isinstance(x, list):
        return [strip_timing(v) for v in x]
    return x


def _redact(x):
    if isinstance(x, dict):
        return {k: _redact(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_redact(v) for v in x]
    if isinstance(x, str):
        for pattern, replacement in export_rules().LOCAL_PATHS:
            x = pattern.sub(replacement, x)
    return x


def published(x):
    """x in the exporter's published form: wall-clock fields dropped and local paths redacted as in the export."""
    return _redact(strip_timing(x))


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, env=dict(os.environ, **(env or {})), capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def tail(log: str) -> str:
    return log.strip().splitlines()[-1][:300] if log.strip() else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--dest", default=None, help="fresh extraction directory (default: next to the ZIP)")
    ap.add_argument("--pdf", default=None, help="canonical PDF to compare with the shipped paper/workshop/main.pdf")
    a = ap.parse_args()
    zp = Path(a.zip).resolve()
    dest = Path(a.dest).resolve() if a.dest else zp.with_name(zp.stem + "-verify")
    if dest.exists():
        raise SystemExit(f"{dest} exists; verification needs a fresh directory")
    with zipfile.ZipFile(zp) as z:
        z.extractall(dest)
    root = next(dest.iterdir())
    py = sys.executable
    rep: dict = {"zip": str(zp.name), "zip_sha256": sha(zp), "root": root.name, "steps": {}}
    plan = json.loads((root / PLAN).read_text())
    evidence = [r for r in plan["runs"] if r["evidence"]]

    # 1. checksums before generating anything
    rep["steps"]["1_checksums"] = {"manifest_mismatch": check_sums(root, "MANIFEST.sha256"),
                                   "run_sums": {r["run_id"]: check_sums(root / "runs" / r["run_id"], "SHA256SUMS") for r in evidence}}
    ok = not rep["steps"]["1_checksums"]["manifest_mismatch"] and not any(rep["steps"]["1_checksums"]["run_sums"].values())

    # 1b. secret and private-path scan of the pristine extraction (before any step writes outputs)
    local = re.compile(r"/(?:Users|home)/(?!<user>)[A-Za-z0-9_.-]+/")
    verbatim_dirs = tuple(f"runs/{r['run_id']}/" for r in evidence)
    hits, verbatim_paths = [], []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in export_rules().TEXT_EXT | {".patch"}:
            rel = p.relative_to(root).as_posix()
            text = p.read_text(errors="replace")
            hits += [f"{rel}: secret-like {m.pattern[:24]}" for m in export_rules().SECRETS if m.search(text)]
            if local.search(text):
                # replication raw records are shipped byte-identical (bound by SHA256SUMS); everything else is scrubbed
                (verbatim_paths if rel.startswith(verbatim_dirs) else hits).append(rel)
    rep["steps"]["1b_scan"] = {"hits": hits[:50], "verbatim_raw_files_with_host_paths": verbatim_paths}
    ok &= not hits

    # 1c. documented quick start (release checksums first), fixtures, mock pipelines and Qwen-14B reanalysis in a
    #     fresh venv without packages
    venv = dest / "venv-stdlib"
    subprocess.run([str(Path(sys.base_prefix) / "bin" / f"python{sys.version_info[0]}.{sys.version_info[1]}"), "-m", "venv", str(venv)], check=True)
    vpy = str(venv / "bin" / "python")
    cases = lambda d: {"W3_CASES_DIR": str(root / d)}
    s1c = {}
    for name, cmd, env in [
        ("verify_artifact", ["scripts/verify_artifact.py"], None),
        ("validate_dev", ["runner/validate.py"], None),
        ("validate_conf", ["runner/validate.py"], cases("confirmation/cases")),
        ("validate_fb", ["runner/validate.py"], cases("failure-boundary/cases")),
        ("validate_agentdojo", ["runner/validate.py"], cases("external/agentdojo/cases")),
        ("generator_selfcheck", ["generator/selfcheck.py", "--cases", "generated/cases"], None),
        ("paper_tables", ["scripts/verify_paper_tables.py"], None),
        ("release_search_audit", ["runner/release_search_audit.py", "--check"], None),
        ("mock_h1", ["runner/experiment.py", "--model", "mock", "--run-id", "verify-mock-h1", "--cases", "S01", "H02", "L02", "--seeds", "0"], None),
        ("mock_h1_analyze", ["runner/analyze.py", "--run", "verify-mock-h1", "--calibrate"], None),
        ("mock_h2", ["runner/experiment.py", "--model", "mock", "--harness", "h2", "--run-id", "verify-mock-h2", "--cases", "S01", "H02", "L02", "--seeds", "0"], None),
        ("mock_h2_analyze", ["runner/analyze.py", "--run", "verify-mock-h2", "--calibrate"], None),
        ("reanalyze_dev_qwen14b", ["runner/analyze.py", "--run", "dev-qwen14b", "--thresholds", "reports/dev-qwen14b/thresholds.json", "--out", "reports/verify-dev-qwen14b"], None),
        ("reanalyze_conf_qwen14b", ["runner/analyze.py", "--run", "conf-qwen14b", "--thresholds", "reports/dev-qwen14b/thresholds.json", "--out", "reports/verify-conf-qwen14b"], cases("confirmation/cases")),
    ]:
        code, log = run([vpy, "-B"] + cmd, root, env)
        s1c[name] = {"exit": code, "tail": tail(log)}
        ok &= code == 0
    for run_id in ("dev-qwen14b", "conf-qwen14b"):
        new = root / "reports" / f"verify-{run_id}" / "summary.json"
        equal = new.exists() and published(json.loads(new.read_text())) == published(json.loads((root / "reports" / run_id / "summary.json").read_text()))
        s1c[f"{run_id}_summary_equal"] = equal
        ok &= equal
    rep["steps"]["1c_stdlib_venv"] = s1c

    # 2. schedule and manifest bindings
    s2 = {}
    for r in evidence:
        d = root / "runs" / r["run_id"]
        recs = jsonl(d / "executions.jsonl")
        keys = [(x["case"], x["condition"], x["seed"]) for x in recs]
        want = sorted((c, k, s) for c in r["cases"] for k in r["conditions"] for s in r["seeds"])
        man = json.loads((d / "manifest.json").read_text())
        fx = {cid: {f: sha(next((root / r["cases_dir"]).glob(f"*/{cid}")) / f) for f in ("runtime.json", "evaluator.json")}
              for cid in r["cases"]}
        e = s2[r["role"]] = {
            "executions": len(recs), "scheduled": r["scheduled"], "keys_equal_plan": sorted(keys) == want,
            "duplicates": len(keys) - len(set(keys)), "revision": man["model"]["revision"], "dtype": man["model"]["dtype"],
            "batch_candidates": man["model"]["batch_candidates"], "plan_sha256_matches": man["plan_sha256"] == sha(root / PLAN),
            "fixture_files_match": man["fixture_files"] == fx,
            "code_files_match": all((root / f).is_file() and sha(root / f) == h for f, h in man["code"].items())}
        ok &= (e["keys_equal_plan"] and not e["duplicates"] and e["batch_candidates"] is False and e["dtype"] == "bf16"
               and e["revision"] == plan["model"]["revision"] and e["plan_sha256_matches"] and e["fixture_files_match"]
               and e["code_files_match"])
    rep["steps"]["2_schedule_and_bindings"] = s2

    # 3. regenerate reports from raw and compare with the shipped summaries
    s3 = {}
    for r in evidence:
        out_rel = f"reports/verify-{r['run_id']}"
        out, shipped = root / out_rel, root / "reports" / r["run_id"]
        code, _ = run([py, "-B", "runner/analyze.py", "--run", r["run_id"], "--thresholds", r["primary_thresholds"]["file"], "--out", out_rel],
                      root, {"W3_CASES_DIR": str(root / r["cases_dir"])})
        s3[r["role"]] = {"exit": code,
                         "summary_equal": code == 0 and published(json.loads((out / "summary.json").read_text()))
                         == published(json.loads((shipped / "summary.json").read_text())),
                         "rows_equal": code == 0 and published(jsonl(out / "rows.jsonl")) == published(jsonl(shipped / "rows.jsonl"))}
        ok &= s3[r["role"]]["summary_equal"] and s3[r["role"]]["rows_equal"]
    rep["steps"]["3_reanalysis_from_raw"] = s3

    # 4. paper tables and comparison
    code, log = run([py, "-B", "scripts/verify_paper_tables.py", "--qwen32b", "replication"], root)
    rep["steps"]["4_paper_tables"] = {"exit": code, "tail": tail(log)}
    code2, _ = run([py, "-B", "runner/qwen32b_compare.py", "--out", "reports/verify-qwen32b-evidence"], root)
    comp = json.loads((root / "reports/verify-qwen32b-evidence/comparison.json").read_text()) if code2 == 0 else {}
    same = {f: code2 == 0 and json.loads((root / "reports/verify-qwen32b-evidence" / f).read_text())
               == json.loads((root / "reports/qwen32b-evidence" / f).read_text()) for f in ("comparison.json", "role-index.json")}
    rec = {role: e.get("raw_recount") for role, e in comp.get("roles", {}).items()}
    rep["steps"]["4_compare"] = {"exit": code2, "raw_recount_mismatches": {k: len(v["mismatches"]) if v else None for k, v in rec.items()},
                                 "keys_equal_schedule": {k: v["keys_equal_schedule"] if v else None for k, v in rec.items()},
                                 "regenerated_equals_shipped": same}
    ok &= code == 0 and code2 == 0 and all(same.values()) and all(v == 0 for v in rep["steps"]["4_compare"]["raw_recount_mismatches"].values())

    # 5. mock interruption / resume / refusal from the export
    code, log = run(["sh", "scripts/check_resume_mock.sh", py], root)
    rep["steps"]["5_resume_mock"] = {"exit": code, "tail": tail(log)}
    ok &= code == 0

    # 5c. headline numbers in the public docs equal the recomputed replication numbers
    m = comp.get("manuscript_numbers", {}).get("replication", {})
    regen_all = comp.get("roles", {}).get("gen-test", {}).get("replication", {}).get("defenses", {}).get("b6_regen_only", {}).get("attack_unauthorized_execution")
    want = [m.get("abstract_test_chosen_action_steered_miss"), m.get("abstract_test_h0_regen_steered_miss"), regen_all]
    docs = {f: (root / f).read_text() for f in ("README.md", "RESULTS.md")}
    rep["steps"]["5c_docs_numbers"] = {f: {str(w): w is not None and f"{w}" in t for w in want} for f, t in docs.items()}
    ok &= all(all(v.values()) for v in rep["steps"]["5c_docs_numbers"].values())

    # 6. PDF identity with the canonical build
    if a.pdf:
        shipped_pdf, canonical = sha(root / "paper/workshop/main.pdf"), sha(Path(a.pdf))
        rep["steps"]["6_pdf"] = {"shipped": shipped_pdf, "canonical": canonical, "equal": shipped_pdf == canonical}
        ok &= shipped_pdf == canonical
    rep["pass"] = bool(ok)
    (dest / "verification.json").write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({"pass": rep["pass"], "report": str(dest / "verification.json")}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
