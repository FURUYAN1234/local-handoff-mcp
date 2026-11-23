"""Install the official OpenCode binary into Local Handoff MCP's private WSL directory."""
from base64 import b64decode
from hashlib import sha512
from pathlib import Path
from platform import machine, system
import hmac
import os
import shutil
import tarfile
import tempfile
import time
from urllib.request import urlopen

OPENCODE_VERSION = "2.4.0"
ARCHIVE_URL = "https://registry.npmjs.org/@opencode/cli-linux-x64/-/cli-linux-x64-2.4.0.tgz"
ARCHIVE_HASH = b64decode("mH7h8HAuSMH+ggFY1ogihbQy1xLMX1L7fE96iqRTV9c0H6apPoTbPgEJKV0qbJGy60p3jBsMvmeMVw67SoZCrw==")
ARCHIVE_LIMIT = 180 * 1024 * 1024
BINARY_LIMIT = 450 * 1024 * 1024


def managed_opencode(install_dir):
    return Path(install_dir) / "bin" / "opencode"


def install_supported():
    return system() == "Linux" and machine() == "x86_64"


def download_archive(target):
    digest = sha512()
    total, deadline = 0, time.monotonic() + 180
    with urlopen(ARCHIVE_URL, timeout=15) as response, target.open("wb") as output:
        if response.geturl() != ARCHIVE_URL:
            raise ValueError("Unexpected package location")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > ARCHIVE_LIMIT or time.monotonic() > deadline:
                raise ValueError("Package transfer exceeded its limits")
            digest.update(chunk)
            output.write(chunk)
    if not hmac.compare_digest(digest.digest(), ARCHIVE_HASH):
        raise ValueError("Package integrity check failed")


def install_opencode(install_dir):
    if not install_supported():
        raise ValueError("This build supports OpenCode installation on x64 WSL")
    target = managed_opencode(install_dir)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".opencode-install-", dir=target.parent) as temp:
        download = Path(temp) / "package.tgz"
        candidate = Path(temp) / "opencode"
        download_archive(download)
        with tarfile.open(download, "r:gz") as archive:
            member = archive.getmember("package/bin/opencode")
            if not member.isfile() or not 0 < member.size <= BINARY_LIMIT:
                raise ValueError("Invalid OpenCode binary")
            with archive.extractfile(member) as source, candidate.open("wb") as output:
                shutil.copyfileobj(source, output)
        candidate.chmod(0o700)
        os.replace(candidate, target)
    return target
