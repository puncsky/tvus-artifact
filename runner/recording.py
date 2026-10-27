"""Durable run recording for ``runner/experiment.py`` (append-only sidecars, immutable manifest, checkpoints).

Files in ``runs/<run-id>/`` (all JSON Lines are append-only, flushed and fsynced per record):

  manifest.json    written once at run creation, then read-only (mode 0444); resumes never rewrite it
  resumes.jsonl    one event per resumed session: time, host, source state, describe(), incomplete attempts
  attempts.jsonl   ``start`` / ``commit`` events per execution attempt (an uncommitted start = interrupted attempt)
  executions.jsonl the committed execution records (unchanged format + ``attempt``/``started``/``finished``)
  trace.jsonl      one record per model call: serialized-input hash, prompt-token hash, decoding settings,
                   raw output text (generate) or continuations + per-token log-probs (score), ledger entries
  inputs.jsonl     content-addressed model inputs: {"sha256", "messages"} written once per distinct input
  ledger.jsonl     every CostLedger entry, tagged with session and attempt (cumulative across sessions)
  ledger.json      cumulative ledger snapshot rewritten from ledger.jsonl at normal exit (legacy consumers)
  SHA256SUMS       checkpoint checksums (``checkpoint``), verified again at the backup copy

Model inputs are built from the runtime view only (``PublicCase``), so traces never contain evaluator truth.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path

from runner.paths import CATEGORY

RECORDER_VERSION = 1
# compatibility keys: a resume must reproduce every one of these exactly, otherwise it is refused
COMPAT_MODEL_KEYS = ("backend", "family", "hf_repo", "revision", "model_type", "quantization", "dtype", "device", "eos_id",
                     "stop_ids", "attn_implementation", "batch_candidates", "torch", "transformers", "sampling")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class AppendLog:
    """Append-only JSON Lines file; every record is flushed and fsynced before ``write`` returns."""

    def __init__(self, path: Path):
        self.path = path
        self.fh = open(path, "a", encoding="utf-8")

    def write(self, rec: dict) -> None:
        self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def close(self) -> None:
        self.fh.close()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def repair_torn_tail(path: Path, session: int) -> dict | None:
    """A hard kill can leave a partial last line. Move the torn bytes to a sidecar and cut the file back
    to its last complete record; earlier records are untouched."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    data = path.read_bytes()
    cut = data.rstrip(b"\n").rfind(b"\n") + 1
    try:
        json.loads(data[cut:])
        if not data.endswith(b"\n"):
            with open(path, "ab") as f:   # complete record, only the newline is missing
                f.write(b"\n")
        return None
    except json.JSONDecodeError:
        pass
    side = path.with_name(f"{path.stem}.torn-s{session}{path.suffix}.txt")
    side.write_bytes(data[cut:])
    with open(path, "r+b") as f:
        f.truncate(cut)
    return {"file": path.name, "torn_bytes": len(data) - cut, "saved_as": side.name}


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

def source_state(files: list[str], run_dir: Path, session: int) -> dict:
    """Git revision of the project plus a snapshot patch of any uncommitted change to the bound files."""
    def git(*args: str) -> str | None:
        try:
            return subprocess.run(["git", "-C", str(CATEGORY), *args], capture_output=True, text=True, check=True, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            return None
    head = git("rev-parse", "HEAD")
    if head is None:
        return {"git": None, "note": "no git checkout (e.g. extracted artifact); file hashes are the binding"}
    diff = git("diff", "HEAD", "--", *files) or ""
    untracked = [f for f in (git("ls-files", "--others", "--exclude-standard", "--", *files) or "").split() if f]
    out = {"git": head.strip(), "dirty_bound_files": bool(diff or untracked), "untracked_bound_files": untracked}
    if diff or untracked:
        patch = diff + "".join(f"\n--- untracked {f} (sha256 {sha256_file(CATEGORY / f)})\n" + (CATEGORY / f).read_text()
                               for f in untracked)
        p = run_dir / f"source-snapshot-s{session}.patch"
        p.write_text(patch)
        out.update({"snapshot": p.name, "snapshot_sha256": sha256_file(p)})
    return out


def host_facts() -> dict:
    d = {"hostname": socket.gethostname(), "machine": platform.machine(), "platform": platform.platform(),
         "python": platform.python_version()}
    try:
        q = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=30)
        d["nvidia_smi"] = q.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        d["nvidia_smi"] = None
    return d


def compat_block(manifest: dict) -> dict:
    m = manifest["model"]
    return {"run_id": manifest["run_id"], "harness": manifest["harness"], "run_specs": manifest["run_specs"],
            "conditions": manifest["conditions"], "cases": manifest["cases"], "fixture_files": manifest["fixture_files"],
            "code": manifest["code"], "plan_sha256": manifest.get("plan_sha256"),
            "model": {k: m.get(k) for k in COMPAT_MODEL_KEYS}}


def check_resume(run_dir: Path, manifest: dict) -> tuple[int, list[str]]:
    """Session index for this invocation and, when resuming, every compat mismatch against the stored manifest.

    Writes nothing. Session 0 = the run does not exist yet. A non-empty mismatch list means: refuse the resume.
    """
    path = run_dir / "manifest.json"
    if not path.exists():
        return 0, []
    stored = json.loads(path.read_text())
    if "compat" not in stored:
        return -1, ["existing manifest predates the durable recorder (no compat block): start a new run id"]
    now_c, bad = compat_block(manifest), []
    for k, v in now_c.items():
        sv = stored["compat"].get(k)
        if canonical(sv) != canonical(v):
            if isinstance(v, dict) and isinstance(sv, dict):
                bad += [f"{k}.{kk}: stored {canonical(sv.get(kk))[:120]} != now {canonical(v.get(kk))[:120]}"
                        for kk in sorted(set(v) | set(sv)) if canonical(sv.get(kk)) != canonical(v.get(kk))]
            else:
                bad.append(f"{k}: stored {canonical(sv)[:120]} != now {canonical(v)[:120]}")
    return 1 + len(read_jsonl(run_dir / "resumes.jsonl")), bad


def create_manifest(run_dir: Path, manifest: dict) -> None:
    """Write the run's manifest once (atomic rename, then read-only)."""
    path = run_dir / "manifest.json"
    manifest = {**manifest, "recorder_version": RECORDER_VERSION, "compat": compat_block(manifest)}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2))
    os.replace(tmp, path)
    os.chmod(path, 0o444)


# ---------------------------------------------------------------------------
# recording adapter
# ---------------------------------------------------------------------------

class RecordingAdapter:
    """Transparent proxy around a model adapter that records every call before returning its result.

    Numerical behaviour is the wrapped adapter's: arguments are forwarded unchanged. Inputs are serialized at
    call time (the H2 loop mutates its message list afterwards).
    """

    def __init__(self, inner, run_dir: Path, session: int, abort_after_calls: int | None = None):
        self._inner = inner
        self.session = session
        self.attempt: str | None = None
        self.calls = 0
        self.abort_after_calls = abort_after_calls
        self.trace = AppendLog(run_dir / "trace.jsonl")
        self.inputs = AppendLog(run_dir / "inputs.jsonl")
        self.ledger_log = AppendLog(run_dir / "ledger.jsonl")
        self._seen = {r["sha256"] for r in read_jsonl(run_dir / "inputs.jsonl")}

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def _input_hash(self, messages: list[dict]) -> str:
        blob = canonical(messages)
        h = sha256_bytes(blob.encode("utf-8"))
        if h not in self._seen:
            self.inputs.write({"sha256": h, "messages": messages})
            self._seen.add(h)
        return h

    def _prompt_hash(self, messages: list[dict]) -> dict:
        ids_fn = getattr(self._inner, "_prompt_ids", None)
        if ids_fn is None:
            return {}
        ids = ids_fn(messages)
        return {"prompt_tokens": len(ids), "prompt_ids_sha256": sha256_bytes(canonical(ids).encode())}

    def _record(self, kind: str, label: str, messages: list[dict], n0: int, **body) -> None:
        self.calls += 1
        for e in self._inner.ledger.entries[n0:]:
            self.ledger_log.write({**e, "session": self.session, "attempt": self.attempt, "call": self.calls})
        self.trace.write({"call": self.calls, "session": self.session, "attempt": self.attempt, "kind": kind, "label": label,
                          "input_sha256": self._input_hash(messages), **self._prompt_hash(messages), **body, "at": now()})
        if self.abort_after_calls is not None and self.calls >= self.abort_after_calls:
            os._exit(137)    # fault injection for the resume check: behaves like SIGKILL (no cleanup)

    def generate(self, messages, *, seed=0, temperature=0.0, max_tokens=256, label="gen"):
        n0 = len(self._inner.ledger.entries)
        snap = json.loads(canonical(messages))
        r = self._inner.generate(messages, seed=seed, temperature=temperature, max_tokens=max_tokens, label=label)
        self._record("generate", label, snap, n0, seed=seed, temperature=temperature, max_tokens=max_tokens,
                     text=r.text, finish=r.finish)
        return r

    def score(self, messages, continuations, *, label="score"):
        n0 = len(self._inner.ledger.entries)
        snap = json.loads(canonical(messages))
        res = self._inner.score(messages, continuations, label=label)
        self._record("score", label, snap, n0, continuations=list(continuations),
                     logprob=[x.logprob for x in res], n_tokens=[x.n_tokens for x in res],
                     token_logprobs=[list(x.token_logprobs) for x in res])
        return res

    def close(self) -> None:
        for log in (self.trace, self.inputs, self.ledger_log):
            log.close()


# ---------------------------------------------------------------------------
# checkpoints
# ---------------------------------------------------------------------------

def write_sums(run_dir: Path) -> Path:
    lines = [f"{sha256_file(p)}  {p.relative_to(run_dir).as_posix()}" for p in sorted(run_dir.rglob("*"))
             if p.is_file() and p.name != "SHA256SUMS"]
    (run_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return run_dir / "SHA256SUMS"


def verify_sums(root: Path) -> list[str]:
    """Return the files whose hash does not match SHA256SUMS (empty == verified)."""
    bad = []
    for line in (root / "SHA256SUMS").read_text().splitlines():
        digest, rel = line.split("  ", 1)
        p = root / rel
        if not p.is_file() or sha256_file(p) != digest:
            bad.append(rel)
    return bad


def checkpoint(run_dir: Path, dest: Path) -> dict:
    """Write SHA256SUMS for the run, copy the whole run dir to ``dest`` and verify every hash there."""
    write_sums(run_dir)
    tmp = dest.with_name(dest.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir, tmp)
    bad = verify_sums(tmp)
    if not bad:
        if dest.exists():
            shutil.rmtree(dest)
        os.replace(tmp, dest)
    return {"run": run_dir.name, "dest": str(dest.relative_to(CATEGORY)) if dest.is_relative_to(CATEGORY) else str(dest),
            "files": len((run_dir / "SHA256SUMS").read_text().splitlines()), "sums_sha256": sha256_file(run_dir / "SHA256SUMS"),
            "mismatched": bad, "verified": not bad, "at": now()}
