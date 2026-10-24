"""Bind evaluator.json to runtime.json by SHA-256 (run after editing a fixture)."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner.schema import case_dirs, runtime_hash

def main(ids: list[str]) -> None:
    for p in case_dirs():
        if ids and p.name not in ids:
            continue
        rt = json.loads((p / "runtime.json").read_text())
        ev_path = p / "evaluator.json"
        ev = json.loads(ev_path.read_text())
        ev["runtime_sha256"] = runtime_hash(rt)
        ev_path.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n")
        print("bound", p.name, ev["runtime_sha256"][:12])

if __name__ == "__main__":
    main(sys.argv[1:])
