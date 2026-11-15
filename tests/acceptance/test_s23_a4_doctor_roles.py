"""S23 A4 · Doctor lists each step's provider and every missing key

Story: With the A3 settings and no keys, the person runs `fact-checker doctor`. It prints one line per step, such as
"role parts: chat · some-model · https://router.huggingface.co/v1", then "HF_TOKEN: missing", "ANTHROPIC_API_KEY:
missing" and "TAVILY_API_KEY: missing", each with its fix and never a key value, and exits 1.

Setup: a Linux machine (platform.system replaced) whose PATH holds only fake `uv`, `yt-dlp`, `ffmpeg` and `chromium`
commands, and failing fake `claude` and `codex` commands. A temporary user home (HOME) and helper home
(FACT_CHECKER_HOME) with the `config.toml` of each case: `provider = "anthropic"` with `[roles.parts]` and
`[roles.search]` on `https://router.huggingface.co/v1`, `key_env = "HF_TOKEN"` and `model = "some-model"`; in the last
case `provider = "chat"` on a local Ollama address with no key. A small HTTP server stands for the running helper on a
free local port. No API key in the environment.
"""
import platform
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fact_checker import cli

SECRETS = {"HF_TOKEN": "hf_invented_secret", "ANTHROPIC_API_KEY": "sk-ant-invented-secret",
           "TAVILY_API_KEY": "tvly-invented-secret"}
ROUTER = "https://router.huggingface.co/v1"
MIXED = ('provider = "anthropic"\n'
         f'[roles.parts]\nprovider = "chat"\nbase_url = "{ROUTER}"\nkey_env = "HF_TOKEN"\nmodel = "some-model"\n'
         f'[roles.search]\nprovider = "chat"\nbase_url = "{ROUTER}"\nkey_env = "HF_TOKEN"\nmodel = "some-model"\n')
FAILING_CLI = "import sys\nsys.exit(1)\n"


def run(monkeypatch, capsys, *args) -> tuple[int, list[str]]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out.splitlines()


class Helper(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


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
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Helper)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = str(httpd.server_address[1])

    # Case 1 · mixed roles and no key → one line per step with its provider, model and address; each missing key once,
    # with its fix; exit 1
    (home / "config.toml").write_text(MIXED)
    code, out = run(monkeypatch, capsys, "doctor", "--port", port)
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
    code, out = run(monkeypatch, capsys, "doctor", "--port", port)
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
    code, out = run(monkeypatch, capsys, "doctor", "--port", port)
    assert "role parts: chat · llama3 · http://localhost:11434/v1" in out, out
    assert not [x for x in out if x.startswith("CHAT_API_KEY")], out
    assert f"TAVILY_API_KEY: missing · fix: add TAVILY_API_KEY=<key> to {home / '.env'}" in out, out
    assert code == 1, (code, out)
    httpd.shutdown()
    print("PASS S23 A4 · Doctor lists each step's provider and every missing key")
