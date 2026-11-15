"""S21 A1 · Setup checks the tools and starts the helper at every login

Story: A tester installs the helper with `uv tool install` and runs `fact-checker setup`. On a Linux machine without
yt-dlp, setup prints one line, "yt-dlp: missing", with its fix, "uv tool install yt-dlp", and installs nothing. Once
yt-dlp is there, setup installs a systemd user service on Linux, or a launchd agent on macOS, that runs
`fact-checker serve` at login. `fact-checker doctor` prints one line per check, such as "helper: not running on port
8765 · fix: fact-checker setup", and "speaker separation: off (optional)" without a Hugging Face token.

Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME). PATH holds only a folder of fake commands:
`claude` (answers `auth status --json` with loggedIn from FAKE_CLAUDE_LOGGED), `uv`, `yt-dlp`, `ffmpeg`, `chromium`,
and `launchctl` and `systemctl`, which only write their arguments to a log; the real ones never run. The operating
system is set by replacing platform.system. The helper port is a free local port; a case that needs a running helper
starts a small HTTP server on it. The last case installs the package for real with `uv tool install` into temporary
tool folders.
"""
import json
import os
import platform
import plistlib
import shutil
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from fact_checker import cli

HELPER_SRC = Path(__file__).parents[2] / "src" / "helper"
REAL_HOME = Path.home()

FAKE_CLAUDE = """\
import json, os, sys
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": os.environ.get("FAKE_CLAUDE_LOGGED") == "1"}))
"""
FAKE_RECORDER = """\
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\\n")
"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A machine with every tool; a test removes one with `missing`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, code in {"claude": FAKE_CLAUDE, "launchctl": FAKE_RECORDER, "systemctl": FAKE_RECORDER,
                       "uv": "", "yt-dlp": "", "ffmpeg": "", "chromium": ""}.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    user_home, helper_home = tmp_path / "user", tmp_path / "helper"
    user_home.mkdir()
    helper_home.mkdir()
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(helper_home))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_CLAUDE_LOGGED", "1")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)

    class Machine:
        port = free_port()
        bin = bin_dir
        user = user_home
        helper = helper_home

        def system(self, name):
            monkeypatch.setattr(platform, "system", lambda: name)

        def missing(self, tool):
            (bin_dir / tool).unlink()

        def calls(self):
            return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []

    return Machine()


def run(monkeypatch, capsys, *args) -> tuple[int, list[str]]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out.splitlines()


def line(lines, start):
    found = [x for x in lines if x.startswith(start)]
    assert len(found) == 1, f"FAIL S21 A1 · one line starting {start!r}: {lines}"
    return found[0]


def test_setup_and_doctor(machine, monkeypatch, capsys, tmp_path):
    real_agent = REAL_HOME / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist"
    real_unit = REAL_HOME / ".config" / "systemd" / "user" / "fact-checker.service"
    before = (real_agent.exists(), real_unit.exists())
    unit = machine.user / ".config" / "systemd" / "user" / "fact-checker.service"
    agent = machine.user / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist"

    # Case 1 · Linux without yt-dlp, setup → one line with the fix, exit 1, no unit, no systemctl call
    machine.system("Linux")
    machine.missing("yt-dlp")
    code, out = run(monkeypatch, capsys, "setup", "--port", str(machine.port))
    assert code == 1, f"FAIL S21 A1 · setup exit {code} with yt-dlp missing"
    assert line(out, "yt-dlp:") == "yt-dlp: missing · fix: uv tool install yt-dlp"
    assert not unit.exists() and machine.calls() == [], "FAIL S21 A1 · setup installed with a tool missing"

    # Case 2 · Linux with every tool, setup → a systemd user unit that serves on the port at login, enabled now
    (machine.bin / "yt-dlp").write_text(f"#!{sys.executable}\n")
    (machine.bin / "yt-dlp").chmod(0o755)
    code, out = run(monkeypatch, capsys, "setup", "--port", str(machine.port))
    assert code == 0, f"FAIL S21 A1 · setup exit {code}: {out}"
    text = unit.read_text()
    exec_start = next((x for x in text.splitlines() if x.startswith("ExecStart=")), "")
    assert exec_start.endswith(f"serve --port {machine.port}"), f"FAIL S21 A1 · ExecStart: {text}"
    assert f"Environment=PATH={machine.bin}" in text, f"FAIL S21 A1 · the unit has no PATH: {text}"
    assert "WantedBy=default.target" in text, f"FAIL S21 A1 · the unit does not start at login: {text}"
    assert ["systemctl", "--user", "daemon-reload"] in machine.calls(), f"FAIL S21 A1 · {machine.calls()}"
    assert ["systemctl", "--user", "enable", "--now", "fact-checker.service"] in machine.calls(), \
        f"FAIL S21 A1 · {machine.calls()}"

    # Case 3 · macOS, setup → a launchd agent that serves on the port at login and stays up, loaded now
    machine.system("Darwin")
    code, out = run(monkeypatch, capsys, "setup", "--port", str(machine.port))
    assert code == 0, f"FAIL S21 A1 · setup exit {code} on macOS: {out}"
    plist = plistlib.loads(agent.read_bytes())
    assert plist["ProgramArguments"][-3:] == ["serve", "--port", str(machine.port)], \
        f"FAIL S21 A1 · ProgramArguments {plist['ProgramArguments']}"
    assert plist["RunAtLoad"] is True and plist["KeepAlive"] is True, "FAIL S21 A1 · the agent does not stay up"
    assert plist["EnvironmentVariables"]["PATH"] == str(machine.bin), "FAIL S21 A1 · the agent has no PATH"
    assert ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(agent)] in machine.calls(), \
        f"FAIL S21 A1 · {machine.calls()}"

    # Case 4 · doctor, Claude logged out, no helper, no token → one line each with its fix, exit 1
    machine.system("Linux")
    monkeypatch.setenv("FAKE_CLAUDE_LOGGED", "0")
    machine.missing("chromium")
    code, out = run(monkeypatch, capsys, "doctor", "--port", str(machine.port))
    assert code == 1, f"FAIL S21 A1 · doctor exit {code} with problems"
    assert line(out, "claude:") == "claude: not logged in · fix: claude auth login"
    assert line(out, "chrome:").startswith("chrome: missing · fix: "), f"FAIL S21 A1 · {out}"
    assert line(out, "helper:") == f"helper: not running on port {machine.port} · fix: fact-checker setup"
    assert line(out, "speaker separation:").startswith("speaker separation: off (optional)"), f"FAIL S21 A1 · {out}"
    assert line(out, "speech to text:") == "speech to text: faster-whisper"

    # Case 5 · doctor, everything there, the token in the helper home's .env, a helper on the port → exit 0
    monkeypatch.setenv("FAKE_CLAUDE_LOGGED", "1")
    (machine.bin / "chromium").write_text(f"#!{sys.executable}\n")
    (machine.bin / "chromium").chmod(0o755)
    (machine.helper / ".env").write_text("HF_TOKEN=invented\n")
    server = ThreadingHTTPServer(("127.0.0.1", machine.port), BaseHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        code, out = run(monkeypatch, capsys, "doctor", "--port", str(machine.port))
    finally:
        server.shutdown()
    assert code == 0, f"FAIL S21 A1 · doctor exit {code}: {out}"
    assert line(out, "helper:") == f"helper: running on port {machine.port}"
    assert line(out, "speaker separation:") == "speaker separation: on"
    assert "HF_TOKEN" not in os.environ, "FAIL S21 A1 · doctor leaked the token into the environment"
    assert (real_agent.exists(), real_unit.exists()) == before, "FAIL S21 A1 · setup wrote into the real home"


def test_uv_tool_install(tmp_path):
    # Case 6 · uv tool install from the repo → a fact-checker command whose package holds its data files
    uv = shutil.which("uv")
    assert uv, "FAIL S21 A1 · uv is not installed on this machine"
    cache = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True).stdout.strip()
    env = os.environ | {"UV_CACHE_DIR": cache, "UV_TOOL_DIR": str(tmp_path / "tools"), "UV_TOOL_BIN_DIR": str(tmp_path / "bin"),
                        "HOME": str(tmp_path), "FACT_CHECKER_HOME": str(tmp_path / "helper")}
    install = subprocess.run([uv, "tool", "install", "--quiet", str(HELPER_SRC)], env=env, capture_output=True, text=True)
    assert install.returncode == 0, f"FAIL S21 A1 · uv tool install: {install.stderr[-400:]}"
    for name in ("thresholds.json", "summary.html"):
        assert list((tmp_path / "tools").rglob(f"fact_checker/{name}")), f"FAIL S21 A1 · the package lacks {name}"
    doctor = subprocess.run([str(tmp_path / "bin" / "fact-checker"), "doctor", "--port", str(free_port())],
                            env=env, capture_output=True, text=True)
    assert "helper: not running" in doctor.stdout, f"FAIL S21 A1 · doctor: {doctor.stdout} {doctor.stderr[-300:]}"
    print("PASS S21 A1 · Setup checks the tools and starts the helper at every login")
