"""S38 A1 · The check knows the helper by its answer

Story: The person's agent runs `fact-checker doctor` while another program answers on port 8765. The helper line says
"another program holds port 8765" and is not ok. With the real helper running and its home writable, it says
"running on port 8766" (the port it found) and is ok.

Setup: a temporary user home and helper home, and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT), so
"8765" below is the first of them. PATH holds only fake commands: `claude` logged in, `uv`, `yt-dlp`, `ffmpeg`,
`chromium`. Another program is a small web server that answers every request with an HTML 404. The real helper is the
helper's HTTP handler on the second port, with the temporary helper home.
"""
import os
import threading
from http.server import ThreadingHTTPServer

from s38_fakes import Foreign, health, helper_check, machine

from fact_checker import feedback
from fact_checker.server import Helper, handler


def test_doctor_knows_helper(tmp_path, monkeypatch, capsys):
    m = machine(tmp_path, monkeypatch)
    first, home = m["first"], m["home"]
    foreign = Foreign(first)
    helper = None
    try:
        # Case 1 · another program answers on the first port, no helper → "another program holds port 8765", not ok
        code, check = helper_check(monkeypatch, capsys)
        assert check["state"] == f"another program holds port {first}", f"FAIL S38 A1 · {check}"
        assert check["ok"] is False and code == 1, f"FAIL S38 A1 · a foreign program passed: {check}"

        # Case 2 · the real helper on the second port → /health names it, "running on port 8766", ok
        helper = ThreadingHTTPServer(("127.0.0.1", first + 1), handler(Helper(home)))
        threading.Thread(target=helper.serve_forever, daemon=True).start()
        answer = health(first + 1)
        assert {k: v for k, v in answer.items() if k != "tools"} == {"app": "fact-checker", "version": feedback.helper_version(), "pid": os.getpid(),
                          "home": str(home), "writable": True}, f"FAIL S38 A1 · /health: {answer}"
        code, check = helper_check(monkeypatch, capsys)
        assert check == {"name": "helper", "state": f"running on port {first + 1}", "fix": "", "ok": True}, \
            f"FAIL S38 A1 · {check}"

        # Case 3 · the helper's home is not writable → /health says so, the helper line is not ok
        home.chmod(0o555)
        assert health(first + 1)["writable"] is False, "FAIL S38 A1 · /health says a read-only home is writable"
        code, check = helper_check(monkeypatch, capsys)
        assert check["ok"] is False and check["state"].startswith(f"running on port {first + 1}"), \
            f"FAIL S38 A1 · a helper that cannot write passed: {check}"
        assert str(home) in check["state"] and "fact-checker setup" in check["fix"], f"FAIL S38 A1 · {check}"
    finally:
        home.chmod(0o755)
        foreign.stop()
        if helper:
            helper.shutdown()
            helper.server_close()
    print("PASS S38 A1 · The check knows the helper by its answer")
