"""Verify a complete extracted release before installation."""
import hashlib
import json
from pathlib import Path
import sys


MANIFEST = "SHA256SUMS.json"


def verify(root):
    expected = json.loads((root / MANIFEST).read_text("utf-8"))
    if not isinstance(expected, dict):
        raise ValueError("Invalid manifest.")
    files = {}
    for item in root.rglob("*"):
        if item.is_symlink():
            raise ValueError(f"Unexpected symbolic link: {item.relative_to(root)}")
        if item.is_file() and item != root / MANIFEST:
            with item.open("rb") as stream:
                files[item.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    if expected != files:
        missing = expected.keys() - files.keys()
        extra = files.keys() - expected.keys()
        changed = {key for key in expected.keys() & files.keys() if expected[key] != files[key]}
        raise ValueError(f"Verification failed. Missing: {sorted(missing)}; extra: {sorted(extra)}; changed: {sorted(changed)}")
    return len(files)


if __name__ == "__main__":
    try:
        print(f"Verified {verify(Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve())} files.")
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
