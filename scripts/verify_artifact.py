"""Check every public artifact file against MANIFEST.sha256 (no dependencies)."""
from pathlib import Path
import hashlib
import sys

root = Path(__file__).resolve().parent.parent
failures = []
lines = (root / "MANIFEST.sha256").read_text().splitlines()
for line in lines:
    expected, name = line.split("  ", 1)
    path = root / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        failures.append(name)
if failures:
    print("Checksum mismatch:", ", ".join(failures))
    sys.exit(1)
print(f"PASS: {len(lines)} artifact files match MANIFEST.sha256")
