"""Output-location guard for w3 research artifacts.

Every artifact must live under the project root (``projects/tvus-research/``, formerly the repository-root ``w3/``)
(the "category root"), regardless of the working directory.  This module
resolves and validates paths, rejects traversal / symlink escapes and sets the
cache/temp environment for child processes.  It is an output-location contract,
not an OS sandbox.
"""
from __future__ import annotations

import os
from pathlib import Path

CATEGORY = Path(__file__).resolve().parent.parent  # project root projects/tvus-research/ (committed code + ignored data roots runs/ cache/ envs/ downloads/ evidence/ tmp/)
REPO_ROOT = CATEGORY.parent.parent


def category_root() -> Path:
    return CATEGORY


def resolve_out(rel: str | os.PathLike, *, mkdir: bool = False) -> Path:
    """Resolve ``rel`` under the category root and refuse escapes."""
    p = Path(rel)
    p = p if p.is_absolute() else CATEGORY / p
    real = p.resolve() if p.exists() else p.parent.resolve() / p.name
    try:
        real.relative_to(CATEGORY)
    except ValueError as e:  # traversal / symlink / external path
        raise PermissionError(f"path escapes category root: {rel} -> {real}") from e
    if mkdir:
        real.parent.mkdir(parents=True, exist_ok=True)
    return real


def child_env() -> dict[str, str]:
    """Environment for subprocesses: all caches/temp inside the category."""
    env = dict(os.environ)
    env.update(
        {
            "HF_HOME": str(resolve_out("cache/hf")),
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_OFFLINE": "1",
            "TMPDIR": str(resolve_out("tmp")),
            "MPLCONFIGDIR": str(resolve_out("cache/mpl")),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    for k in ("HF_HOME", "TMPDIR", "MPLCONFIGDIR"):
        Path(env[k]).mkdir(parents=True, exist_ok=True)
    return env


def apply_env() -> None:
    os.environ.update(child_env())


if __name__ == "__main__":
    print("category root:", CATEGORY)
    for bad in ("../x", "/tmp/x"):
        try:
            resolve_out(bad)
            print("FAIL accepted", bad)
        except PermissionError:
            print("ok rejected", bad)
    print("ok", resolve_out("runs/demo"))
