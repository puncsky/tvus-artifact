"""Export the workshop's public artifact without monorepo history or private notes.

Run from the research project with Python 3.12+. This only prepares local files;
GitHub publication is a separate, explicitly authorized operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "v1.0.1"            # --version overrides; a published tag is never rebuilt in place
ZIP_DATE = (2026, 10, 24, 0, 0, 0)
OUT = ROOT / f"artifact/tvus-public-{VERSION}"
CODE_DIRS = ["runner", "models", "generator", "cases", "confirmation",
             "failure-boundary", "generated", "configs", "docs", "bypass", "external/agentdojo"]
ROOT_FILES = ["protocol.md", "protocol-v2.md", "preregistration.json",
              "preregistration-v2.json", "artifacts.md", "baseline-matrix.md"]
REVIEW_FILES = ["fixture-authoring-brief.md", "case-review-template.json", "release-search-validity.json"]
SUPPORT_REPORTS = {"main", "separability", "causalarmor-native", "adaptive-pilot-qwen14b", "model-readiness"}
QWEN32B_PLAN = "reports/qwen32b-evidence/run-plan.json"   # the run plan every Qwen-32B run manifest binds by hash
HOST_ONLY = {"runner/qwen32b_evidence.py", "runner/qwen32b_compare.py"}   # collection-host tooling (local backups, model cache)
ROOT_REPORTS = ["bypass-extractor-audit.json", "bypass-extractor.md", "binding-control.json",
                "serialization-probe-qwen14b.json", "structural-baselines-compatibility.md"]
SCRIPT_FILES = ["smoke_adapter.py", "serialization_probe.py", "verify_artifact.py", "verify_paper_tables.py",
                "check_resume_mock.sh", "analyze_qwen32b.sh", "verify_qwen32b_release.py", "make_public_artifact.py"]   # the verifier reuses the export redaction rules
# raw files of a legacy run; a checksum-bound run ships exactly the files its SHA256SUMS lists (see raw_files)
RAW_FILES = ["manifest.json", "executions.jsonl", "queries.jsonl", "summary.json", "ledger.json", "spend.json",
             "spend-attacker.json"]
TEXT_EXT = {".py", ".sh", ".md", ".json", ".jsonl", ".txt", ".csv", ".svg", ".tex", ".bib", ".cff", ".lock"}
ALLOWED_EXT = TEXT_EXT | {".png", ".pdf"}
LOCAL_PATHS = [(re.compile(r"/Users/[A-Za-z0-9_.-]+/projects/tianpan-v3/projects/tvus-research"), "<ARTIFACT_ROOT>"),
               (re.compile(r"/Users/[A-Za-z0-9_.-]+/projects/tianpan-v3/w3"), "<ARTIFACT_ROOT>"),
               (re.compile(r"/Users/[A-Za-z0-9_.-]+/projects/tianpan-v3"), "<REPO_ROOT>"),
               (re.compile(r"/Users/[A-Za-z0-9_.-]+"), "/Users/<user>"),
               (re.compile(r"/home/[A-Za-z0-9_.-]+"), "/home/<user>"),
               (re.compile(r"/opt/homebrew/opt/python@3\.12/bin/python3\.12"), "python3.12")]
SECRETS = [re.compile(p) for p in [r"sk-ant-[A-Za-z0-9_-]{20,}", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}",
           r"\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,})", r"\bhf_[A-Za-z0-9]{20,}",
           r"AIza[A-Za-z0-9_-]{30,}", r"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----"]]
REDACTIONS = []


def wanted(path: Path) -> bool:
    return (path.is_file() and not path.is_symlink()
            and not any(p.startswith(".") or p == "__pycache__" for p in path.relative_to(ROOT).parts)
            and path.relative_to(ROOT).as_posix() not in HOST_ONLY
            and path.suffix in ALLOWED_EXT)


def checksum_bound(run: Path) -> bool:
    """A durable-recorder run (runner/recording.py) whose SHA256SUMS and manifest bind its files: copied byte-identically."""
    return (run / "SHA256SUMS").is_file()


def raw_files(run: Path) -> list[str]:
    if checksum_bound(run):
        return ["SHA256SUMS"] + [line.split("  ", 1)[1] for line in (run / "SHA256SUMS").read_text().splitlines() if line.strip()]
    return RAW_FILES


def copy(src: Path, rel: Path | str | None = None) -> None:
    rel = Path(rel) if rel else src.relative_to(ROOT)
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    raw = src.read_bytes()
    verbatim = rel.parts[0] == "runs" and checksum_bound(src.parent)
    is_text = src.suffix in TEXT_EXT or src.name in {"LICENSE-agentdojo", "LICENSE", "Makefile"}
    if verbatim or is_text:
        text = raw.decode("utf-8", "replace") if verbatim else raw.decode()
        if any(pattern.search(text) for pattern in SECRETS):
            raise ValueError(f"Credential-like material in {rel}; refusing export")
    if verbatim:   # never rewritten (secret scan above still applies)
        dst.write_bytes(raw)
        dst.chmod(0o644)
        return
    if is_text:
        if src.is_relative_to(ROOT / "release") and "{{" in text:
            raise ValueError(f"Unfilled template placeholder in {src.relative_to(ROOT)}; refusing export")
        # Fixtures/query texts are hash-bound; require them to remain byte-identical.
        scrubbed = text
        for pattern, replacement in LOCAL_PATHS:
            scrubbed = pattern.sub(replacement, scrubbed)
        if scrubbed != text:
            if src.name in {"runtime.json", "evaluator.json", "queries.jsonl", "executions.jsonl"}:
                raise ValueError(f"Hash-bound scientific data needs explicit review: {rel}")
            REDACTIONS.append(str(rel))
        raw = scrubbed.encode()
    dst.write_bytes(raw)
    dst.chmod(0o755 if src.stat().st_mode & 0o111 else 0o644)


def main() -> None:
    global VERSION, OUT, ZIP_DATE
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=VERSION)
    ap.add_argument("--zip-date", default=None, help="YYYY-MM-DD stamped on every ZIP entry (reproducible archive)")
    a = ap.parse_args()
    VERSION, OUT = a.version, ROOT / f"artifact/tvus-public-{a.version}"
    if a.zip_date:
        ZIP_DATE = tuple(map(int, a.zip_date.split("-"))) + (0, 0, 0)
    if (OUT / ".git").exists():
        raise ValueError("Refusing to overwrite an initialized Git checkout")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for directory in CODE_DIRS:
        for path in sorted((ROOT / directory).rglob("*")):
            if wanted(path):
                copy(path)
    copy(ROOT / "external/agentdojo/LICENSE-agentdojo")
    for name in ROOT_FILES:
        copy(ROOT / name)
    for name in REVIEW_FILES:
        copy(ROOT / "review" / name)
    for name in SCRIPT_FILES:
        copy(ROOT / "scripts" / name)
    def report_run(p: Path) -> str:   # a report's raw run is the run_id analyze.py records
        return json.loads((p / "summary.json").read_text())["run_id"]
    # every exported run report has its raw run; derived-only and duplicate analyses stay local
    report_dirs = sorted(p for p in (ROOT / "reports").iterdir() if p.is_dir()
                         and (p.name in SUPPORT_REPORTS or ((p / "summary.json").exists()
                                                            and (ROOT / "runs" / report_run(p) / "executions.jsonl").exists()))
                         and not re.search(r"mock|dry|refix|histfix|h1thr|secthr", p.name))
    for directory in report_dirs:
        for path in sorted(directory.rglob("*")):
            if wanted(path) and path.name != "README.md":
                copy(path)
    for name in ROOT_REPORTS:
        copy(ROOT / "reports" / name)
    copy(ROOT / QWEN32B_PLAN)
    # Preserve the actual author's signed validation, separately from private packets.
    for path in sorted((ROOT / "review").glob("spot-check*")):
        if path.suffix == ".md":
            copy(path)
    run_names = {report_run(p) if (p / "summary.json").exists() else p.name for p in report_dirs}
    run_names |= {p.name for p in (ROOT / "runs").glob("bypass-*") if "mock" not in p.name}
    run_names |= {"adaptive-pilot-qwen14b", "adojo-h2-qwen14b"}
    coverage = []
    for name in sorted(run_names):
        directory = ROOT / "runs" / name
        shipped = []
        for filename in raw_files(directory):
            path = directory / filename
            if path.exists():
                copy(path)
                shipped.append(filename)
        if shipped or (ROOT / "reports" / name / "summary.json").exists():
            coverage.append({"run": name, "raw_files": shipped,
                             "derived_rows": (OUT / "reports" / name / "rows.jsonl").exists(),
                             "summary": (OUT / "reports" / name / "summary.json").exists()})
    for name in ["main.tex", "main.pdf", "refs.bib"]:
        copy(ROOT / "paper/workshop" / name)
    for path in (ROOT / "paper/workshop/figures").glob("*.tex"):
        copy(path)
    for path in (ROOT / "release").rglob("*"):
        if path.is_file():
            copy(path, path.relative_to(ROOT / "release"))
    (OUT / "RELEASE.json").write_text(json.dumps({
        "version": VERSION, "author": "Tian Pan", "repository": "https://github.com/puncsky/tvus-artifact",
        "path_redactions": REDACTIONS, "run_coverage": coverage,
        "missing_raw_runs": [r["run"] for r in coverage if r["derived_rows"] and not r["raw_files"]],
        "historical_hashes": "Original run manifests retain original code hashes; MANIFEST.sha256 covers the public export.",
        "verbatim_raw_evidence": sorted(r["run"] for r in coverage if checksum_bound(ROOT / "runs" / r["run"]) and r["raw_files"]),
        "verbatim_note": ("Checksum-bound run files are copied byte-identically (their SHA256SUMS and manifests bind them), so their "
                          "manifests keep the collection host's absolute cache path and hostname; all other metadata paths are scrubbed."),
    }, indent=2) + "\n")
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT).as_posix()}"
             for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "MANIFEST.sha256"]
    (OUT / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    archive = ROOT / f"artifact/tvus-artifact-{VERSION}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(f"tvus-artifact-{VERSION}/{path.relative_to(OUT).as_posix()}", ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
                bundle.writestr(info, path.read_bytes())
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{sha}  {archive.name}\n")
    print(json.dumps({"files": len(lines), "archive": str(archive.relative_to(ROOT)),
                      "zip_bytes": archive.stat().st_size, "path_redactions": len(REDACTIONS),
                      "missing_raw_runs": [r["run"] for r in coverage if r["derived_rows"] and not r["raw_files"]]}, indent=2))


if __name__ == "__main__":
    main()
