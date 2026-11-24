"""Build the ZIP from a clean checkout of the requested version."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

PACKAGE_FILES = ("Install.bat", "Dashboard.bat", "Autosave.bat", "LICENSE", "MANUAL.md", "README.md", "VERSION",
                 "clients.py", "dashboard.py", "dashboard.css", "dashboard.js", "managed_cli.py",
                 "handoff.py", "install.py", "launch.py", "verify_package.py",
                 "paper-ja.md", "paper-en.md", "RELEASE-PROCESS.md", "check_release_docs.py", "docs/sunset-comic.md", "docs/dashboard-demo-v1.1.7.jpg")
ROOT = Path(__file__).resolve().parent


def build(destination):
    subprocess.run([sys.executable, "-B", str(ROOT / "check_release_docs.py")], check=True)
    version = (ROOT / "VERSION").read_text("ascii").strip()
    target = destination / f"Local-Handoff-MCP-v{version}.zip"
    files = {name: (ROOT / name).read_bytes() for name in PACKAGE_FILES}
    manifest = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    files["SHA256SUMS.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w") as archive:
        for name, content in sorted(files.items()):
            member = ZipInfo(name)
            member.compress_type = ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, content)
    return target


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
