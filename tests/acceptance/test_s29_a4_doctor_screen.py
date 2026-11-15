"""S29 A4 · Doctor lists the screen, and no settings gives the cheap defaults

Story: With no settings file, `fact-checker doctor` prints "models: parts opus, verdict opus, judge opus, search haiku,
screen haiku". With `provider = "anthropic"` it prints `screen claude-haiku-5-5`; with `provider = "chat"` and
`parts = "llama3"` it prints "role screen: chat · llama3 · …".

Setup: a Linux machine (platform.system replaced) whose PATH holds only fake `uv`, `yt-dlp`, `ffmpeg` and `chromium`
commands, and failing fake `claude` and `codex` commands. A temporary user home (HOME) and helper home
(FACT_CHECKER_HOME) with the `config.toml` of each case. A small HTTP server stands for the running helper on a free
local port. No API key in the environment.
"""
import platform
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fact_checker import cli

FAILING_CLI = "import sys\nsys.exit(1)\n"


def run(monkeypatch, capsys, *args) -> list[str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
    except SystemExit:
        pass
    return capsys.readouterr().out.splitlines()


class Helper(BaseHTTPRequestHandler):
    def do_GET(self):  # S38: doctor knows the helper by its /health
        raw = b'{"app": "fact-checker", "writable": true}' if self.path == "/health" else b""
        self.send_response(200 if raw else 404)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


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
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Helper)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = str(httpd.server_address[1])

    # Case 1 · no settings file → haiku screens the parts and searches the figures; opus does the rest
    out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert "models: parts opus, verdict opus, judge opus, search haiku, screen haiku" in out, \
        f"FAIL S29 A4 · models line {[x for x in out if x.startswith('models')]}"
    assert "role screen: claude · haiku" in out, out

    # Case 2 · provider anthropic → claude-haiku-5-5 screens and searches
    (home / "config.toml").write_text('provider = "anthropic"\n')
    out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert ("models: parts claude-opus-5-5, verdict claude-opus-5-5, judge claude-opus-5-5, "
            "search claude-haiku-5-5, screen claude-haiku-5-5") in out, \
        f"FAIL S29 A4 · models line {[x for x in out if x.startswith('models')]}"

    # Case 3 · provider chat with only the parts model → the screen uses the parts model
    (home / "config.toml").write_text('provider = "chat"\n[models]\nparts = "llama3"\n')
    out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert "role screen: chat · llama3 · http://localhost:11434/v1" in out, \
        f"FAIL S29 A4 · role lines {[x for x in out if x.startswith('role')]}"
    httpd.shutdown()
    print("PASS S29 A4 · Doctor lists the screen, and no settings gives the cheap defaults")
