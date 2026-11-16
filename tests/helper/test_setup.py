"""Setup, doctor, key and provider: the install on the person's machine."""
import errno
import json
import os
import platform
import plistlib
import pty
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import tomllib
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from fact_checker import cli, feedback
from fact_checker.install import settings_files
from fact_checker.server import handler, Helper, read_env
from machine_fakes import (
    calls,
    doctor_check,
    FAKE_CODEX,
    Foreign,
    health,
    helper_check,
    listening,
    machine,
    no_app,
    run,
    wait,
)


# S21 A1 · Setup checks the tools and starts the helper at every login
#
# Story: A tester installs the helper with `uv tool install` and runs `fact-checker setup`. On a Linux machine without
# yt-dlp, setup prints one line, "yt-dlp: missing", with its fix, "uv tool install yt-dlp", and installs nothing. Once
# yt-dlp is there, setup installs a systemd user service on Linux, or a launchd agent on macOS, that runs
# `fact-checker serve` at login. `fact-checker doctor` prints one line per check, such as "helper: not running on port
# 8765 · fix: fact-checker setup", and "speaker separation: off (optional)" without a Hugging Face token.
#
# Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME). PATH holds only a folder of fake commands:
# `claude` (answers `auth status --json` with loggedIn from FAKE_CLAUDE_LOGGED), `uv`, `yt-dlp`, `ffmpeg`, `chromium`,
# and `launchctl` and `systemctl`, which only write their arguments to a log; the real ones never run. The operating
# system is set by replacing platform.system. The helper port is a free local port; a case that needs a running helper
# starts the helper's HTTP server on it (S38: doctor knows the helper by its /health). The last case installs the package for real with `uv tool install` into temporary
# tool folders.

HELPER_SRC_s21a1 = Path(__file__).parents[2] / "src" / "helper"
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
def machine_s21a1(tmp_path, monkeypatch):
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


def run_s21a1(monkeypatch, capsys, *args) -> tuple[int, list[str]]:
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


def test_setup_and_doctor(machine_s21a1, monkeypatch, capsys, tmp_path):
    real_agent = REAL_HOME / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist"
    real_unit = REAL_HOME / ".config" / "systemd" / "user" / "fact-checker.service"
    before = (real_agent.exists(), real_unit.exists())
    unit = machine_s21a1.user / ".config" / "systemd" / "user" / "fact-checker.service"
    agent = machine_s21a1.user / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist"

    # Case 1 · Linux without yt-dlp, setup → one line with the fix, exit 1, no unit, no systemctl call
    machine_s21a1.system("Linux")
    machine_s21a1.missing("yt-dlp")
    code, out = run_s21a1(monkeypatch, capsys, "setup", "--port", str(machine_s21a1.port))
    assert code == 1, f"FAIL S21 A1 · setup exit {code} with yt-dlp missing"
    assert line(out, "yt-dlp:") == "yt-dlp: missing · fix: uv tool install yt-dlp"
    assert not unit.exists() and machine_s21a1.calls() == [], "FAIL S21 A1 · setup installed with a tool missing"

    # Case 2 · Linux with every tool, setup → a systemd user unit that serves on the port at login, enabled now
    (machine_s21a1.bin / "yt-dlp").write_text(f"#!{sys.executable}\n")
    (machine_s21a1.bin / "yt-dlp").chmod(0o755)
    code, out = run_s21a1(monkeypatch, capsys, "setup", "--port", str(machine_s21a1.port))
    assert code == 0, f"FAIL S21 A1 · setup exit {code}: {out}"
    text = unit.read_text()
    exec_start = next((x for x in text.splitlines() if x.startswith("ExecStart=")), "")
    assert exec_start.endswith(f"serve --port {machine_s21a1.port}"), f"FAIL S21 A1 · ExecStart: {text}"
    assert f"Environment=PATH={machine_s21a1.bin}" in text, f"FAIL S21 A1 · the unit has no PATH: {text}"
    assert "WantedBy=default.target" in text, f"FAIL S21 A1 · the unit does not start at login: {text}"
    assert ["systemctl", "--user", "daemon-reload"] in machine_s21a1.calls(), f"FAIL S21 A1 · {machine_s21a1.calls()}"
    assert ["systemctl", "--user", "enable", "--now", "fact-checker.service"] in machine_s21a1.calls(), \
        f"FAIL S21 A1 · {machine_s21a1.calls()}"

    # Case 3 · macOS, setup → a launchd agent that serves on the port at login and stays up, loaded now
    machine_s21a1.system("Darwin")
    code, out = run_s21a1(monkeypatch, capsys, "setup", "--port", str(machine_s21a1.port))
    assert code == 0, f"FAIL S21 A1 · setup exit {code} on macOS: {out}"
    plist = plistlib.loads(agent.read_bytes())
    assert plist["ProgramArguments"][-3:] == ["serve", "--port", str(machine_s21a1.port)], \
        f"FAIL S21 A1 · ProgramArguments {plist['ProgramArguments']}"
    assert plist["RunAtLoad"] is True and plist["KeepAlive"] == {"SuccessfulExit": False}, \
        "FAIL S21 A1 · the agent does not stay up"
    assert plist["EnvironmentVariables"]["PATH"] == str(machine_s21a1.bin), "FAIL S21 A1 · the agent has no PATH"
    assert ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(agent)] in machine_s21a1.calls(), \
        f"FAIL S21 A1 · {machine_s21a1.calls()}"

    # Case 4 · doctor, Claude logged out, no helper, no token → one line each with its fix, exit 1
    machine_s21a1.system("Linux")
    monkeypatch.setenv("FAKE_CLAUDE_LOGGED", "0")
    machine_s21a1.missing("chromium")
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", str(machine_s21a1.port))
    assert code == 1, f"FAIL S21 A1 · doctor exit {code} with problems"
    assert line(out, "claude:") == "claude: not logged in · fix: claude auth login"
    assert line(out, "chrome:").startswith("chrome: missing · fix: "), f"FAIL S21 A1 · {out}"
    assert line(out, "helper:") == f"helper: not running on port {machine_s21a1.port} · fix: fact-checker setup"
    assert line(out, "speaker separation:").startswith("speaker separation: off (optional)"), f"FAIL S21 A1 · {out}"
    assert line(out, "speech to text:") == "speech to text: faster-whisper"

    # Case 5 · doctor, everything there, the token in the helper home's .env, a helper on the port → exit 0
    monkeypatch.setenv("FAKE_CLAUDE_LOGGED", "1")
    (machine_s21a1.bin / "chromium").write_text(f"#!{sys.executable}\n")
    (machine_s21a1.bin / "chromium").chmod(0o755)
    (machine_s21a1.helper / ".env").write_text("HF_TOKEN=invented\n")
    server = ThreadingHTTPServer(("127.0.0.1", machine_s21a1.port), handler(Helper(machine_s21a1.helper)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", str(machine_s21a1.port))
    finally:
        server.shutdown()
    assert code == 0, f"FAIL S21 A1 · doctor exit {code}: {out}"
    assert line(out, "helper:") == f"helper: running on port {machine_s21a1.port}"
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
    install = subprocess.run([uv, "tool", "install", "--quiet", str(HELPER_SRC_s21a1)], env=env, capture_output=True, text=True)
    assert install.returncode == 0, f"FAIL S21 A1 · uv tool install: {install.stderr[-400:]}"
    for name in ("thresholds.json", "summary.html"):
        assert list((tmp_path / "tools").rglob(f"fact_checker/{name}")), f"FAIL S21 A1 · the package lacks {name}"
    doctor = subprocess.run([str(tmp_path / "bin" / "fact-checker"), "doctor", "--port", str(free_port())],
                            env=env, capture_output=True, text=True)
    assert "helper: not running" in doctor.stdout, f"FAIL S21 A1 · doctor: {doctor.stdout} {doctor.stderr[-300:]}"
    print("PASS S21 A1 · Setup checks the tools and starts the helper at every login")


# S22 A4 · Doctor names the provider, the models and a missing key
#
# Story: The person sets `provider = "anthropic"` and `parts = "claude-sonnet-5-5"`, with no API key, and runs
# `fact-checker doctor`. It prints "provider: anthropic", the model of each step ("parts claude-sonnet-5-5, verdict
# claude-opus-5-5, …"), and "ANTHROPIC_API_KEY: missing" with its fix, never a key value, and exits 1. It does not ask
# for Claude Code.
# Edge case: WHEN the provider is `codex` and no model is set THEN the models line says "account default" for each step,
# and a line says "Run `codex debug models` to see the models your plan allows."
#
# Setup: a Linux machine (platform.system replaced) whose PATH holds only fake `uv`, `yt-dlp`, `ffmpeg` and `chromium`
# commands, and a fake `codex` that answers `login status` with exit 0 in the last case; there is no `claude`. A
# temporary user home (HOME) and helper home (FACT_CHECKER_HOME) with the `config.toml` of each case. A small HTTP server
# stands for the running helper on a free local port. No API key in the environment.

SECRET = "sk-ant-invented-secret-value"


class Helper_s22a4(BaseHTTPRequestHandler):
    def do_GET(self):  # S38: doctor knows the helper by its /health
        raw = b'{"app": "fact-checker", "writable": true}' if self.path == "/health" else b""
        self.send_response(200 if raw else 404)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def test_doctor_provider(tmp_path, monkeypatch, capsys):
    bin_dir, user, home = tmp_path / "bin", tmp_path / "user", tmp_path / "helper"
    for folder in (bin_dir, user, home):
        folder.mkdir()
    for name in ("uv", "yt-dlp", "ffmpeg", "chromium"):
        (bin_dir / name).write_text(f"#!{sys.executable}\n")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "FACT_CHECK_PROVIDER", "CODEX_BIN", "HF_TOKEN",
                 "FACT_CHECK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Helper_s22a4)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = str(httpd.server_address[1])

    # Case 1 · anthropic with parts = claude-sonnet-5-5 and no key → the provider, the model of each step, the missing
    # key variable with its fix; exit 1; no line about Claude Code
    (home / "config.toml").write_text('provider = "anthropic"\n[models]\nparts = "claude-sonnet-5-5"\n')
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", port)
    assert code == 1, (code, out)
    assert "provider: anthropic" in out, out
    assert ("models: parts claude-sonnet-5-5, verdict claude-opus-5-5, judge claude-opus-5-5, "
            "search claude-haiku-5-5, screen claude-haiku-5-5") in out, out
    assert f"ANTHROPIC_API_KEY: missing · fix: add ANTHROPIC_API_KEY=<key> to {home / '.env'}" in out, out
    assert not [x for x in out if x.startswith("claude:")], out

    # Case 2 · the key in the helper's .env → "set", never its value; every check passes
    (home / ".env").write_text(f"ANTHROPIC_API_KEY={SECRET}\n")
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", port)
    assert "ANTHROPIC_API_KEY: set" in out, out
    assert not [x for x in out if SECRET in x], out
    assert code == 0, (code, out)

    # Case 3 · openai with key_env = XAI_API_KEY and no key → that variable is named, not OPENAI_API_KEY
    (home / "config.toml").write_text('provider = "openai"\n[openai]\nbase_url = "https://api.x.ai/v1"\n'
                                      'key_env = "XAI_API_KEY"\n')
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", port)
    assert code == 1, (code, out)
    assert f"XAI_API_KEY: missing · fix: add XAI_API_KEY=<key> to {home / '.env'}" in out, out
    assert not [x for x in out if x.startswith("OPENAI_API_KEY")], out

    # Case 4 · codex with no model → "account default" for each step and the hint to list the plan's models
    (home / "config.toml").write_text('provider = "codex"\n')
    (bin_dir / "codex").write_text(f"#!{sys.executable}\n")
    (bin_dir / "codex").chmod(0o755)
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", port)
    assert "provider: codex" in out, out
    assert ("models: parts account default, verdict account default, judge account default, "
            "search account default, screen account default") in out, out
    assert "Run `codex debug models` to see the models your plan allows." in out, out
    assert code == 0, (code, out)
    httpd.shutdown()
    print("PASS S22 A4 · Doctor names the provider, the models and a missing key")


# S23 A4 · Doctor lists each step's provider and every missing key
#
# Story: With the A3 settings and no keys, the person runs `fact-checker doctor`. It prints one line per step, such as
# "role parts: chat · some-model · https://router.huggingface.co/v1", then "HF_TOKEN: missing", "ANTHROPIC_API_KEY:
# missing" and "TAVILY_API_KEY: missing", each with its fix and never a key value, and exits 1.
#
# Setup: a Linux machine (platform.system replaced) whose PATH holds only fake `uv`, `yt-dlp`, `ffmpeg` and `chromium`
# commands, and failing fake `claude` and `codex` commands. A temporary user home (HOME) and helper home
# (FACT_CHECKER_HOME) with the `config.toml` of each case: `provider = "anthropic"` with `[roles.parts]` and
# `[roles.search]` on `https://router.huggingface.co/v1`, `key_env = "HF_TOKEN"` and `model = "some-model"`; in the last
# case `provider = "chat"` on a local Ollama address with no key. A small HTTP server stands for the running helper on a
# free local port. No API key in the environment.

SECRETS = {"HF_TOKEN": "hf_invented_secret", "ANTHROPIC_API_KEY": "sk-ant-invented-secret",
           "TAVILY_API_KEY": "tvly-invented-secret"}
ROUTER = "https://router.huggingface.co/v1"
MIXED = ('provider = "anthropic"\n'
         f'[roles.parts]\nprovider = "chat"\nbase_url = "{ROUTER}"\nkey_env = "HF_TOKEN"\nmodel = "some-model"\n'
         f'[roles.search]\nprovider = "chat"\nbase_url = "{ROUTER}"\nkey_env = "HF_TOKEN"\nmodel = "some-model"\n')
FAILING_CLI = "import sys\nsys.exit(1)\n"


def test_doctor_roles(tmp_path, monkeypatch, capsys):
    bin_dir, user, home = tmp_path / "bin", tmp_path / "user", tmp_path / "helper"
    for folder in (bin_dir, user, home):
        folder.mkdir()
    for name in ("uv", "yt-dlp", "ffmpeg", "chromium"):
        (bin_dir / name).write_text(f"#!{sys.executable}\n")
        (bin_dir / name).chmod(0o755)
    for name in ("claude", "codex"):
        (bin_dir / name).write_text(f"#!{sys.executable}\n{FAILING_CLI}")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    for name in (*SECRETS, "OPENAI_API_KEY", "CHAT_API_KEY", "FACT_CHECK_PROVIDER", "CODEX_BIN", "FACT_CHECK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Helper_s22a4)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = str(httpd.server_address[1])

    # Case 1 · mixed roles and no key → one line per step with its provider, model and address; each missing key once,
    # with its fix; exit 1
    (home / "config.toml").write_text(MIXED)
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", port)
    assert code == 1, (code, out)
    for line in (f"role parts: chat · some-model · {ROUTER}",
                 "role verdict: anthropic · claude-opus-5-5 · https://api.anthropic.com",
                 "role judge: anthropic · claude-opus-5-5 · https://api.anthropic.com",
                 f"role search: chat · some-model · {ROUTER}"):
        assert line in out, (line, out)
    for variable in SECRETS:
        fix = f"{variable}: missing · fix: add {variable}=<key> to {home / '.env'}"
        assert out.count(fix) == 1, (fix, out)
    assert not [x for x in out if x.startswith("claude:") or x.startswith("codex:")], out

    # Case 2 · the keys in the helper's .env → each "set", never its value; exit 0
    (home / ".env").write_text("".join(f"{k}={v}\n" for k, v in SECRETS.items()))
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", port)
    for variable in SECRETS:
        assert f"{variable}: set" in out, (variable, out)
    assert not [x for x in out for secret in SECRETS.values() if secret in x], out
    assert code == 0, (code, out)

    # Case 3 · a chat provider on a local Ollama address → its role lines, no key line for it; the search key is still
    # named
    (home / ".env").unlink()
    (home / "config.toml").write_text('provider = "chat"\n[models]\nparts = "llama3"\nverdict = "llama3"\n'
                                      'judge = "llama3"\nsearch = "llama3"\n'
                                      '[chat]\nbase_url = "http://localhost:11434/v1"\n')
    code, out = run_s21a1(monkeypatch, capsys, "doctor", "--port", port)
    assert "role parts: chat · llama3 · http://localhost:11434/v1" in out, out
    assert not [x for x in out if x.startswith("CHAT_API_KEY")], out
    assert f"TAVILY_API_KEY: missing · fix: add TAVILY_API_KEY=<key> to {home / '.env'}" in out, out
    assert code == 1, (code, out)
    httpd.shutdown()
    print("PASS S23 A4 · Doctor lists each step's provider and every missing key")


# S25 A1 · One script installs everything, and a second run changes nothing
#
# Story: On a fresh macOS or Linux account with Claude Code logged in and no uv, yt-dlp, ffmpeg or helper, a person runs
# `./install.sh` from the repo. It installs uv with the official installer, yt-dlp, an ffmpeg from a Python wheel (no
# Homebrew), and the helper, runs `fact-checker setup`, and ends with the ready extension folder, such as
# `~/.fact-checker/extension`, which holds a built extension with no Node.js. A second run prints "already there" for uv,
# yt-dlp, ffmpeg and the helper, downloads and installs nothing, and leaves every file the same.
#
# Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME). PATH holds a folder with only the system
# commands the script needs (sh, dirname, cp, chmod, mkdir) and a folder of fakes: `curl` answers the uv installer URL
# with a script that puts a fake `uv` in ~/.local/bin; the fake `uv` writes each call to a log, makes `yt-dlp` and the
# helper's `fact-checker` command on `tool install` (the helper command runs the real CLI from src/helper), and answers
# the imageio-ffmpeg query with a fake ffmpeg file. `claude` is logged in and fails any reading; `codex` fails every call;
# `launchctl`, `systemctl`, `brew` and `sudo` only log; `chromium` exists. The last case installs the helper package for real with
# `uv tool install` into temporary tool folders. FACT_CHECKER_PORT moves the helper's ports to a free one, away from the
# person's helper on 8765–8769.

REPO = Path(__file__).parents[2]
HELPER_SRC = REPO / "src" / "helper"

FAKE_UV = """\
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(json.dumps(["uv", *args]) + "\\n")
bin_dir = os.path.join(os.environ["HOME"], ".local", "bin")
def make(name, text):
    path = os.path.join(bin_dir, name)
    open(path, "w").write(text)
    os.chmod(path, 0o755)
if args[:3] == ["tool", "dir", "--bin"]:
    print(bin_dir)
elif args[:2] == ["tool", "install"] and args[-1] == "yt-dlp":
    make("yt-dlp", "#!/bin/sh\\n")
elif args[:2] == ["tool", "install"]:
    make("fact-checker", f"#!/bin/sh\\nPYTHONPATH={os.environ['HELPER_SRC']} exec {sys.executable} -m fact_checker.cli \\"$@\\"\\n")
elif args[:1] == ["run"] and "imageio-ffmpeg" in args:
    print(os.environ["FAKE_FFMPEG"])
"""
FAKE_CURL = """\
import json, os, sys
open(os.environ["FAKE_LOG"], "a").write(json.dumps(["curl", *sys.argv[1:]]) + "\\n")
if sys.argv[-1] == "https://astral.sh/uv/install.sh":
    print('mkdir -p "$HOME/.local/bin" && cp "$FAKE_UV" "$HOME/.local/bin/uv" && chmod 755 "$HOME/.local/bin/uv"')
"""
FAKE_CLAUDE_s25a1 = """\
import json, sys
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True}))
else:
    sys.exit(1)
"""
FAKE_RECORDER_s25a1 = """\
import json, os, sys
open(os.environ["FAKE_LOG"], "a").write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + "\\n")
"""


def script(path: Path, code: str) -> None:
    path.write_text(f"#!{sys.executable}\n{code}")
    path.chmod(0o755)


def machine_s25a1(tmp_path: Path) -> dict:
    fakes, system = tmp_path / "fakes", tmp_path / "system"
    fakes.mkdir()
    system.mkdir()
    for name in ("sh", "dirname", "cp", "chmod", "mkdir"):
        (system / name).symlink_to(shutil.which(name))
    for name, code in {"curl": FAKE_CURL, "claude": FAKE_CLAUDE_s25a1, "codex": "import sys\nsys.exit(1)\n",
                       "launchctl": FAKE_RECORDER_s25a1, "systemctl": FAKE_RECORDER_s25a1, "brew": FAKE_RECORDER_s25a1,
                       "sudo": FAKE_RECORDER_s25a1, "chromium": ""}.items():
        script(fakes / name, code)
    script(tmp_path / "uv", FAKE_UV)
    (tmp_path / "ffmpeg-from-wheel").write_text("#!/bin/sh\n")
    home = tmp_path / "home"
    home.mkdir()
    return {"PATH": f"{fakes}{os.pathsep}{system}", "HOME": str(home), "FACT_CHECKER_HOME": str(home / ".fact-checker"),
            "FAKE_LOG": str(tmp_path / "calls.jsonl"), "FAKE_UV": str(tmp_path / "uv"),
            "FAKE_FFMPEG": str(tmp_path / "ffmpeg-from-wheel"), "HELPER_SRC": str(HELPER_SRC),
            "FACT_CHECKER_PORT": str(free_port())}


def install(env: dict) -> tuple[int, list[str], list[list[str]]]:
    log = Path(env["FAKE_LOG"])
    log.unlink(missing_ok=True)
    done = subprocess.run(["sh", str(REPO / "install.sh")], env=env, capture_output=True, text=True, timeout=120)
    calls = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    return done.returncode, (done.stdout + done.stderr).splitlines(), calls


def files(home: Path) -> dict:
    return {str(p.relative_to(home)): p.read_bytes() for p in sorted(home.rglob("*")) if p.is_file()}


def test_installer_twice(tmp_path):
    env = machine_s25a1(tmp_path)
    home = Path(env["HOME"])
    bin_dir = home / ".local" / "bin"
    real = (REAL_HOME / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist",
            REAL_HOME / ".config" / "systemd" / "user" / "fact-checker.service")
    before = [p.exists() and p.read_bytes() for p in real]

    # Case 1 · a fresh account → uv from its official installer, yt-dlp, ffmpeg from the wheel, the helper, setup
    code, out, calls = install(env)
    assert code == 0, f"FAIL S25 A1 · install.sh exit {code}: {out[-15:]}"
    assert ["curl", "-LsSf", "https://astral.sh/uv/install.sh"] in calls, f"FAIL S25 A1 · no uv installer: {calls}"
    assert ["uv", "tool", "install", "yt-dlp"] in calls, f"FAIL S25 A1 · no yt-dlp: {calls}"
    assert ["uv", "tool", "install", str(HELPER_SRC)] in calls, f"FAIL S25 A1 · no helper: {calls}"
    for name in ("uv", "yt-dlp", "ffmpeg", "fact-checker"):
        assert (bin_dir / name).exists(), f"FAIL S25 A1 · {name} is not in {bin_dir}"
    assert (bin_dir / "ffmpeg").read_bytes() == Path(env["FAKE_FFMPEG"]).read_bytes(), "FAIL S25 A1 · ffmpeg"
    assert not any(c[0] in ("brew", "sudo") for c in calls), f"FAIL S25 A1 · Homebrew or sudo: {calls}"
    assert any(c[0] in ("launchctl", "systemctl") for c in calls), f"FAIL S25 A1 · setup did not start the helper"

    # Case 2 · the end of the run → the extension folder, a built extension that needs no Node.js
    extension = home / ".fact-checker" / "extension"
    manifest = json.loads((extension / "manifest.json").read_text())
    for script_path in (manifest["background"]["service_worker"], *manifest["content_scripts"][0]["js"],
                        *manifest["content_scripts"][1]["js"]):
        assert (extension / script_path).stat().st_size > 0, f"FAIL S25 A1 · the extension lacks {script_path}"
    assert any(str(extension) in line for line in out[-5:]), f"FAIL S25 A1 · the end names no folder: {out[-5:]}"

    # Case 3 · a second run → "already there" for each tool, no download, no install, every file the same
    first = files(home)
    code, out, calls = install(env)
    assert code == 0, f"FAIL S25 A1 · second run exit {code}: {out[-15:]}"
    for name in ("uv", "yt-dlp", "ffmpeg", "helper"):
        assert f"{name}: already there" in out, f"FAIL S25 A1 · second run, {name}: {out}"
    installs = [c for c in calls if c[0] == "curl" or c[1:3] == ["tool", "install"] or c[1:2] == ["run"]]
    assert installs == [], f"FAIL S25 A1 · the second run installed: {installs}"
    assert files(home) == first, "FAIL S25 A1 · the second run changed files"
    assert [p.exists() and p.read_bytes() for p in real] == before, "FAIL S25 A1 · setup wrote into the real home"


def test_package_holds_the_extension(tmp_path):
    # Case 4 · uv tool install of the helper → its package holds the built extension: manifest and scripts
    uv = shutil.which("uv")
    assert uv, "FAIL S25 A1 · uv is not installed on this machine"
    cache = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True).stdout.strip()
    env = os.environ | {"UV_CACHE_DIR": cache, "UV_TOOL_DIR": str(tmp_path / "tools"),
                        "UV_TOOL_BIN_DIR": str(tmp_path / "bin"), "HOME": str(tmp_path)}
    done = subprocess.run([uv, "tool", "install", "--quiet", str(HELPER_SRC)], env=env, capture_output=True, text=True)
    assert done.returncode == 0, f"FAIL S25 A1 · uv tool install: {done.stderr[-400:]}"
    for name in ("manifest.json", "dist/content.js", "dist/sw.js", "dist/guard.js", "icons/icon128.png"):
        assert list((tmp_path / "tools").rglob(f"fact_checker/extension/{name}")), f"FAIL S25 A1 · package lacks {name}"
    print("PASS S25 A1 · One script installs everything, and a second run changes nothing")


# S25 A2 · Setup picks the logged-in subscription and keeps an existing settings file
#
# Story: A person with no `~/.fact-checker/config.toml` runs `fact-checker setup`. With Claude Code logged in, the new
# settings file says `provider = "claude"`; with only Codex logged in, `provider = "codex"`; with neither, setup prints
# one line, "provider: no agent CLI logged in", with the fix, writes no settings file and starts nothing. A settings file
# that says `provider = "codex"` stays byte for byte, also when Claude Code is logged in.
#
# Setup: a temporary user home (HOME) and a new helper home (FACT_CHECKER_HOME) for each case. PATH holds only fakes:
# `claude` answers `auth status --json` with loggedIn from FAKE_CLAUDE_LOGGED and fails any other call; `codex` answers
# `login status` with exit 0 when FAKE_CODEX_LOGGED is 1 and fails any other call; `uv`, `yt-dlp`, `ffmpeg` and
# `chromium` exist; `launchctl` and `systemctl` only write their arguments to a log. The system is Linux. Setup uses a
# free local port, never the person's helper on 8765.

FAKE_CLAUDE_s25a2 = """\
import json, os, sys
if sys.argv[1:3] != ["auth", "status"]:
    sys.exit(1)
print(json.dumps({"loggedIn": os.environ.get("FAKE_CLAUDE_LOGGED") == "1"}))
"""
FAKE_CODEX_s25a2 = """\
import os, sys
sys.exit(0 if sys.argv[1:3] == ["login", "status"] and os.environ.get("FAKE_CODEX_LOGGED") == "1" else 1)
"""
FAKE_RECORDER_s25a2 = """\
import json, os, sys
open(os.environ["FAKE_LOG"], "a").write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\\n")
"""


def test_provider_detection(tmp_path, monkeypatch, capsys):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, code in {"claude": FAKE_CLAUDE_s25a2, "codex": FAKE_CODEX_s25a2, "launchctl": FAKE_RECORDER_s25a2,
                       "systemctl": FAKE_RECORDER_s25a2, "uv": "", "yt-dlp": "", "ffmpeg": "", "chromium": ""}.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    (tmp_path / "user").mkdir()
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.delenv("FACT_CHECK_PROVIDER", raising=False)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    def setup(case: str, claude: bool, codex: bool, config: str | None = None):
        home = tmp_path / case
        home.mkdir()
        if config is not None:
            (home / "config.toml").write_text(config)
        log.unlink(missing_ok=True)
        monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
        monkeypatch.setenv("FAKE_CLAUDE_LOGGED", "1" if claude else "0")
        monkeypatch.setenv("FAKE_CODEX_LOGGED", "1" if codex else "0")
        monkeypatch.setattr(sys, "argv", ["fact-checker", "setup", "--port", str(free_port())])
        try:
            cli.main()
            code = 0
        except SystemExit as end:
            code = end.code or 0
        calls = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
        return code, capsys.readouterr().out.splitlines(), home, calls

    def provider(home: Path) -> dict:
        # The author's collector address ships active in the example; every other line stays a comment.
        return {k: v for k, v in tomllib.loads((home / "config.toml").read_text()).items() if k != "feedback_url"}

    # Case 1 · no settings file, Claude Code and Codex logged in → provider "claude", the other lines stay comments
    code, out, home, calls = setup("both", claude=True, codex=True)
    assert code == 0, f"FAIL S25 A2 · setup exit {code}: {out}"
    assert provider(home) == {"provider": "claude"}, f"FAIL S25 A2 · {provider(home)}"
    assert "# [models]" in (home / "config.toml").read_text(), "FAIL S25 A2 · the settings file lost its comments"

    # Case 2 · no settings file, only Codex logged in → provider "codex"
    code, out, home, calls = setup("codex", claude=False, codex=True)
    assert code == 0, f"FAIL S25 A2 · setup exit {code}: {out}"
    assert provider(home) == {"provider": "codex"}, f"FAIL S25 A2 · {provider(home)}"

    # Case 3 · no settings file, neither logged in → one provider line with its fix, no settings file, nothing started
    code, out, home, calls = setup("none", claude=False, codex=False)
    assert code == 1, f"FAIL S25 A2 · setup exit {code} with no agent CLI"
    found = [x for x in out if x.startswith("provider:")]
    assert len(found) == 1 and found[0].startswith("provider: no agent CLI logged in · fix: "), \
        f"FAIL S25 A2 · {out}"
    assert "claude auth login" in found[0] and "codex login" in found[0], f"FAIL S25 A2 · the fix: {found[0]}"
    assert not (home / "config.toml").exists(), "FAIL S25 A2 · a settings file without a provider"
    assert calls == [], f"FAIL S25 A2 · setup started the helper: {calls}"

    # Case 4 · a settings file with provider "codex", Claude Code logged in → the file stays byte for byte
    own = '# mine\nprovider = "codex"\n'
    code, out, home, calls = setup("own", claude=True, codex=True, config=own)
    assert code == 0, f"FAIL S25 A2 · setup exit {code}: {out}"
    assert (home / "config.toml").read_text() == own, "FAIL S25 A2 · setup changed an existing settings file"
    print("PASS S25 A2 · Setup picks the logged-in subscription and keeps an existing settings file")


# S25 A3 · A key goes in through a hidden prompt, and doctor answers in JSON
#
# Story: A person with `provider = "anthropic"` runs `fact-checker doctor --json`: an agent reads `"ok": false` and the
# check `ANTHROPIC_API_KEY` with state "missing" and its fix, the same as in the
# text output. The person runs `fact-checker key set ANTHROPIC_API_KEY` in
# a terminal and types an invented key: the screen never shows it, and `~/.fact-checker/.env` gets one
# `ANTHROPIC_API_KEY=` line with it, readable only by the person. A second `key set` replaces that line.
# `doctor --json` then says "set", and its output never holds the key.
#
# Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME) with `provider = "anthropic"` in config.toml
# and the commented keys example as .env. PATH holds only fakes: `claude` and `codex` fail every call; `uv`, `yt-dlp`,
# `ffmpeg` and `chromium` exist. Each command runs the real CLI from src/helper in a child process. `key set` runs in a
# pseudo-terminal, as in a real terminal window: the test waits for the prompt, types the key and reads every byte the
# screen gets. No helper listens on the port.

EXAMPLE = HELPER_SRC / "fact_checker" / "env.example"
FIRST, SECOND = "sk-ant-invented-first-1234", "sk-ant-invented-second-5678"


def machine_s25a3(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, code in {"claude": "import sys\nsys.exit(1)\n", "codex": "import sys\nsys.exit(1)\n",
                       "uv": "", "yt-dlp": "", "ffmpeg": "", "chromium": ""}.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    home = tmp_path / "helper"
    home.mkdir()
    (home / "config.toml").write_text('provider = "anthropic"\n')
    (home / ".env").write_text(EXAMPLE.read_text())
    (tmp_path / "user").mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "FACT_CHECK_PROVIDER")}
    return env | {"PATH": str(bin_dir), "HOME": str(tmp_path / "user"), "FACT_CHECKER_HOME": str(home),
                  "PYTHONPATH": str(HELPER_SRC)}


def doctor(env: dict) -> tuple[int, str]:
    done = subprocess.run([sys.executable, "-m", "fact_checker.cli", "doctor", "--json", "--port", str(free_port())],
                          env=env, capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout + done.stderr


def key_set(env: dict, name: str, typed: str) -> tuple[int, str]:
    """Runs `key set` in a pseudo-terminal; types the key after the prompt; returns the exit code and the screen."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execve(sys.executable, [sys.executable, "-m", "fact_checker.cli", "key", "set", name], env)
    screen = b""

    def read() -> bytes:
        if not select.select([fd], [], [], 30)[0]:
            return b""
        try:
            return os.read(fd, 1024)
        except OSError:
            return b""
    while name.encode() not in screen:
        chunk = read()
        if not chunk:
            break
        screen += chunk
    os.write(fd, typed.encode() + b"\n")
    while chunk := read():
        screen += chunk
    os.close(fd)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), screen.decode(errors="replace")


def check(report: dict, name: str) -> dict:
    found = [c for c in report["checks"] if c["name"] == name]
    assert len(found) == 1, f"FAIL S25 A3 · one check named {name}: {report['checks']}"
    return found[0]


def test_key_and_doctor_json(tmp_path):
    env = machine_s25a3(tmp_path)
    dotenv = Path(env["FACT_CHECKER_HOME"]) / ".env"
    example_lines = [x for x in EXAMPLE.read_text().splitlines() if "ANTHROPIC_API_KEY" not in x]

    # Case 1 · doctor --json, no key → "ok": false, the key check "missing" with its fix, each check with its fields
    code, out = doctor(env)
    assert code == 1, f"FAIL S25 A3 · doctor exit {code}: {out}"
    report = json.loads(out)
    assert report["ok"] is False, f"FAIL S25 A3 · {report}"
    key = check(report, "ANTHROPIC_API_KEY")
    assert key["state"] == "missing" and key["ok"] is False, f"FAIL S25 A3 · {key}"
    assert key["fix"] == f"add ANTHROPIC_API_KEY=<key> to {dotenv}", f"FAIL S25 A3 · the fix: {key}"
    assert check(report, "helper")["ok"] is False, f"FAIL S25 A3 · {report}"
    assert all(set(c) == {"name", "state", "fix", "ok"} for c in report["checks"]), f"FAIL S25 A3 · {report}"

    # Case 2 · key set in a terminal → the prompt names the key, the screen never shows it, one line in .env, mode 600
    code, screen = key_set(env, "ANTHROPIC_API_KEY", FIRST)
    assert code == 0, f"FAIL S25 A3 · key set exit {code}: {screen}"
    assert FIRST not in screen, f"FAIL S25 A3 · the screen showed the key: {screen!r}"
    lines = dotenv.read_text().splitlines()
    assert [x for x in lines if "ANTHROPIC_API_KEY" in x] == [f"ANTHROPIC_API_KEY={FIRST}"], f"FAIL S25 A3 · {lines}"
    assert [x for x in lines if "ANTHROPIC_API_KEY" not in x] == example_lines, "FAIL S25 A3 · other lines changed"
    assert dotenv.stat().st_mode & 0o777 == 0o600, f"FAIL S25 A3 · .env mode {oct(dotenv.stat().st_mode & 0o777)}"

    # Case 3 · key set again → the line is replaced, still one line
    code, screen = key_set(env, "ANTHROPIC_API_KEY", SECOND)
    assert code == 0 and SECOND not in screen, f"FAIL S25 A3 · second key set: {code} {screen!r}"
    lines = dotenv.read_text().splitlines()
    assert [x for x in lines if "ANTHROPIC_API_KEY" in x] == [f"ANTHROPIC_API_KEY={SECOND}"], f"FAIL S25 A3 · {lines}"

    # Case 4 · doctor --json with the key → "set", and the output never holds the key
    code, out = doctor(env)
    key = check(json.loads(out), "ANTHROPIC_API_KEY")
    assert key["state"] == "set" and key["ok"] is True, f"FAIL S25 A3 · {key}"
    assert FIRST not in out and SECOND not in out, "FAIL S25 A3 · doctor printed a key"
    print("PASS S25 A3 · A key goes in through a hidden prompt, and doctor answers in JSON")


# S25 A4 · One sentence leads any agent through the install, in Spanish and English
#
# Story: The README starts with the sentence to paste into Claude or ChatGPT, in Spanish and English; the extension's
# "helper does not answer" notice shows the same sentence in both languages. The agent guide names only commands that
# exist, and each message it tells the person has a Spanish and an English text. The person reads the guide and the
# README quick start in both languages.
#
# Setup: none. The test reads INSTALL-AGENT.md, README.md, install.sh and the notice texts of the extension. The guide
# address comes from the repo address in install.sh. Each `fact-checker` command in a shell block or a code span of the
# guide runs with `--help` through the real CLI from src/helper; a `<NAME>` placeholder becomes a sample name.

GUIDE = REPO / "INSTALL-AGENT.md"
TEXTS = REPO / "src" / "extension" / "src" / "texts.ts"


def guide_url() -> str:
    assert (REPO / "install.sh").exists(), "FAIL S25 A4 · no install.sh, so no guide address"
    found = re.search(r'FACT_CHECKER_REPO:-([^}"]+)', (REPO / "install.sh").read_text())
    assert found, "FAIL S25 A4 · install.sh has no FACT_CHECKER_REPO default"
    return f"{found.group(1)}/blob/main/INSTALL-AGENT.md"


def test_agent_guide():
    url = guide_url()
    spanish, english = f"Instala fact-checker siguiendo {url}", f"Install fact-checker by following {url}"

    # Case 1 · the README → its first lines link the guide and give the sentence in Spanish and English
    readme = (REPO / "README.md").read_text()
    head = "\n".join(readme.splitlines()[:12])
    assert "INSTALL-AGENT.md" in head, f"FAIL S25 A4 · the README does not start with the guide: {head}"
    assert spanish in readme and english in readme, "FAIL S25 A4 · the README lacks the sentence in a language"

    # Case 2 · the "helper does not answer" notice → the same sentence in Spanish and English
    texts = TEXTS.read_text()
    assert "export const TEXTS" in texts, "FAIL S25 A4 · no exported TEXTS object"
    assert "INSTALL-AGENT.md" in texts and "Instala fact-checker siguiendo" in texts and \
        "Install fact-checker by following" in texts, "FAIL S25 A4 · the notice lacks the sentence in a language"
    assert url in texts, f"FAIL S25 A4 · the notice does not name {url}"

    # Case 3 · each message for the person in the guide → a Spanish text, then an English text
    lines = GUIDE.read_text().splitlines()
    es = [i for i, x in enumerate(lines) if x.startswith("> **ES:**")]
    en = [i for i, x in enumerate(lines) if x.startswith("> **EN:**")]
    assert len(es) >= 4, f"FAIL S25 A4 · {len(es)} messages for the person"
    assert [i + 1 for i in es] == en, "FAIL S25 A4 · a message lacks its English text right after the Spanish one"

    # Case 4 · each fact-checker command the guide names → it exists (--help exits 0); install.sh exists
    text = GUIDE.read_text()
    blocks = "\n".join(re.findall(r"```sh\n(.*?)```", text, re.S))
    spans = re.findall(r"`([^`\n]+)`", re.sub(r"```.*?```", "", text, flags=re.S))
    commands = {re.sub(r"<[A-Z_]+>", "HF_TOKEN", c.strip()).split(" #")[0].split(" &&")[0].strip()
                for c in [*blocks.splitlines(), *spans] if c.strip().startswith("fact-checker ")}
    assert {"fact-checker doctor --json", "fact-checker key set HF_TOKEN", "fact-checker setup"} <= commands, \
        f"FAIL S25 A4 · the guide misses a command: {sorted(commands)}"
    for command in sorted(commands):
        done = subprocess.run([sys.executable, "-m", "fact_checker.cli", *command.split()[1:], "--help"],
                              cwd=REPO / "src" / "helper", capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, f"FAIL S25 A4 · `{command}` does not exist: {done.stderr[-300:]}"
    assert "./install.sh" in text and (REPO / "install.sh").exists(), "FAIL S25 A4 · the guide names no installer"
    print("PASS S25 A4 · One sentence leads any agent through the install, in Spanish and English")


# S29 A4 · Doctor lists the screen, and no settings gives the cheap defaults
#
# Story: With no settings file, `fact-checker doctor` prints "models: parts opus, verdict opus, judge opus, search haiku,
# screen haiku". With `provider = "anthropic"` it prints `screen claude-haiku-5-5`; with `provider = "chat"` and
# `parts = "llama3"` it prints "role screen: chat · llama3 · …".
#
# Setup: a Linux machine (platform.system replaced) whose PATH holds only fake `uv`, `yt-dlp`, `ffmpeg` and `chromium`
# commands, and failing fake `claude` and `codex` commands. A temporary user home (HOME) and helper home
# (FACT_CHECKER_HOME) with the `config.toml` of each case. A small HTTP server stands for the running helper on a free
# local port. No API key in the environment.

def run_s29a4(monkeypatch, capsys, *args) -> list[str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
    except SystemExit:
        pass
    return capsys.readouterr().out.splitlines()


def test_doctor_screen(tmp_path, monkeypatch, capsys):
    bin_dir, user, home = tmp_path / "bin", tmp_path / "user", tmp_path / "helper"
    for folder in (bin_dir, user, home):
        folder.mkdir()
    for name in ("uv", "yt-dlp", "ffmpeg", "chromium"):
        (bin_dir / name).write_text(f"#!{sys.executable}\n")
        (bin_dir / name).chmod(0o755)
    for name in ("claude", "codex"):
        (bin_dir / name).write_text(f"#!{sys.executable}\n{FAILING_CLI}")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CHAT_API_KEY", "HF_TOKEN", "TAVILY_API_KEY",
                 "FACT_CHECK_PROVIDER", "CODEX_BIN", "FACT_CHECK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Helper_s22a4)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = str(httpd.server_address[1])

    # Case 1 · no settings file → haiku screens the parts and searches the figures; opus does the rest
    out = run_s29a4(monkeypatch, capsys, "doctor", "--port", port)
    assert "models: parts opus, verdict opus, judge opus, search haiku, screen haiku" in out, \
        f"FAIL S29 A4 · models line {[x for x in out if x.startswith('models')]}"
    assert "role screen: claude · haiku" in out, out

    # Case 2 · provider anthropic → claude-haiku-5-5 screens and searches
    (home / "config.toml").write_text('provider = "anthropic"\n')
    out = run_s29a4(monkeypatch, capsys, "doctor", "--port", port)
    assert ("models: parts claude-opus-5-5, verdict claude-opus-5-5, judge claude-opus-5-5, "
            "search claude-haiku-5-5, screen claude-haiku-5-5") in out, \
        f"FAIL S29 A4 · models line {[x for x in out if x.startswith('models')]}"

    # Case 3 · provider chat with only the parts model → the screen uses the parts model
    (home / "config.toml").write_text('provider = "chat"\n[models]\nparts = "llama3"\n')
    out = run_s29a4(monkeypatch, capsys, "doctor", "--port", port)
    assert "role screen: chat · llama3 · http://localhost:11434/v1" in out, \
        f"FAIL S29 A4 · role lines {[x for x in out if x.startswith('role')]}"
    httpd.shutdown()
    print("PASS S29 A4 · Doctor lists the screen, and no settings gives the cheap defaults")


# S38 A1 · The check knows the helper by its answer
#
# Story: The person's agent runs `fact-checker doctor` while another program answers on port 8765. The helper line says
# "another program holds port 8765" and is not ok. With the real helper running and its home writable, it says
# "running on port 8766" (the port it found) and is ok.
#
# Setup: a temporary user home and helper home, and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT), so
# "8765" below is the first of them. PATH holds only fake commands: `claude` logged in, `uv`, `yt-dlp`, `ffmpeg`,
# `chromium`. Another program is a small web server that answers every request with an HTML 404. The real helper is the
# helper's HTTP handler on the second port, with the temporary helper home.

def test_doctor_knows_helper(tmp_path, monkeypatch, capsys):
    m = machine(tmp_path, monkeypatch)
    first, home = m["first"], m["home"]
    foreign = Foreign(first)
    helper = None
    try:
        # Case 1 · another program answers on the first port, no helper → "another program holds port 8765", not ok
        code, check = helper_check(monkeypatch, capsys)
        assert check["state"] == f"another program holds port {first}", f"FAIL S38 A1 · {check}"
        assert check["ok"] is False and code == 1, f"FAIL S38 A1 · a foreign program passed: {check}"

        # Case 2 · the real helper on the second port → /health names it, "running on port 8766", ok
        helper = ThreadingHTTPServer(("127.0.0.1", first + 1), handler(Helper(home)))
        threading.Thread(target=helper.serve_forever, daemon=True).start()
        answer = health(first + 1)
        assert {k: v for k, v in answer.items() if k != "tools"} == {"app": "fact-checker", "version": feedback.helper_version(), "pid": os.getpid(),
                          "home": str(home), "writable": True}, f"FAIL S38 A1 · /health: {answer}"
        code, check = helper_check(monkeypatch, capsys)
        assert check == {"name": "helper", "state": f"running on port {first + 1}", "fix": "", "ok": True}, \
            f"FAIL S38 A1 · {check}"

        # Case 3 · the helper's home is not writable → /health says so, the helper line is not ok
        home.chmod(0o555)
        assert health(first + 1)["writable"] is False, "FAIL S38 A1 · /health says a read-only home is writable"
        code, check = helper_check(monkeypatch, capsys)
        assert check["ok"] is False and check["state"].startswith(f"running on port {first + 1}"), \
            f"FAIL S38 A1 · a helper that cannot write passed: {check}"
        assert str(home) in check["state"] and "fact-checker setup" in check["fix"], f"FAIL S38 A1 · {check}"
    finally:
        home.chmod(0o755)
        foreign.stop()
        if helper:
            helper.shutdown()
            helper.server_close()
    print("PASS S38 A1 · The check knows the helper by its answer")


# S38 A3 · Setup replaces an old helper
#
# Story: A fact-checker helper started by hand (for example by an agent) holds port 8765. The person's agent runs
# `fact-checker setup`. The old helper stops, the login helper answers on 8765, and doctor's helper line is ok.
#
# Setup: a temporary user home and helper home, and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT), so
# "8765" below is the first of them. The system is macOS. PATH holds only fake commands: `claude` logged in, `uv`,
# `yt-dlp`, `ffmpeg`, `chromium`, and a `launchctl` that acts as launchd for this test only: `bootstrap` starts the
# command of the agent file in the background and keeps its process id, `bootout` stops that process. The old helper
# is a real `fact-checker serve --port 8765` started by the test. Another program, a small web server that answers every
# request with an HTML 404, holds the last port, and a `serve` of another home holds the fourth: setup leaves both
# running. A connection to the real 8765–8769 fails the test. Every process the test starts is stopped at the end.

FAKE_LAUNCHD = """\
import json, os, plistlib, signal, subprocess, sys
pid_file = os.environ["FAKE_LAUNCHD_PID"]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(["launchctl"] + sys.argv[1:]) + "\\n")
if sys.argv[1] == "bootout" and os.path.exists(pid_file):
    try:
        os.kill(int(open(pid_file).read()), signal.SIGTERM)
    except ProcessLookupError:
        pass
    os.remove(pid_file)
if sys.argv[1] == "bootstrap":
    agent = plistlib.load(open(sys.argv[3], "rb"))
    args = agent["ProgramArguments"]
    port = int(args[args.index("--port") + 1]) if "--port" in args else int(os.environ.get("FACT_CHECKER_PORT", 8765))
    if port in range(8761, 8770):
        sys.exit("the test refuses to start a helper on the person's ports")
    log = open(agent["StandardOutPath"], "a")
    env = os.environ | agent["EnvironmentVariables"]
    child = subprocess.Popen(agent["ProgramArguments"], env=env, stdout=log, stderr=log, start_new_session=True)
    open(pid_file, "w").write(str(child.pid))
"""


def stop(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_setup_replaces_helper(tmp_path, monkeypatch, capsys):
    pid_file = tmp_path / "launchd.pid"
    monkeypatch.setenv("FAKE_LAUNCHD_PID", str(pid_file))
    m = machine(tmp_path, monkeypatch, commands={"launchctl": FAKE_LAUNCHD})
    first, home = m["first"], m["home"]
    old = subprocess.Popen([sys.executable, "-m", "fact_checker.cli", "serve", "--port", str(first)], env=os.environ.copy(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    foreign = other = None
    try:
        assert wait(lambda: listening(first)), f"FAIL S38 A3 · the old helper does not listen on {first}"
        foreign = Foreign(first + 4)
        other = subprocess.Popen([sys.executable, "-m", "fact_checker.cli", "serve", "--port", str(first + 3)],
                                 env=os.environ | {"FACT_CHECKER_HOME": str(tmp_path / "other-home")},
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert wait(lambda: listening(first + 3)), "FAIL S38 A3 · the other home's helper does not listen"

        # Case 1 · setup → exit 0, the old helper has stopped, the other program and the other home's helper still answer
        code, out = run(monkeypatch, capsys, "setup")
        assert code == 0, f"FAIL S38 A3 · setup exit {code}: {out}"
        try:
            old.wait(timeout=10)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"FAIL S38 A3 · the old helper {old.pid} still runs")
        assert foreign.answers(), "FAIL S38 A3 · setup stopped another program"
        assert (health(first + 3) or {}).get("home") == str(tmp_path / "other-home"), \
            "FAIL S38 A3 · setup stopped the helper of another home"

        # Case 2 · the login agent runs `serve` with no port, and its helper answers on 8765 with a new process
        agent = plistlib.loads((m["user"] / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist").read_bytes())
        assert agent["ProgramArguments"][-1] == "serve", f"FAIL S38 A3 · {agent['ProgramArguments']}"
        answer = health(first)
        assert answer and answer["app"] == "fact-checker" and answer["home"] == str(home), \
            f"FAIL S38 A3 · no login helper on {first}: {answer}"
        assert answer["pid"] == int(pid_file.read_text()) != old.pid, f"FAIL S38 A3 · not the login helper: {answer}"

        # Case 3 · doctor → the helper line is ok on 8765
        code, check = helper_check(monkeypatch, capsys)
        assert check == {"name": "helper", "state": f"running on port {first}", "fix": "", "ok": True}, \
            f"FAIL S38 A3 · {check}"
    finally:
        if old.poll() is None:
            old.kill()
            old.wait()
        if pid_file.exists():
            stop(int(pid_file.read_text()))
        if foreign:
            foreign.stop()
        if other and other.poll() is None:
            other.kill()
            other.wait()
    print("PASS S38 A3 · Setup replaces an old helper")


# S38 A4 · A sandboxed check says to step out
#
# Story: Codex runs `fact-checker doctor --json` inside its sandbox, where a local connection fails with "Operation not
# permitted". The helper check is not ok, says "blocked by the agent's sandbox", and its fix says to run
# `fact-checker setup` and `doctor` outside the sandbox with the person's approval.
#
# Setup: a temporary user home and helper home, and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT).
# PATH holds only fake commands: `claude` logged in, `uv`, `yt-dlp`, `ffmpeg`, `chromium`. The sandbox is faked as
# measured in Codex's Seatbelt sandbox: every socket connection raises PermissionError [Errno 1] Operation not
# permitted. Codex itself never runs.

def sandboxed(self, address):
    raise PermissionError(errno.EPERM, "Operation not permitted")


def test_doctor_sandbox(tmp_path, monkeypatch, capsys):
    machine(tmp_path, monkeypatch)
    monkeypatch.setattr(socket.socket, "connect", sandboxed)

    # Case 1 · doctor --json in the sandbox → the helper check is not ok and says "blocked by the agent's sandbox"
    code, check = helper_check(monkeypatch, capsys)
    assert code == 1, f"FAIL S38 A4 · doctor exit {code} in the sandbox"
    assert check["ok"] is False and check["state"] == "blocked by the agent's sandbox", f"FAIL S38 A4 · {check}"

    # Case 2 · its fix → run setup and doctor outside the sandbox, with the person's approval
    fix = check["fix"]
    for words in ("fact-checker setup", "fact-checker doctor", "outside the sandbox", "the person's approval"):
        assert words in fix, f"FAIL S38 A4 · the fix lacks {words!r}: {fix}"

    # Case 3 · the text doctor → the same helper line, never "not running"
    code, out = run(monkeypatch, capsys, "doctor")
    helper = [line for line in out if line.startswith("helper:")]
    assert helper == [f"helper: blocked by the agent's sandbox · fix: {fix}"], f"FAIL S38 A4 · {helper}"
    print("PASS S38 A4 · A sandboxed check says to step out")


# S39 A1 · Setup reads with the provider it is given
#
# Story: On a Mac where Claude and Codex are both logged in, the agent runs `fact-checker setup --provider codex`. The
# settings file says `provider = "codex"`, the other lines of an existing settings file stay as they were, and doctor's
# provider line says `codex`. With Codex not logged in, setup stops with "codex: not logged in · fix: codex login" and
# changes nothing.
#
# Setup: the S38 machine for each case: a temporary user home and helper home, five free local ports in place of
# 8765–8769, and the system is macOS. PATH holds only fakes: `claude` logged in, `codex` logged in by
# FAKE_CODEX_LOGGED, `uv`, `yt-dlp`, `ffmpeg`, `chromium`, and `launchctl` that only logs its arguments. The ChatGPT
# app search points at an empty temporary folder. A connection to the real 8765–8769 fails the test.

def test_setup_provider(tmp_path, monkeypatch, capsys):
    def mac(case: str, codex_logged: bool, config: str | None = None) -> dict:
        root = tmp_path / case
        root.mkdir()
        m = machine(root, monkeypatch, commands={"codex": FAKE_CODEX})
        no_app(root, monkeypatch)
        monkeypatch.setenv("FAKE_CODEX_LOGGED", "1" if codex_logged else "0")
        if config is not None:
            (m["home"] / "config.toml").write_text(config)
        return m

    # Case 1 · no settings file, Claude and Codex logged in, setup --provider codex → provider "codex", doctor says codex
    m = mac("new", codex_logged=True)
    code, out = run(monkeypatch, capsys, "setup", "--provider", "codex")
    assert code == 0, f"FAIL S39 A1 · setup exit {code}: {out}"
    assert tomllib.loads((m["home"] / "config.toml").read_text())["provider"] == "codex", \
        f"FAIL S39 A1 · {(m['home'] / 'config.toml').read_text()}"
    assert "# [models]" in (m["home"] / "config.toml").read_text(), "FAIL S39 A1 · the new settings lost their comments"
    assert doctor_check(monkeypatch, capsys, "provider")["state"] == "codex", "FAIL S39 A1 · doctor's provider line"

    # Case 2 · a settings file that says claude → only its top provider line changes, a table's provider line stays
    own = '# mine\nprovider = "claude"\nscreen = false\n\n[roles.search]\nprovider = "claude"\nmodel = "haiku"\n'
    m = mac("own", codex_logged=True, config=own)
    code, out = run(monkeypatch, capsys, "setup", "--provider", "codex")
    assert code == 0, f"FAIL S39 A1 · setup exit {code}: {out}"
    assert (m["home"] / "config.toml").read_text() == own.replace('provider = "claude"', 'provider = "codex"', 1), \
        f"FAIL S39 A1 · {(m['home'] / 'config.toml').read_text()!r}"
    assert doctor_check(monkeypatch, capsys, "provider")["state"] == "codex", "FAIL S39 A1 · doctor's provider line"

    # Case 3 · a settings file with no provider line → the line is added and every other line stays
    own = '# mine\nscreen = false\n\n[models]\nparts = "opus"\n'
    m = mac("no-line", codex_logged=True, config=own)
    code, out = run(monkeypatch, capsys, "setup", "--provider", "codex")
    assert code == 0, f"FAIL S39 A1 · setup exit {code}: {out}"
    text = (m["home"] / "config.toml").read_text()
    assert tomllib.loads(text)["provider"] == "codex" and own in text, f"FAIL S39 A1 · {text!r}"

    # Case 4 · Codex not logged in → one line "codex: not logged in · fix: codex login", exit 1, nothing changed
    own = '# mine\nprovider = "claude"\n'
    m = mac("logged-out", codex_logged=False, config=own)
    code, out = run(monkeypatch, capsys, "setup", "--provider", "codex")
    assert code == 1, f"FAIL S39 A1 · setup exit {code} with Codex logged out"
    assert "codex: not logged in · fix: codex login" in out, f"FAIL S39 A1 · {out}"
    assert (m["home"] / "config.toml").read_text() == own, "FAIL S39 A1 · setup changed the settings file"
    assert [p.name for p in m["home"].iterdir()] == ["config.toml"], "FAIL S39 A1 · setup wrote into the helper home"
    assert calls(m["env"]) == [], f"FAIL S39 A1 · setup started the helper: {calls(m['env'])}"
    print("PASS S39 A1 · Setup reads with the provider it is given")


# S39 A2 · Setup finds the Codex of the ChatGPT app
#
# Story: `codex` is not on the PATH, but the ChatGPT app holds it at
# `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`. The agent runs `fact-checker setup --provider
# codex`. Doctor says "codex: logged in", and the login helper's PATH holds that folder, so its readings find Codex.
#
# Setup: the S38 machine: a temporary user home and helper home, five free local ports in place of 8765–8769, and the
# system is macOS. PATH holds only fakes: `claude` logged in, `uv`, `yt-dlp`, `ffmpeg`, `chromium`, and `launchctl`
# that only logs its arguments; there is no `codex`. The ChatGPT app is a temporary folder in place of /Applications
# (the helper's search location is replaced), and its `codex` is a fake that answers `login status` with exit 0. The
# real ChatGPT app never runs. A connection to the real 8765–8769 fails the test.

def test_codex_in_chatgpt_app(tmp_path, monkeypatch, capsys):
    m = machine(tmp_path, monkeypatch)
    codex = no_app(tmp_path, monkeypatch)
    codex.parent.mkdir(parents=True)
    codex.write_text(f"#!{sys.executable}\n{FAKE_CODEX}")
    codex.chmod(0o755)
    monkeypatch.setenv("FAKE_CODEX_LOGGED", "1")
    assert shutil.which("codex") is None, "FAIL S39 A2 · codex is on the PATH of the test"

    # Case 1 · setup --provider codex → exit 0, provider "codex"
    code, out = run(monkeypatch, capsys, "setup", "--provider", "codex")
    assert code == 0, f"FAIL S39 A2 · setup exit {code}: {out}"
    assert 'provider = "codex"' in (m["home"] / "config.toml").read_text(), "FAIL S39 A2 · the provider line"

    # Case 2 · doctor → "codex: logged in", ok
    check = doctor_check(monkeypatch, capsys, "codex")
    assert check["state"] == "logged in" and check["ok"], f"FAIL S39 A2 · {check}"

    # Case 3 · the login helper's PATH keeps the shell's PATH and adds the app's folder, where `codex` is found
    agent = plistlib.loads((m["user"] / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist").read_bytes())
    path = agent["EnvironmentVariables"]["PATH"]
    assert path.split(os.pathsep)[0] == m["env"]["PATH"], f"FAIL S39 A2 · the shell's PATH is gone: {path}"
    assert shutil.which("codex", path=path) == str(codex), f"FAIL S39 A2 · the login helper finds no codex: {path}"
    print("PASS S39 A2 · Setup finds the Codex of the ChatGPT app")


# S39 A3 · One command switches the reader
#
# Story: The person's agent runs `fact-checker provider codex`. The settings file now says `codex`, the login helper
# restarts, and the analyse button's spend line names Codex. `fact-checker provider` alone prints the provider in use.
#
# Setup: the S38 machine: a temporary user home and helper home, five free local ports in place of 8765–8769, and the
# system is macOS. PATH holds only fakes: `claude` logged in, `codex` logged in by FAKE_CODEX_LOGGED, `uv`, `yt-dlp`,
# `ffmpeg`, `chromium`, and `launchctl` and `systemctl` that only log their arguments. The ChatGPT app search points at
# an empty temporary folder. The settings file says `provider = "claude"`. The helper's HTTP handler runs in this
# process on the first free port with the temporary helper home; its /provider answer picks the spend line (S30 A3).
# A connection to the real 8765–8769 fails the test.

def test_provider_command(tmp_path, monkeypatch, capsys):
    m = machine(tmp_path, monkeypatch, commands={"codex": FAKE_CODEX})
    no_app(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_LOGGED", "1")
    home, log = m["home"], tmp_path / "calls.jsonl"
    own = '# mine\nprovider = "claude"\n\n[models]\nparts = "opus"\n'
    (home / "config.toml").write_text(own)
    helper = ThreadingHTTPServer(("127.0.0.1", m["first"]), handler(Helper(home)))
    threading.Thread(target=helper.serve_forever, daemon=True).start()

    def spend_provider() -> str:
        with urllib.request.urlopen(f"http://127.0.0.1:{m['first']}/provider", timeout=5) as res:
            return json.loads(res.read())["provider"]

    try:
        # Case 1 · provider alone → "provider: claude", exit 0, nothing changed
        code, out = run(monkeypatch, capsys, "provider")
        assert (code, out) == (0, ["provider: claude"]), f"FAIL S39 A3 · {code} {out}"
        assert (home / "config.toml").read_text() == own and calls(m["env"]) == [], "FAIL S39 A3 · provider changed things"

        # Case 2 · provider codex on macOS → the settings say codex, other lines stay, launchd restarts the login helper
        code, out = run(monkeypatch, capsys, "provider", "codex")
        assert code == 0, f"FAIL S39 A3 · provider codex exit {code}: {out}"
        assert (home / "config.toml").read_text() == own.replace('"claude"', '"codex"', 1), \
            f"FAIL S39 A3 · {(home / 'config.toml').read_text()!r}"
        assert calls(m["env"]) == [["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/com.fact-checker.helper"]], \
            f"FAIL S39 A3 · the login helper did not restart: {calls(m['env'])}"

        # Case 3 · the helper names codex to the analyse button, which then shows the spend line of Codex
        assert spend_provider() == "codex", f"FAIL S39 A3 · /provider says {spend_provider()}"

        # Case 4 · provider alone → "provider: codex"
        code, out = run(monkeypatch, capsys, "provider")
        assert (code, out) == (0, ["provider: codex"]), f"FAIL S39 A3 · {code} {out}"

        # Case 5 · provider claude on Linux → claude, systemd restarts the login helper
        log.unlink()
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        code, out = run(monkeypatch, capsys, "provider", "claude")
        assert code == 0 and spend_provider() == "claude", f"FAIL S39 A3 · provider claude exit {code}: {out}"
        assert calls(m["env"]) == [["systemctl", "--user", "restart", "fact-checker.service"]], \
            f"FAIL S39 A3 · the login helper did not restart: {calls(m['env'])}"

        # Case 6 · provider codex with Codex not logged in → "codex: not logged in · fix: codex login", exit 1, no change
        log.unlink()
        monkeypatch.setenv("FAKE_CODEX_LOGGED", "0")
        code, out = run(monkeypatch, capsys, "provider", "codex")
        assert code == 1 and "codex: not logged in · fix: codex login" in out, f"FAIL S39 A3 · {code} {out}"
        assert (home / "config.toml").read_text() == own and calls(m["env"]) == [], "FAIL S39 A3 · a logged-out switch"
    finally:
        helper.shutdown()
        helper.server_close()
    print("PASS S39 A3 · One command switches the reader")


# `fact-checker setup` gives a new person a settings file that names their provider and a commented keys file, and
# never overwrites their own.

def test_new_home_gets_commented_examples(tmp_path):
    settings_files(tmp_path, "codex")
    assert tomllib.loads((tmp_path / "config.toml").read_text()) == {"provider": "codex", "feedback_url": "https://fact-checker-feedback.alexgcalvet7.workers.dev"}
    assert read_env(tmp_path) == {}
    assert "TAVILY_API_KEY" in (tmp_path / ".env").read_text()


def test_existing_files_stay(tmp_path):
    (tmp_path / "config.toml").write_text('provider = "codex"\n')
    (tmp_path / ".env").write_text("HF_TOKEN=x\n")
    settings_files(tmp_path, "claude")
    assert (tmp_path / "config.toml").read_text() == 'provider = "codex"\n'
    assert (tmp_path / ".env").read_text() == "HF_TOKEN=x\n"


# S40 A1 · The check shows what the helper finds
#
# Story: The login helper runs with a search path that holds no yt-dlp, while the agent's terminal finds it. The agent
# runs `fact-checker doctor`. The yt-dlp line says "the helper does not find yt-dlp" with the fix `fact-checker setup`,
# and is not ok. The same holds for ffmpeg, uv and the command of the provider in use.
#
# Setup: the S38 machine: a temporary user home and helper home, and five free local ports in place of 8765–8769
# (FACT_CHECKER_PORT), so "8765" below is the first of them. The agent's PATH holds only fakes: `claude` logged in,
# `codex` logged in, `uv`, `yt-dlp`, `ffmpeg`, `chromium`. The ChatGPT app search points at an empty temporary folder,
# in the agent and in the helper. The helper is a real `fact-checker serve --port 8765` that the test starts with a
# PATH of its own, as the login agent does: first a folder with every fake but yt-dlp, then an empty folder. A
# connection to the real 8765–8769 fails the test. The test stops each helper it starts.

# The helper process, with the ChatGPT app search pointed at a folder that does not exist.
SERVE = """\
import sys
from pathlib import Path
from fact_checker.adapters import llm_codex_cli
llm_codex_cli.CHATGPT_CODEX = Path(sys.argv[1])
from fact_checker import cli
sys.argv = ["fact-checker", "serve", "--port", sys.argv[2]]
cli.main()
"""


def test_doctor_from_helper(tmp_path, monkeypatch, capsys):
    m = machine(tmp_path, monkeypatch, commands={"codex": FAKE_CODEX})
    no_app(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_LOGGED", "1")
    first, agent_bin = m["first"], tmp_path / "bin"
    helper_bin = tmp_path / "helper-bin"
    helper_bin.mkdir()
    for name in ("claude", "codex", "uv", "ffmpeg", "chromium"):
        shutil.copy(agent_bin / name, helper_bin / name)
    started = []

    def start_helper(path) -> None:
        env = os.environ | {"PATH": str(path), "FAKE_CODEX_LOGGED": "1"}
        started.append(subprocess.Popen([sys.executable, "-c", SERVE, str(tmp_path / "no-app" / "codex"), str(first)],
                                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        assert wait(lambda: health(first)), f"FAIL S40 A1 · the helper does not answer on {first}"

    def stop_helpers() -> None:
        for child in started:
            child.terminate()
            child.wait(timeout=10)
        started.clear()
        assert wait(lambda: not listening(first)), f"FAIL S40 A1 · a helper still listens on {first}"

    def missing(name: str) -> dict:
        return {"name": name, "state": f"the helper does not find {name}", "fix": "fact-checker setup", "ok": False}

    try:
        # Case 1 · the helper's PATH has no yt-dlp → /health says so, from the helper's own PATH
        start_helper(helper_bin)
        assert health(first).get("tools") == {"claude": True, "uv": True, "yt-dlp": False, "ffmpeg": True}, \
            f"FAIL S40 A1 · /health tools: {health(first).get('tools')}"

        # Case 2 · the agent finds yt-dlp, the helper does not → "the helper does not find yt-dlp", fix setup, not ok
        assert doctor_check(monkeypatch, capsys, "yt-dlp") == missing("yt-dlp"), "FAIL S40 A1 · the yt-dlp line"
        assert run(monkeypatch, capsys, "doctor", "--json")[0] == 1, \
            "FAIL S40 A1 · doctor passed with the helper missing yt-dlp"

        # Case 3 · the tools the helper finds keep the agent's line: claude logged in, uv and ffmpeg ok
        assert doctor_check(monkeypatch, capsys, "claude")["state"] == "logged in", "FAIL S40 A1 · the claude line"
        for name in ("uv", "ffmpeg"):
            assert doctor_check(monkeypatch, capsys, name) == {"name": name, "state": "ok", "fix": "", "ok": True}, \
                f"FAIL S40 A1 · the {name} line"

        # Case 4 · the helper's PATH is empty → ffmpeg, uv and claude also say the helper does not find them
        stop_helpers()
        start_helper(tmp_path / "empty")
        for name in ("claude", "uv", "yt-dlp", "ffmpeg"):
            assert doctor_check(monkeypatch, capsys, name) == missing(name), f"FAIL S40 A1 · the {name} line"

        # Case 5 · the provider in use is codex → /health names codex, not claude; the codex line says the helper
        # does not find it
        (m["home"] / "config.toml").write_text('provider = "codex"\n')
        assert set(health(first)["tools"]) == {"codex", "uv", "yt-dlp", "ffmpeg"}, \
            f"FAIL S40 A1 · /health tools for codex: {health(first)['tools']}"
        assert doctor_check(monkeypatch, capsys, "codex") == missing("codex"), "FAIL S40 A1 · the codex line"

        # Case 6 · no helper answers → the lines are the agent's own again: yt-dlp ok
        stop_helpers()
        assert doctor_check(monkeypatch, capsys, "yt-dlp") == {"name": "yt-dlp", "state": "ok", "fix": "", "ok": True}, \
            "FAIL S40 A1 · the yt-dlp line with no helper"
    finally:
        for child in started:
            child.terminate()
            child.wait(timeout=10)
    print("PASS S40 A1 · The check shows what the helper finds")


REFUSED = "claude: inside the Claude app, it moves on each update · fix: curl -fsSL https://claude.ai/install.sh | bash"


# S40 A2 · Setup refuses a Claude that moves on update
#
# Story: The only `claude` on the agent's search path lives under the Claude app's versioned folder, such as
# `…/Claude/claude-code/2.1.299/…`. The agent runs `fact-checker setup --provider claude`. Setup stops with "claude:
# inside the Claude app, it moves on each update · fix: curl -fsSL https://claude.ai/install.sh | bash" and starts no
# helper.
#
# Setup: the S38 machine: a temporary user home and helper home, five free local ports in place of 8765–8769, and the
# system is macOS. PATH holds only fakes: `uv`, `yt-dlp`, `ffmpeg`, `chromium`, and `launchctl` and `systemctl` that
# only log their arguments. The only `claude`, logged in, is in
# `<user home>/Library/Application Support/Claude/claude-code/2.1.299/`, the Claude app's folder of one version. A
# connection to the real 8765–8769 fails the test.

def test_versioned_claude(tmp_path, monkeypatch, capsys):
    m = machine(tmp_path, monkeypatch)
    user, first = m["user"], m["first"]
    app = user / "Library" / "Application Support" / "Claude" / "claude-code" / "2.1.299"
    app.mkdir(parents=True)
    shutil.move(tmp_path / "bin" / "claude", app / "claude")
    monkeypatch.setenv("PATH", f"{app}{os.pathsep}{tmp_path / 'bin'}")
    agent = user / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist"

    # Case 1 · setup --provider claude → the refusal line, exit 1
    code, out = run(monkeypatch, capsys, "setup", "--provider", "claude")
    assert code == 1, f"FAIL S40 A2 · setup exit {code}: {out}"
    assert REFUSED in out, f"FAIL S40 A2 · the refusal: {out}"

    # Case 2 · no helper started: no login agent file, no launchctl call, nothing on the five ports
    assert not agent.exists(), f"FAIL S40 A2 · setup wrote {agent}"
    assert calls(m["env"]) == [], f"FAIL S40 A2 · setup called {calls(m['env'])}"
    assert not any(listening(p) for p in range(first, first + 5)), "FAIL S40 A2 · a helper answers"

    # Case 3 · setup with no provider and no settings → it does not pick the versioned Claude either
    code, out = run(monkeypatch, capsys, "setup")
    assert code == 1 and not agent.exists() and calls(m["env"]) == [], f"FAIL S40 A2 · setup picked it: {code} {out}"

    # Case 4 · doctor → the claude line gives the same refusal and fix, not ok
    assert doctor_check(monkeypatch, capsys, "claude") == {
            "name": "claude", "state": "inside the Claude app, it moves on each update",
            "fix": "curl -fsSL https://claude.ai/install.sh | bash", "ok": False}, "FAIL S40 A2 · doctor's claude line"

    # Case 5 · the standalone claude in ~/.local/bin → setup --provider claude goes on and starts the helper
    local = user / ".local" / "bin"
    local.mkdir(parents=True)
    shutil.copy(app / "claude", local / "claude")
    monkeypatch.setenv("PATH", f"{local}{os.pathsep}{tmp_path / 'bin'}")
    code, out = run(monkeypatch, capsys, "setup", "--provider", "claude")
    assert code == 0 and REFUSED not in out and agent.exists(), f"FAIL S40 A2 · the stable claude: {code} {out}"
    print("PASS S40 A2 · Setup refuses a Claude that moves on update")
