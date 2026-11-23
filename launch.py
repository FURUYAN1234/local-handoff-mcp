"""Run the release selected by the installer."""
import json
import os
from pathlib import Path
import re
import sys


def main():
    root = Path(__file__).resolve().parent
    try:
        version = json.loads((root / "current.json").read_text("utf-8"))["version"]
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise ValueError("invalid version")
        entry = root / "versions" / ("v" + version) / "handoff.py"
        os.execv(sys.executable, [sys.executable, "-B", str(entry), "--config",
                                 str(root / "settings.json"), *sys.argv[1:]])
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Local Handoff MCP: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
