"""S39 A3 · One command switches the reader

Story: The person's agent runs `fact-checker provider codex`. The settings file now says `codex`, the login helper
restarts, and the analyse button's spend line names Codex. `fact-checker provider` alone prints the provider in use.

Setup: the S38 machine: a temporary user home and helper home, five free local ports in place of 8765–8769, and the
system is macOS. PATH holds only fakes: `claude` logged in, `codex` logged in by FAKE_CODEX_LOGGED, `uv`, `yt-dlp`,
`ffmpeg`, `chromium`, and `launchctl` and `systemctl` that only log their arguments. The ChatGPT app search points at
an empty temporary folder. The settings file says `provider = "claude"`. The helper's HTTP handler runs in this
process on the first free port with the temporary helper home; its /provider answer picks the spend line (S30 A3).
A connection to the real 8765–8769 fails the test.
"""
import json
import os
import platform
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from s38_fakes import machine, run
from s39_fakes import FAKE_CODEX, calls, no_app

from fact_checker.server import Helper, handler


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
