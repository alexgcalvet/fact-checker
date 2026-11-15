"""S40 A2 · Setup refuses a Claude that moves on update

Story: The only `claude` on the agent's search path lives under the Claude app's versioned folder, such as
`…/Claude/claude-code/2.1.299/…`. The agent runs `fact-checker setup --provider claude`. Setup stops with "claude:
inside the Claude app, it moves on each update · fix: curl -fsSL https://claude.ai/install.sh | bash" and starts no
helper.

Setup: the S38 machine: a temporary user home and helper home, five free local ports in place of 8765–8769, and the
system is macOS. PATH holds only fakes: `uv`, `yt-dlp`, `ffmpeg`, `chromium`, and `launchctl` and `systemctl` that
only log their arguments. The only `claude`, logged in, is in
`<user home>/Library/Application Support/Claude/claude-code/2.1.299/`, the Claude app's folder of one version. A
connection to the real 8765–8769 fails the test.
"""
import os
import shutil

from s38_fakes import listening, machine, run
from s39_fakes import calls, doctor_check

REFUSED = "claude: inside the Claude app, it moves on each update · fix: curl -fsSL https://claude.ai/install.sh | bash"


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
