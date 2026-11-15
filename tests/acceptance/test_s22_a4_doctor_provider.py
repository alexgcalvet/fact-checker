"""S22 A4 · Doctor names the provider, the models and a missing key

Story: The person sets `provider = "anthropic"` and `parts = "claude-sonnet-5-5"`, with no API key, and runs
`fact-checker doctor`. It prints "provider: anthropic", the model of each step ("parts claude-sonnet-5-5, verdict
claude-opus-5-5, …"), and "ANTHROPIC_API_KEY: missing" with its fix, never a key value, and exits 1. It does not ask
for Claude Code.
Edge case: WHEN the provider is `codex` and no model is set THEN the models line says "account default" for each step,
and a line says "Run `codex debug models` to see the models your plan allows."

Setup: a Linux machine (platform.system replaced) whose PATH holds only fake `uv`, `yt-dlp`, `ffmpeg` and `chromium`
commands, and a fake `codex` that answers `login status` with exit 0 in the last case; there is no `claude`. A
temporary user home (HOME) and helper home (FACT_CHECKER_HOME) with the `config.toml` of each case. A small HTTP server
stands for the running helper on a free local port. No API key in the environment.
"""
import platform
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fact_checker import cli

SECRET = "sk-ant-invented-secret-value"


def run(monkeypatch, capsys, *args) -> tuple[int, list[str]]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out.splitlines()


class Helper(BaseHTTPRequestHandler):
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
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Helper)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = str(httpd.server_address[1])

    # Case 1 · anthropic with parts = claude-sonnet-5-5 and no key → the provider, the model of each step, the missing
    # key variable with its fix; exit 1; no line about Claude Code
    (home / "config.toml").write_text('provider = "anthropic"\n[models]\nparts = "claude-sonnet-5-5"\n')
    code, out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert code == 1, (code, out)
    assert "provider: anthropic" in out, out
    assert ("models: parts claude-sonnet-5-5, verdict claude-opus-5-5, judge claude-opus-5-5, "
            "search claude-haiku-5-5, screen claude-haiku-5-5") in out, out
    assert f"ANTHROPIC_API_KEY: missing · fix: add ANTHROPIC_API_KEY=<key> to {home / '.env'}" in out, out
    assert not [x for x in out if x.startswith("claude:")], out

    # Case 2 · the key in the helper's .env → "set", never its value; every check passes
    (home / ".env").write_text(f"ANTHROPIC_API_KEY={SECRET}\n")
    code, out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert "ANTHROPIC_API_KEY: set" in out, out
    assert not [x for x in out if SECRET in x], out
    assert code == 0, (code, out)

    # Case 3 · openai with key_env = XAI_API_KEY and no key → that variable is named, not OPENAI_API_KEY
    (home / "config.toml").write_text('provider = "openai"\n[openai]\nbase_url = "https://api.x.ai/v1"\n'
                                      'key_env = "XAI_API_KEY"\n')
    code, out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert code == 1, (code, out)
    assert f"XAI_API_KEY: missing · fix: add XAI_API_KEY=<key> to {home / '.env'}" in out, out
    assert not [x for x in out if x.startswith("OPENAI_API_KEY")], out

    # Case 4 · codex with no model → "account default" for each step and the hint to list the plan's models
    (home / "config.toml").write_text('provider = "codex"\n')
    (bin_dir / "codex").write_text(f"#!{sys.executable}\n")
    (bin_dir / "codex").chmod(0o755)
    code, out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert "provider: codex" in out, out
    assert ("models: parts account default, verdict account default, judge account default, "
            "search account default, screen account default") in out, out
    assert "Run `codex debug models` to see the models your plan allows." in out, out
    assert code == 0, (code, out)
    httpd.shutdown()
    print("PASS S22 A4 · Doctor names the provider, the models and a missing key")
