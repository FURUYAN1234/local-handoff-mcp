"""Inspect supported clients and open their own sign-in tools on request."""
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
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
from managed_cli import managed_opencode

LABELS = {"codex": "Codex", "antigravity": "Antigravity",
          "claude-code": "Claude Code", "opencode": "OpenCode", "strata": "Strata", "muse-code": "Muse Code"}
WINDOWS_PS = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
WINDOWS_CURL = Path("/mnt/c/Windows/System32/curl.exe")
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
$muse = Find-App 'muse.exe'
$open = Find-App 'opencode.exe'
if (!$open) { $open = Find-App 'opencode.cmd' }
$openDesktop = ($apps | Where-Object { $_.Name -in 'OpenCode','OpenCode Desktop' } | Select-Object -First 1).AppID
$codexDesktop = ($apps | Where-Object { $_.Name -eq 'Codex' -or $_.AppID -like 'OpenAI.Codex_*' } | Select-Object -First 1).AppID
$claudeDesktop = ($apps | Where-Object { $_.Name -in 'Claude','Claude Desktop' } | Select-Object -First 1).AppID
$agCli = Find-App 'agy.exe'
if (!$agCli) { $agCli = Find-App 'agy.cmd' }
$ollama = Find-App 'ollama.exe'
if (!$ollama) {
  $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
  if (Test-Path -LiteralPath $candidate) { $ollama = $candidate }
}
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
  'muse-code' = $muse
  opencode = $open
  opencode_desktop = $openDesktop
  codex_desktop = $codexDesktop
  'claude-code_desktop' = $claudeDesktop
  antigravity = $ag
  antigravity_desktop = $ag
  antigravity_cli = $agCli
  ollama = $ollama
  ollama_live = Test-LocalRuntime 'http://127.0.0.1:11434/api/version' 'version'
  lmstudio = $lms -or $lmapp
  lmstudio_cli = $lms
  lmstudio_active = $null -ne (Get-Process -Name 'LM Studio','llmster' | Select-Object -First 1)
  lmstudio_live = Test-LocalRuntime 'http://127.0.0.1:1234/api/v1/models' 'models'
} | ConvertTo-Json -Compress
"""
SCAN_TIMEOUT = 12


@dataclass(frozen=True)
class Client:
    key: str
    executable: str | None
    installed: bool
    registered: bool | None
    auth: str
    windows: bool
    browser_login: bool = False
    desktop_installed: bool = False
    cli_installed: bool = False


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
    if key == "muse-code":
        path = home / ".config/muse/settings.json"
        return (read_registration(path, ("mcp_servers", "local_handoff"))
                or read_registration(path, ("mcpServers", "local_handoff")))
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


def claude_auth_command(executable, windows, cwd):
    response = capture(command(executable, windows, ["--help"]), cwd, 5)
    return bool(response and response.returncode == 0
                and re.search(r"(?m)^[ \t]+auth(?:[ \t]+\[options\])?[ \t]{2,}\S", response.stdout))


def auth_state(key, executable, windows, cwd, browser_login=False):
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

    if browser_login:
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


def windows_ollama_available(cwd):
    if not os.environ.get("WSL_DISTRO_NAME") or not WINDOWS_CURL.is_file():
        return False
    result = capture([str(WINDOWS_CURL), "-q", "--silent", "--fail", "--noproxy", "*",
                      "--max-time", "2", "http://127.0.0.1:11434/api/version"], cwd, 4)
    if result is None or result.returncode:
        return False
    try:
        version = json.loads(result.stdout)["version"]
        return isinstance(version, str) and bool(version.strip())
    except (ValueError, TypeError, KeyError):
        return False


def local_executable(name):
    paths = [entry for entry in os.get_exec_path() if Path(entry).is_absolute()]
    return shutil.which(name, path=os.pathsep.join(paths))


def lmstudio_status(message):
    try:
        status = json.loads(message)
        running, port = status["running"], status["port"]
        if type(running) is bool and type(port) is int and 1 <= port <= 65535:
            return running, port
    except (TypeError, ValueError, KeyError):
        pass
    return None, None


def strata_install(home):
    if local_executable("strata"):
        return True
    base = home / "Codex/tools/strata"
    try:
        release = json.loads((base / "active-release.json").read_text("utf-8"))
        app = Path(release["app"]).resolve()
        return (isinstance(release["app_version"], str) and app.is_relative_to(base.resolve())
                and (app / "host/server/index.mjs").is_file())
    except (OSError, KeyError, TypeError, ValueError):
        return False


def probe_lmstudio(cwd, inventory):
    if not inventory.get("lmstudio_active") or not inventory.get("lmstudio_cli"):
        return None, None
    args = ["server", "status", "--json", "--quiet"]
    response = capture(command(inventory["lmstudio_cli"], True, args), cwd, 12)
    if response and response.returncode == 0:
        return lmstudio_status(response.stdout.strip())
    return None, None


def discover(cwd, *, scan_auth=True):
    inventory = windows_inventory(cwd)
    win_home = native_path(inventory["home"]) if inventory.get("home") else None
    with ThreadPoolExecutor(max_workers=1) as worker:
        lm_status = worker.submit(probe_lmstudio, cwd, inventory) if scan_auth else None
        clients = {}
        for key in LABELS:
            if key == "strata":
                clients[key] = Client(key, None, strata_install(Path.home()), None, "local", False)
                continue
            windows_app = inventory.get(key)
            linux_app = None if windows_app or key == "antigravity" else local_executable(
                {"claude-code": "claude", "muse-code": "muse"}.get(key, key)
            )
            if key == "muse-code" and not windows_app and not linux_app:
                official = Path.home() / ".local/bin/muse"
                if official.is_file() and os.access(official, os.X_OK):
                    linux_app = str(official)
            if key == "opencode" and not windows_app and not linux_app:
                managed = managed_opencode(cwd)
                if managed.is_file() and os.access(managed, os.X_OK):
                    linux_app = str(managed)
            executable = windows_app or linux_app
            desktop = bool(inventory.get(key + "_desktop"))
            cli = (bool(executable) if key != "antigravity"
                   else bool(inventory.get("antigravity_cli") or local_executable("agy")))
            is_registered = registered(win_home if windows_app or desktop else Path.home(), key)
            windows = bool(windows_app)
            browser_login = bool(scan_auth and executable and key == "claude-code"
                                 and claude_auth_command(executable, windows, cwd))
            authentication = auth_state(key, executable, windows, cwd, browser_login) if scan_auth else "unknown"
            clients[key] = Client(key, executable, bool(executable) or desktop or cli,
                                  is_registered, authentication, windows, browser_login, desktop, cli)
    runtimes = {}
    for key, label, executable, port, path, marker in (
        ("ollama", "Ollama", "ollama", 11434, "/api/version", "version"),
        ("lmstudio", "LM Studio", "lms", 1234, "/api/v1/models", "models"),
    ):
        live = inventory.get(key + "_live") or runtime_available(port, path, marker) if scan_auth else False
        if key == "ollama" and scan_auth and not live:
            live = windows_ollama_available(cwd)
        running, configured_port = None, None
        if key == "lmstudio" and scan_auth and inventory.get("lmstudio_active") and inventory.get("lmstudio_cli"):
            running, configured_port = lm_status.result()
        installed = configured_port or live or inventory.get(key) or local_executable(executable)
        live_port = configured_port if running else (port if live else None)
        runtimes[label] = bool(installed), live_port, port, configured_port if running is False else None
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


def configure_muse(client, cwd):
    launcher = cwd / "launch.py"
    if not client.executable or not launcher.is_file() or not (cwd / "current.json").is_file():
        return False
    scan_args = ["mcp", "list", "--user", "--json"]
    result = capture(command(client.executable, client.windows, scan_args), cwd)
    if result is None or result.returncode != 0:
        return False
    try:
        servers = json.loads(result.stdout.lstrip("\ufeff"))["servers"]
        if not isinstance(servers, list) or any(not isinstance(server, dict) for server in servers):
            return False
        if any(server.get("name") == "local_handoff" for server in servers):
            return False
    except (ValueError, KeyError, TypeError):
        return False
    start = ([WINDOWS_WSL, "-d", os.environ.get("WSL_DISTRO_NAME", "Ubuntu"), "--exec", "/usr/bin/python3"]
             if client.windows else ["/usr/bin/python3"])
    entry = {"transport": "stdio", "command": start[0], "mode": "optional",
             "args": [*start[1:], "-B", str(launcher), "--host", "muse-code", "serve"]}
    args = ["mcp", "add-json", "local_handoff", json.dumps(entry), "--user"]
    result = capture(command(client.executable, client.windows, args), cwd)
    return result is not None and result.returncode == 0


def open_sign_in(client, cwd):
    if not client.executable or client.key not in ("codex", "antigravity", "claude-code"):
        return None
    notice = "browser-login"
    if client.key == "antigravity":
        notice = "antigravity-opened"
        if not re.fullmatch(r"[\w.{}!\-]+", client.executable, re.ASCII):
            return False
        script = "Start-Process explorer.exe -ArgumentList " + ps_string(
            "shell:AppsFolder\\" + client.executable
        )
    else:
        args = ["login"]
        window_style = "Minimized"
        if client.key == "claude-code":
            if claude_auth_command(client.executable, client.windows, cwd):
                args = ["auth", "login"]
            else:
                args = []
                window_style = "Normal"
                notice = "claude-terminal"
        words = " ".join(ps_string(arg) for arg in (client.executable, *args))
        launcher = f"& {words}"
        if notice == "claude-terminal":
            launcher = "Write-Host 'First launch: select a theme and sign-in method. Existing setup: type /login.'; " + launcher
        if not client.windows:
            distribution = os.environ.get("WSL_DISTRO_NAME")
            if not distribution or not WINDOWS_PS.is_file():
                return False
            script = "Start-Process " + ps_string(WINDOWS_WSL) + " -ArgumentList " + ps_string(
                "-d " + subprocess.list2cmdline([distribution, "--cd", str(cwd), "--exec",
                                                client.executable, *args])
            ) + " -WindowStyle " + window_style
        else:
            encoded = b64encode(launcher.encode("utf-16-le")).decode("ascii")
            script = "Start-Process -FilePath $PSHOME\\powershell.exe -WorkingDirectory $env:TEMP " \
                     f"-ArgumentList '-NoProfile -NoExit -EncodedCommand {encoded}' -WindowStyle {window_style}"
    result = capture(powershell(script), cwd, 8)
    return notice if result is not None and result.returncode == 0 else None
