"""S38 A2 · A taken port moves the helper and the extension follows (the helper side)

Story: Another program holds port 8765. The helper starts at login on 8766 instead, and on YouTube the "Analizar este
vídeo" button starts an analysis whose flag file appears in the helper home. With all five ports 8765–8769 taken, the
helper log says so in one line and the helper stops; it does not restart in a loop.

Setup: a temporary helper home and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT), so "8765" below
is the first of them. Another program is a small web server that answers every request with an HTML 404. The helper
runs as `fact-checker serve` with no `--port`, as the login agent starts it, in this process: the invented interview
stands in for YouTube, and failing `claude` and `codex` commands stand in for the readers. The extension side is
checked in s38-a2-extension-finds-helper.test.ts.
"""
import json
import plistlib
import sys
import threading
import urllib.request

from s23_fakes import fail_clis, fake_video
from s38_fakes import Foreign, free_ports, guard, health, wait

from fact_checker import cli, install, server

VIDEO = "abcdefgh"


def test_port_fallback(tmp_path, monkeypatch, capsys):
    fail_clis(tmp_path, monkeypatch)
    fake_video(monkeypatch)
    guard(monkeypatch)
    first = free_ports()
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.setenv("FACT_CHECKER_PORT", str(first))
    started = []

    class Recorded(server.ThreadingHTTPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            started.append(self)

    monkeypatch.setattr(server, "ThreadingHTTPServer", Recorded)
    foreigners = [Foreign(first)]
    try:
        # Case 1 · another program holds 8765, `serve` with no port → the helper answers /health on 8766
        monkeypatch.setattr(sys, "argv", ["fact-checker", "serve"])
        threading.Thread(target=cli.main, daemon=True).start()
        answer = wait(lambda: health(first + 1))
        assert answer and answer["app"] == "fact-checker" and answer["home"] == str(home), \
            f"FAIL S38 A2 · no helper on {first + 1}: {answer}"
        assert foreigners[0].answers(), "FAIL S38 A2 · the other program lost its port"

        # Case 2 · the analyse request on 8766 → 202, and the flag file of the video appears in the helper home
        req = urllib.request.Request(f"http://127.0.0.1:{first + 1}/videos/{VIDEO}?from=0&lang=es", method="POST")
        with urllib.request.urlopen(req, timeout=10) as res:
            assert res.status == 202, f"FAIL S38 A2 · analyse answered {res.status}"
        flag_file = home / "videos" / f"{VIDEO}.json"
        assert wait(flag_file.exists), f"FAIL S38 A2 · no flag file in {home / 'videos'}"
        assert json.loads(flag_file.read_text())["video_id"] == VIDEO, "FAIL S38 A2 · the flag file of another video"
        for httpd in started:
            httpd.shutdown()
            httpd.server_close()
        started.clear()
        capsys.readouterr()

        # Case 3 · all five ports taken → one log line that says so, and the helper stops with exit 0
        foreigners += [Foreign(port) for port in range(first + 1, first + 5)]
        ended = []

        def serve():
            try:
                cli.main()
            except SystemExit as end:
                ended.append(end.code or 0)
            else:
                ended.append(0)
        stopper = threading.Thread(target=serve, daemon=True)
        stopper.start()
        stopper.join(timeout=10)
        assert ended, "FAIL S38 A2 · the helper still runs with every port taken"
        code, out = ended[0], capsys.readouterr().out.splitlines()
        assert code == 0, f"FAIL S38 A2 · serve exit {code} with every port taken"
        assert len(out) == 1 and f"{first}–{first + 4}" in out[0] and "taken" in out[0], \
            f"FAIL S38 A2 · the log: {out}"

        # Case 4 · the login agent restarts the helper only after a failure, never after that clean stop
        plist = install.launchd_plist(["fact-checker", "serve"], "/usr/bin", tmp_path / "server.log")
        assert plistlib.loads(plist)["KeepAlive"] == {"SuccessfulExit": False}, \
            f"FAIL S38 A2 · launchd restarts a clean stop: {plistlib.loads(plist)['KeepAlive']}"
        assert "Restart=on-failure" in install.systemd_unit(["fact-checker", "serve"], "/usr/bin"), \
            "FAIL S38 A2 · systemd restarts a clean stop"
    finally:
        for foreign in foreigners:
            foreign.stop()
        for httpd in started:
            httpd.shutdown()
            httpd.server_close()
    print("PASS S38 A2 · A taken port moves the helper and the extension follows (helper side)")
