"""S39 A2 · Setup finds the Codex of the ChatGPT app

Story: `codex` is not on the PATH, but the ChatGPT app holds it at
`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`. The agent runs `fact-checker setup --provider
codex`. Doctor says "codex: logged in", and the login helper's PATH holds that folder, so its readings find Codex.

Setup: the S38 machine: a temporary user home and helper home, five free local ports in place of 8765–8769, and the
system is macOS. PATH holds only fakes: `claude` logged in, `uv`, `yt-dlp`, `ffmpeg`, `chromium`, and `launchctl`
that only logs its arguments; there is no `codex`. The ChatGPT app is a temporary folder in place of /Applications
(the helper's search location is replaced), and its `codex` is a fake that answers `login status` with exit 0. The
real ChatGPT app never runs. A connection to the real 8765–8769 fails the test.
"""
import os
import plistlib
import shutil
import sys

from s38_fakes import machine, run
from s39_fakes import FAKE_CODEX, doctor_check, no_app


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
