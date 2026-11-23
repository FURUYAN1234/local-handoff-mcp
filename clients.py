"""Inspect supported clients and open their own sign-in tools on request."""
from base64 import b64encode
from dataclasses import dataclass
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

from handoff import native_path

LABELS = {"codex": "Codex", "antigravity": "Antigravity",
          "claude-code": "Claude Code", "opencode": "OpenCode"}
WINDOWS_PS = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
WINDOWS_WSL = r"C:\Windows\System32\wsl.exe"
WINDOWS_SCAN = r"""
$ErrorActionPreference = 'SilentlyContinue'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
function Find-App($name) {
  (Get-Command $name -CommandType Application | Select-Object -First 1).Source
}
$codex = Find-App 'codex.exe'
$apps = @(Get-StartApps)
$ag = ($apps | Where-Object Name -EQ 'Antigravity IDE' | Select-Object -First 1).AppID
if (!$ag) { $ag = ($apps | Where-Object Name -EQ 'Antigravity' | Select-Object -First 1).AppID }
$claude = Find-App 'claude.exe'
if (!$claude) { $claude = Find-App 'claude.cmd' }
$open = Find-App 'opencode.exe'
if (!$open) { $open = Find-App 'opencode.cmd' }
$ollama = Find-App 'ollama.exe'
$lms = Find-App 'lms.exe'
if (!$lms) {
  $candidate = Join-Path $env:USERPROFILE '.lmstudio\bin\lms.exe'
  if (Test-Path -LiteralPath $candidate) { $lms = $candidate }
}
$lmapp = ($apps | Where-Object Name -EQ 'LM Studio' | Select-Object -First 1).AppID
function Test-LocalRuntime($url, $property) {
  try {
    $response = Invoke-RestMethod -Uri $url -TimeoutSec 1
    return $null -ne $response.PSObject.Properties[$property]
  } catch { return $false }
}
[ordered]@{
  home = $env:USERPROFILE
  codex = $codex
  'claude-code' = $claude
  opencode = $open
  antigravity = $ag
  ollama = $ollama
  ollama_live = Test-LocalRuntime 'http://127.0.0.1:11434/api/version' 'version'
  lmstudio = $lms -or $lmapp
  lmstudio_live = Test-LocalRuntime 'http://127.0.0.1:1234/api/v1/models' 'models'
} | ConvertTo-Json -Compress
"""
SCAN_TIMEOUT = 12


@dataclass(frozen=True)
class Client:
    key: str
    executable: str | None
    installed: bool
    registered: bool
    auth: str
    windows: bool


def powershell(script):
    encoded = b64encode(script.encode("utf-16-le")).decode("ascii")
    return [str(WINDOWS_PS), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def ps_string(text):
    return "'" + text.replace("'", "''") + "'"


def capture(args, cwd, timeout=SCAN_TIMEOUT):
    try:
        return subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                              encoding="utf-8", errors="replace", check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def windows_inventory(cwd):
    if not WINDOWS_PS.is_file() or not os.environ.get("WSL_DISTRO_NAME"):
        return {}
    result = capture(powershell(WINDOWS_SCAN), cwd)
    if result and result.returncode == 0:
        try:
            value = json.loads(result.stdout.lstrip("\ufeff"))
            return value if isinstance(value, dict) else {}
        except ValueError:
            pass
    return {}


def read_registration(path, keys):
    if path is None:
        return False
    try:
        if path.stat().st_size > 2_000_000:
            return False
        content = path.read_text("utf-8-sig")
        value = tomllib.loads(content) if path.suffix == ".toml" else json.loads(content)
        for key in keys:
            value = value[key]
        return isinstance(value, dict) and value.get("enabled") is not False and value.get("disabled") is not True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def registered(home, key):
    if home is None:
        return False
    if key == "codex":
        return read_registration(home / ".codex/config.toml", ("mcp_servers", "local_handoff"))
    if key == "antigravity":
        return read_registration(home / ".gemini/config/mcp_config.json", ("mcpServers", "local_handoff"))
    if key == "claude-code":
        return read_registration(home / ".claude.json", ("mcpServers", "local_handoff"))
    path = home / ".config/opencode/opencode.json"
    return (read_registration(path, ("mcp", "servers", "local_handoff"))
            or read_registration(path, ("mcp", "local_handoff")))


def command(executable, windows, args):
    if not windows:
        return [executable, *args]
    words = " ".join(ps_string(value) for value in [executable, *args])
    return powershell(
        "$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); "
        f"Set-Location -LiteralPath $env:TEMP; & {words}; exit $LASTEXITCODE"
    )


def auth_state(key, executable, windows, cwd):
    if key == "opencode":
        return "local"
    if key == "antigravity" or not executable:
        return "unknown"
    if key == "codex":
        response = capture(command(executable, windows, ["login", "status"]), cwd, 4)
        if response and response.returncode == 0:
            return "signed-in"
        if response and "not logged in" in (response.stdout + response.stderr).lower():
            return "signed-out"
        return "unknown"

    version = capture(command(executable, windows, ["--version"]), cwd, 4)
    release = re.match(r"(\d+)\.(\d+)\.", version.stdout) if version and version.returncode == 0 else None
    if release and tuple(map(int, release.groups())) >= (2, 1):
        response = capture(command(executable, windows, ["auth", "status"]), cwd, 4)
        if response:
            try:
                logged_in = json.loads(response.stdout.lstrip("\ufeff")).get("loggedIn")
                if isinstance(logged_in, bool):
                    return "signed-in" if logged_in else "signed-out"
            except (ValueError, AttributeError):
                pass
    return "unknown"


def runtime_available(port, path, marker):
    conn = HTTPConnection("127.0.0.1", port, timeout=0.5)
    try:
        conn.request("GET", path)
        reply = conn.getresponse()
        value = json.loads(reply.read(131072)) if reply.status == 200 else None
        return isinstance(value, dict) and marker in value
    except (OSError, ValueError, AttributeError):
        return False
    finally:
        conn.close()


def local_executable(name):
    paths = [entry for entry in os.get_exec_path() if Path(entry).is_absolute()]
    return shutil.which(name, path=os.pathsep.join(paths))


def discover(cwd, *, scan_auth=True):
    inventory = windows_inventory(cwd)
    win_home = native_path(inventory["home"]) if inventory.get("home") else None
    clients = {}
    for key in LABELS:
        windows_app = inventory.get(key)
        linux_app = None if windows_app or key == "antigravity" else local_executable(
            "claude" if key == "claude-code" else key
        )
        executable = windows_app or linux_app
        is_registered = registered(win_home if windows_app else Path.home(), key)
        clients[key] = Client(key, executable, bool(executable), is_registered,
                              auth_state(key, executable, bool(windows_app), cwd) if scan_auth else "unknown",
                              bool(windows_app))
    runtimes = {}
    for key, label, executable, port, path, marker in (
        ("ollama", "Ollama", "ollama", 11434, "/api/version", "version"),
        ("lmstudio", "LM Studio", "lms", 1234, "/api/v1/models", "models"),
    ):
        live = inventory.get(key + "_live") or runtime_available(port, path, marker) if scan_auth else False
        installed = live or inventory.get(key) or local_executable(executable)
        runtimes[label] = bool(installed), bool(live)
    return clients, runtimes


def configure_claude(client, cwd):
    if not client.executable:
        return False
    launcher = cwd / "launch.py"
    if not launcher.is_file() or not (cwd / "current.json").is_file():
        return False
    start = (WINDOWS_WSL, "-d", os.environ.get("WSL_DISTRO_NAME", "Ubuntu"), "--exec",
             "/usr/bin/python3") if client.windows else ("/usr/bin/python3",)
    args = ["mcp", "add", "--scope", "user", "--transport", "stdio", "local_handoff", "--",
            *start, "-B", str(launcher), "--host", "claude-code", "serve"]
    result = capture(command(client.executable, client.windows, args), cwd)
    return result is not None and result.returncode == 0


def open_sign_in(client, cwd):
    if not client.executable or client.key == "opencode":
        return False
    if client.key == "antigravity":
        if not re.fullmatch(r"[\w.{}!\-]+", client.executable, re.ASCII):
            return False
        script = "Start-Process explorer.exe -ArgumentList " + ps_string(
            "shell:AppsFolder\\" + client.executable
        )
    else:
        args = "'login'" if client.key == "codex" else ""
        launcher = f"& {ps_string(client.executable)} {args}"
        if client.key == "claude-code":
            launcher = "Write-Host 'Claude Code: run /login to sign in.'; " + launcher
        if not client.windows:
            distribution = os.environ.get("WSL_DISTRO_NAME")
            if not distribution or not WINDOWS_PS.is_file():
                return False
            script = "Start-Process " + ps_string(WINDOWS_WSL) + " -ArgumentList " + ps_string(
                "-d " + subprocess.list2cmdline([distribution, "--cd", str(cwd), "--exec",
                                                client.executable, *([] if not args else ["login"])])
            ) + " -WindowStyle Normal"
        else:
            encoded = b64encode(launcher.encode("utf-16-le")).decode("ascii")
            script = "Start-Process -FilePath $PSHOME\\powershell.exe -WorkingDirectory $env:TEMP " \
                     f"-ArgumentList '-NoProfile -NoExit -EncodedCommand {encoded}' -WindowStyle Normal"
    result = capture(powershell(script), cwd, 8)
    return result is not None and result.returncode == 0
