"""S25 A2 · Setup picks the logged-in subscription and keeps an existing settings file

Story: A person with no `~/.fact-checker/config.toml` runs `fact-checker setup`. With Claude Code logged in, the new
settings file says `provider = "claude"`; with only Codex logged in, `provider = "codex"`; with neither, setup prints
one line, "provider: no agent CLI logged in", with the fix, writes no settings file and starts nothing. A settings file
that says `provider = "codex"` stays byte for byte, also when Claude Code is logged in.

Setup: a temporary user home (HOME) and a new helper home (FACT_CHECKER_HOME) for each case. PATH holds only fakes:
`claude` answers `auth status --json` with loggedIn from FAKE_CLAUDE_LOGGED and fails any other call; `codex` answers
`login status` with exit 0 when FAKE_CODEX_LOGGED is 1 and fails any other call; `uv`, `yt-dlp`, `ffmpeg` and
`chromium` exist; `launchctl` and `systemctl` only write their arguments to a log. The system is Linux.
"""
import json
import platform
import sys
import tomllib
from pathlib import Path

from fact_checker import cli

FAKE_CLAUDE = """\
import json, os, sys
if sys.argv[1:3] != ["auth", "status"]:
    sys.exit(1)
print(json.dumps({"loggedIn": os.environ.get("FAKE_CLAUDE_LOGGED") == "1"}))
"""
FAKE_CODEX = """\
import os, sys
sys.exit(0 if sys.argv[1:3] == ["login", "status"] and os.environ.get("FAKE_CODEX_LOGGED") == "1" else 1)
"""
FAKE_RECORDER = """\
import json, os, sys
open(os.environ["FAKE_LOG"], "a").write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\\n")
"""


def test_provider_detection(tmp_path, monkeypatch, capsys):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, code in {"claude": FAKE_CLAUDE, "codex": FAKE_CODEX, "launchctl": FAKE_RECORDER,
                       "systemctl": FAKE_RECORDER, "uv": "", "yt-dlp": "", "ffmpeg": "", "chromium": ""}.items():
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
        monkeypatch.setattr(sys, "argv", ["fact-checker", "setup", "--port", "8765"])
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
