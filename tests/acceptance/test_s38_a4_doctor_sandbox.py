"""S38 A4 · A sandboxed check says to step out

Story: Codex runs `fact-checker doctor --json` inside its sandbox, where a local connection fails with "Operation not
permitted". The helper check is not ok, says "blocked by the agent's sandbox", and its fix says to run
`fact-checker setup` and `doctor` outside the sandbox with the person's approval.

Setup: a temporary user home and helper home, and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT).
PATH holds only fake commands: `claude` logged in, `uv`, `yt-dlp`, `ffmpeg`, `chromium`. The sandbox is faked as
measured in Codex's Seatbelt sandbox: every socket connection raises PermissionError [Errno 1] Operation not
permitted. Codex itself never runs.
"""
import errno
import socket

from s38_fakes import helper_check, machine, run


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
