"""`fact-checker setup`, `doctor` and `key set`: the tools the helper needs, the helper started at every login, and
the keys."""
import getpass
import json
import os
import platform
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from fact_checker.adapters import whisper
from fact_checker.adapters.screenshot import find_chrome
from fact_checker.adapters.llm_codex_cli import CHATGPT_CODEX
from fact_checker.server import (ROLES, key_names, ports, provider, read_env, role, secret, speech_cli,
                                 write_key)
from fact_checker.store import default_home

LABEL = "com.fact-checker.helper"
UNIT = "fact-checker.service"
HERE = Path(__file__).parent
WAIT = 5.0  # seconds that setup waits for an old helper to stop and for the login helper to answer
INSTALL_CLAUDE = "curl -fsSL https://claude.ai/install.sh | bash"
# The Claude app keeps its own Claude Code in a folder per version, which the next update removes.
VERSIONED_CLAUDE = re.compile(r"/Claude/claude-code/\d[^/]*/")
NO_AGENT_CLI = ("provider: no agent CLI logged in · fix: claude auth login (Claude subscription) or codex login "
                "(ChatGPT subscription); to install one, see INSTALL-AGENT.md")


@dataclass
class Check:
    name: str
    state: str
    fix: str = ""
    ok: bool = True

    def __str__(self) -> str:
        return f"{self.name}: {self.state}" + (f" · fix: {self.fix}" if self.fix else "")


def _tool(name: str, fix: str) -> Check:
    return Check(name, "ok") if shutil.which(name) else Check(name, "missing", fix, ok=False)


def _claude() -> Check:
    found = shutil.which("claude")
    if not found:
        return Check("claude", "missing", INSTALL_CLAUDE, ok=False)
    if VERSIONED_CLAUDE.search(os.path.realpath(found)):
        return Check("claude", "inside the Claude app, it moves on each update", INSTALL_CLAUDE, ok=False)
    status = subprocess.run(["claude", "auth", "status", "--json"], capture_output=True, text=True)
    try:
        logged_in = json.loads(status.stdout).get("loggedIn") is True
    except json.JSONDecodeError:
        logged_in = False
    return Check("claude", "logged in") if logged_in else Check("claude", "not logged in", "claude auth login", ok=False)


def codex_cli() -> str | None:
    """The Codex command: CODEX_BIN or `codex` on PATH, else the one that ships inside the ChatGPT app."""
    return shutil.which(os.environ.get("CODEX_BIN", "codex")) or (str(CHATGPT_CODEX) if CHATGPT_CODEX.is_file()
                                                                   else None)


def _codex() -> Check:
    codex = codex_cli()
    if not codex:
        return Check("codex", "missing", "install Codex CLI, or set CODEX_BIN", ok=False)
    status = subprocess.run([codex, "login", "status"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return Check("codex", "logged in") if status.returncode == 0 else Check("codex", "not logged in", "codex login", ok=False)


def _llm(name: str) -> list[Check]:
    """The command of a subscription provider; an API provider needs none."""
    return {"claude": [_claude()], "codex": [_codex()]}.get(name, [])


def _keys(home: Path) -> list[Check]:
    """Each key that the roles need, by its variable name only."""
    return [Check(v, "set") if secret(home, v) else Check(v, "missing", f"add {v}=<key> to {home / '.env'}", ok=False)
            for v in key_names(home)]


def tools(system: str, home: Path) -> list[Check]:
    """The tools the helper needs: setup installs nothing while one is missing."""
    mac = system == "Darwin"
    return [
        *[c for name in dict.fromkeys(role(home, r)["provider"] for r in ROLES) for c in _llm(name)],
        _tool("uv", "curl -LsSf https://astral.sh/uv/install.sh | sh"),
        _tool("yt-dlp", "uv tool install yt-dlp"),
        _tool("ffmpeg", "brew install ffmpeg" if mac else "sudo apt install ffmpeg (or your distribution's package)"),
        Check("chrome", "ok") if find_chrome(system) else
        Check("chrome", "missing", "install Google Chrome" if mac else "install Google Chrome or Chromium", ok=False),
    ]


SANDBOX_FIX = ("run fact-checker setup, then fact-checker doctor, outside the sandbox, "
               "with the person's approval")


def health(port: int) -> dict | None:
    """What answers GET /health on a local port: the helper's JSON, {} for another program, None for nothing.
    PermissionError means the agent's sandbox blocks local connections."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as res:
            answer = json.loads(res.read())
    except urllib.error.URLError as e:
        if isinstance(e.reason, PermissionError):
            raise e.reason
        return {} if isinstance(e, urllib.error.HTTPError) else None
    except PermissionError:
        raise
    except (OSError, ValueError):  # a program that answers, but not with JSON
        return {}
    return answer if isinstance(answer, dict) and answer.get("app") == "fact-checker" else {}


def _helper(ports) -> tuple[Check, dict]:
    """The helper found by /health over `ports`, and its answer ({} without one); another program on a port is not
    the helper."""
    found = {}
    try:
        for port in ports:
            found[port] = health(port)
            if found[port]:
                break
    except PermissionError:
        return Check("helper", "blocked by the agent's sandbox", SANDBOX_FIX, ok=False), {}
    helper = next(((p, h) for p, h in found.items() if h), None)
    if helper and not helper[1]["writable"]:
        return Check("helper", f"running on port {helper[0]}, cannot write {helper[1]['home']}",
                     f"stop it, then {SANDBOX_FIX}", ok=False), helper[1]
    if helper:
        return Check("helper", f"running on port {helper[0]}"), helper[1]
    foreign = next((p for p, h in found.items() if h == {}), None)
    if foreign is not None:
        return Check("helper", f"another program holds port {foreign}", "fact-checker setup", ok=False), {}
    return Check("helper", f"not running on port {ports[0]}", "fact-checker setup", ok=False), {}


def seen_by_helper(check: Check, tools: dict) -> Check:
    """A tool this terminal finds but the running helper does not: setup gives the helper this terminal's PATH."""
    if check.ok and tools.get(check.name) is False:
        return Check(check.name, f"the helper does not find {check.name}", "fact-checker setup", ok=False)
    return check


def doctor(port: int | None, as_json: bool = False) -> int:
    system = platform.system()
    home = default_home()
    env = read_env(home) | os.environ
    engine = speech_cli()
    roles = {name: role(home, name) for name in ROLES}
    helper, answer = _helper([port] if port else ports())
    checks = [
        Check("provider", provider(home)),
        Check("models", ", ".join(f"{name} {r['model'] or 'account default'}" for name, r in roles.items())),
        *[Check(f"role {name}", " · ".join(x for x in (r["provider"], r["model"] or "account default", r["base_url"]) if x))
          for name, r in roles.items()],
        *_keys(home),
        *[seen_by_helper(c, answer.get("tools", {})) for c in tools(system, home)],
        helper,
        Check("speech to text", ("mlx-whisper" if engine == whisper.CLI else "faster-whisper") if engine else "missing",
              "" if engine else "install uv (see uv above)"),
        Check("speaker separation", "on") if env.get("HF_TOKEN") else
        Check("speaker separation", "off (optional)", f"add HF_TOKEN=<token> to {default_home() / '.env'}"),
        Check("published fact-checks", "on") if env.get("FACT_CHECK_API_KEY") else
        Check("published fact-checks", "off (optional)", f"add FACT_CHECK_API_KEY=<key> to {default_home() / '.env'}"),
    ]
    ok = all(c.ok for c in checks)
    if as_json:
        print(json.dumps({"ok": ok, "checks": [asdict(c) for c in checks]}, ensure_ascii=False, indent=1))
        return 0 if ok else 1
    for check in checks:
        print(check)
    if provider(home) == "codex":
        print("Run `codex debug models` to see the models your plan allows.")
    return 0 if ok else 1


def launchd_plist(command: list[str], path: str, log: Path) -> bytes:
    return plistlib.dumps({"Label": LABEL, "ProgramArguments": command, "RunAtLoad": True,
                           # Restarted after a crash, not after the clean stop of a helper with every port taken.
                           "KeepAlive": {"SuccessfulExit": False},
                           "EnvironmentVariables": {"PATH": path},
                           "StandardOutPath": str(log), "StandardErrorPath": str(log)})


def systemd_unit(command: list[str], path: str) -> str:
    return (f"[Unit]\nDescription=fact-checker helper\n\n"
            f"[Service]\nExecStart={' '.join(command)}\nEnvironment=PATH={path}\nRestart=on-failure\n\n"
            f"[Install]\nWantedBy=default.target\n")


def logged_in_cli() -> str | None:
    """The first agent CLI that is logged in: Claude Code, then Codex."""
    return next((name for name, check in (("claude", _claude), ("codex", _codex)) if check().ok), None)


def settings_files(home: Path, provider: str | None) -> None:
    """Writes a settings file that names the provider, from the commented example, and copies the commented keys
    file; an existing file stays."""
    home.mkdir(parents=True, exist_ok=True)
    config, keys = home / "config.toml", home / ".env"
    if provider and not config.exists():
        example = (HERE / "config.example.toml").read_text()
        config.write_text(example.replace('# provider = "claude"', f'provider = "{provider}"', 1))
        print(f"settings: {config} (provider {provider}; edit it to change provider or models)")
    if not keys.exists():
        shutil.copy(HERE / "env.example", keys)
        print(f"keys: {keys} (add a key with fact-checker key set <NAME>)")


def write_provider(home: Path, name: str) -> None:
    """Writes `provider = "<name>"` into `<home>/config.toml`: in place of its line above every table, or first; every
    other line stays."""
    path = home / "config.toml"
    text = path.read_text()
    table = re.search(r"(?m)^\[", text)
    end = table.start() if table else len(text)
    line = f'provider = "{name}"'
    head, found = re.subn(r"(?m)^provider\s*=.*$", line, text[:end], count=1)
    path.write_text(head + text[end:] if found else f"{line}\n{text}")


def set_provider(home: Path, name: str | None) -> int:
    """Prints the provider in use; with `name`, a logged-in subscription, writes it into the settings and restarts
    the login helper."""
    if not name:
        print(f"provider: {provider(home)}")
        return 0
    check = _llm(name)[0]
    if not check.ok:
        print(check)
        return 1
    settings_files(home, name)
    write_provider(home, name)
    restart = {"Darwin": ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{LABEL}"],
               "Linux": ["systemctl", "--user", "restart", UNIT]}.get(platform.system())
    restarted = restart and subprocess.run(restart, capture_output=True).returncode == 0
    print(f"provider: {name}" + ("; the helper restarted" if restarted else " · fix: fact-checker setup"))
    return 0


def set_key(home: Path, name: str) -> int:
    """Reads a key with a hidden prompt and writes `<name>=<key>` into `<home>/.env`, in place of the line of that
    name, commented or not; the file is readable only by the person."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        print(f"key: {name} is not a variable name, such as HF_TOKEN")
        return 1
    value = getpass.getpass(f"{name} (what you type stays hidden): ").strip()
    if not value:
        print("key: nothing typed, nothing saved")
        return 1
    write_key(home, name, value)
    print(f"{name}: saved in {home / '.env'}. Run fact-checker setup to restart the helper with it.")
    return 0


def extension(home: Path) -> Path:
    """Copies the built extension of the package to `<home>/extension`, the folder that Chrome loads."""
    target = home / "extension"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(HERE / "extension", target)
    return target


def stop_helpers(home: Path, ports) -> None:
    """Stops each fact-checker helper of this home that answers on `ports`, such as one an agent started by hand;
    another program, or the helper of another home, keeps running."""
    for port in ports:
        found = health(port)
        if found and found["home"] == str(home) and found["pid"] != os.getpid():
            os.kill(found["pid"], signal.SIGTERM)
            wait(lambda: health(port) is None)
            print(f"helper: stopped the old helper on port {port}")


def wait(test, seconds: float = WAIT) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(0.1)
    return False


def setup(port: int | None, name: str | None = None) -> int:
    """Checks the tools, then installs the helper as a launchd agent (macOS) or a systemd user service (Linux).
    `name` is the subscription to read with; without it, a new settings file names the first one logged in."""
    system = platform.system()
    home = default_home()
    if name and not (check := _llm(name)[0]).ok:
        print(check)
        return 1
    found = name or (None if (home / "config.toml").exists() else logged_in_cli())
    if not found and not (home / "config.toml").exists():
        print(NO_AGENT_CLI)
        return 1
    settings_files(home, found)
    if name:
        write_provider(home, name)
    missing = [c for c in tools(system, home) if not c.ok]
    if missing:
        for check in missing:
            print(check)
        return 1
    folder = extension(home)
    # An autostarted helper gets a bare PATH: it keeps the one of this shell, where every tool was found.
    command = [sys.executable, "-m", "fact_checker.cli", "serve", *(["--port", str(port)] if port else [])]
    path, tries = os.environ["PATH"], [port] if port else ports()
    codex = codex_cli()
    if codex and "codex" in {role(home, r)["provider"] for r in ROLES} and \
            str(Path(codex).parent) not in path.split(os.pathsep):
        path += os.pathsep + str(Path(codex).parent)  # such as the Codex inside the ChatGPT app
    if system == "Darwin":
        agent = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        agent.parent.mkdir(parents=True, exist_ok=True)
        default_home().mkdir(parents=True, exist_ok=True)
        agent.write_bytes(launchd_plist(command, path, default_home() / "server.log"))
        domain = f"gui/{os.getuid()}"
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
        stop_helpers(home, tries)
        started = subprocess.run(["launchctl", "bootstrap", domain, str(agent)], capture_output=True, text=True)
        if started.returncode:  # such as "Bootstrap failed: 5: Input/output error" in an agent's sandbox
            print(f"helper: launchd refused it ({started.stderr.strip()}) · fix: {SANDBOX_FIX}")
            return 1
        print(f"helper: starts at login ({agent})")
    elif system == "Linux":
        unit = Path.home() / ".config" / "systemd" / "user" / UNIT
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(systemd_unit(command, path))
        subprocess.run(["systemctl", "--user", "stop", UNIT], capture_output=True)
        stop_helpers(home, tries)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", UNIT], check=True)
        print(f"helper: starts at login ({unit})")
    else:
        print(f"helper: no autostart on {system} · fix: run fact-checker serve by hand")
        return 1
    running = None

    def answers() -> bool:
        nonlocal running
        running = next((p for p in tries if (health(p) or {}).get("home") == str(home)), None)
        return running is not None
    print(f"helper: running on port {running}" if wait(answers) else
          f"helper: not answering yet · fix: fact-checker doctor (log: {home / 'server.log'})")
    print(f"next: load {folder} in Chrome (chrome://extensions → Developer mode → Load unpacked), "
          "then run fact-checker doctor")
    return 0
