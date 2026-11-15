"""S39 A1 · Setup reads with the provider it is given

Story: On a Mac where Claude and Codex are both logged in, the agent runs `fact-checker setup --provider codex`. The
settings file says `provider = "codex"`, the other lines of an existing settings file stay as they were, and doctor's
provider line says `codex`. With Codex not logged in, setup stops with "codex: not logged in · fix: codex login" and
changes nothing.

Setup: the S38 machine for each case: a temporary user home and helper home, five free local ports in place of
8765–8769, and the system is macOS. PATH holds only fakes: `claude` logged in, `codex` logged in by
FAKE_CODEX_LOGGED, `uv`, `yt-dlp`, `ffmpeg`, `chromium`, and `launchctl` that only logs its arguments. The ChatGPT
app search points at an empty temporary folder. A connection to the real 8765–8769 fails the test.
"""
import tomllib

from s38_fakes import machine, run
from s39_fakes import FAKE_CODEX, calls, doctor_check, no_app


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
