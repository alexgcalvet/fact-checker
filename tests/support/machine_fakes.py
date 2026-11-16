"""The fakes of the setup and doctor tests: five free local ports away from the person's 8765–8769, a machine of fake
commands, a program that is not fact-checker, and the CLI run in this process; on top of that machine (S39), a `codex`
that answers `login status` by FAKE_CODEX_LOGGED, a ChatGPT app folder that is never the real /Applications, and one
check of doctor --json.

FACT_CHECKER_PORT moves the helper's five ports to the free ones, so no test ever reaches the person's own helper.
"""
import json
import platform
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fact_checker import cli, install

HELPER_SRC = Path(__file__).resolve().parents[2] / "src" / "helper"
REAL_PORTS = range(8765, 8770)

FAKE_CLAUDE = """\
import json, sys
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True}))
"""
FAKE_RECORDER = """\
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\\n")
"""


def guard(monkeypatch) -> None:
    """Makes any connection to or bind on 8765–8769 in this process fail the test: the person's helper is there."""
    for name in ("connect", "bind"):
        real = getattr(socket.socket, name)

        def checked(self, address, real=real, name=name):
            if isinstance(address, tuple) and address[1] in REAL_PORTS:
                raise AssertionError(f"FAIL S38 · the test tried to {name} the person's port {address[1]}")
            return real(self, address)
        monkeypatch.setattr(socket.socket, name, checked)


def free_ports() -> int:
    """The first of five free consecutive local ports, never one of 8765–8769."""
    for _ in range(50):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            first = s.getsockname()[1]
        if first + 4 > 65535 or set(range(first, first + 5)) & set(REAL_PORTS):
            continue
        try:
            for port in range(first, first + 5):
                with socket.socket() as s:
                    s.bind(("127.0.0.1", port))
            return first
        except OSError:
            continue
    raise RuntimeError("no five free consecutive ports")


class Foreign:
    """Another program on a local port: it answers every GET and POST with an HTML 404, as a web server does."""

    def __init__(self, port: int):
        class Handler(BaseHTTPRequestHandler):
            def _page(self):
                raw = b"<html><body>Not Found</body></html>"
                self.send_response(404)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = _page

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def answers(self) -> bool:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.httpd.server_address[1]}/", timeout=2)
        except urllib.error.HTTPError as e:
            return e.code == 404
        except OSError:
            return False
        return False

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def health(port: int) -> dict | None:
    """The JSON of GET /health on a local port; None when nothing answers or the answer is not JSON."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as res:
            return json.loads(res.read())
    except (OSError, ValueError):
        return None


def listening(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        return True
    except OSError:
        return False


def wait(test, seconds: float = 10.0):
    """The first true value of `test()` within `seconds`, else None."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if value := test():
            return value
        time.sleep(0.05)
    return None


def machine(tmp_path: Path, monkeypatch, system: str = "Darwin", commands: dict | None = None) -> dict:
    """A temporary user home (HOME), helper home (FACT_CHECKER_HOME) and five free ports (FACT_CHECKER_PORT). PATH holds
    only fakes: `claude` logged in, `uv`, `yt-dlp`, `ffmpeg`, `chromium`, and `launchctl` and `systemctl` that only log
    their arguments, unless `commands` gives other code. A connection to 8765–8769 fails the test."""
    bin_dir, user, home = tmp_path / "bin", tmp_path / "user", tmp_path / "helper"
    for d in (bin_dir, user, home):
        d.mkdir()
    fakes = {"claude": FAKE_CLAUDE, "launchctl": FAKE_RECORDER, "systemctl": FAKE_RECORDER,
             "uv": "", "yt-dlp": "", "ffmpeg": "", "chromium": ""} | (commands or {})
    for name, code in fakes.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    first = free_ports()
    env = {"PATH": str(bin_dir), "HOME": str(user), "FACT_CHECKER_HOME": str(home), "FACT_CHECKER_PORT": str(first),
           "FAKE_LOG": str(tmp_path / "calls.jsonl"), "PYTHONPATH": str(HELPER_SRC)}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for name in ("HF_TOKEN", "FACT_CHECK_API_KEY", "FACT_CHECK_PROVIDER", "CODEX_BIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(platform, "system", lambda: system)
    guard(monkeypatch)
    return {"home": home, "user": user, "first": first, "env": env}


def run(monkeypatch, capsys, *args) -> tuple[int, list[str]]:
    """Runs `fact-checker <args>` in this process; returns the exit code and the printed lines."""
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out.splitlines()


def helper_check(monkeypatch, capsys) -> tuple[int, dict]:
    """`fact-checker doctor --json`: the exit code and its check named helper."""
    code, out = run(monkeypatch, capsys, "doctor", "--json")
    report = json.loads("\n".join(out))
    found = [c for c in report["checks"] if c["name"] == "helper"]
    assert len(found) == 1, f"FAIL S38 · one helper check: {report['checks']}"
    return code, found[0]


FAKE_CODEX = """\
import os, sys
sys.exit(0 if sys.argv[1:3] == ["login", "status"] and os.environ.get("FAKE_CODEX_LOGGED") == "1" else 1)
"""
APP_CODEX = Path("ChatGPT.app") / "Contents" / "Resources" / "codex-cli" / "bin" / "codex"


def no_app(tmp_path: Path, monkeypatch) -> Path:
    """Points the helper's ChatGPT app search at an empty temporary folder; returns where the app's codex would be."""
    codex = tmp_path / "Applications" / APP_CODEX
    monkeypatch.setattr(install, "CHATGPT_CODEX", codex)
    return codex


def doctor_check(monkeypatch, capsys, name: str) -> dict:
    """The check called `name` of `fact-checker doctor --json`."""
    code, out = run(monkeypatch, capsys, "doctor", "--json")
    found = [c for c in json.loads("\n".join(out))["checks"] if c["name"] == name]
    assert len(found) == 1, f"FAIL S39 · one {name} check: {out}"
    return found[0]


def calls(env: dict) -> list[list[str]]:
    """The calls that the fake `launchctl` and `systemctl` logged."""
    log = Path(env["FAKE_LOG"])
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
