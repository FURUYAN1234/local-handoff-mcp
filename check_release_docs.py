"""Check that both technical papers identify the exact candidate release."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
version = (root / "VERSION").read_text("ascii").strip()
for name in ("paper-ja.md", "paper-en.md"):
    header = (root / name).read_text("utf-8").splitlines()[:4]
    if not any(line.startswith(f"Local Handoff MCP v{version} ") for line in header):
        sys.exit(f"{name}: update the technical paper for v{version}")
print(f"Technical paper versions match v{version}.")
