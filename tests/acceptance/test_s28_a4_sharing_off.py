"""S28 A4 · With sharing off nothing is uploaded, and downloading still works

Story: A tester unticks "Compartir mis marcas y análisis" in ⚙ and analyses a whole video: the collector gets no
upload. The same tester opens a video that the collector holds in Spanish and sees its flags at once.

Setup: s26_fakes (a fake `yt-dlp` with invented captions, a fake `claude` that answers by schema, a failing `codex`),
the S28 fake collector on a free local port holding the invented Spanish analysis, a temporary helper home whose
`config.toml` points `feedback_url` to it, and the helper's own HTTP server on another free port. The ⚙ box is the
S27 one: it posts `/share` with `{"share": false}`.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker import server

from s24_fakes import request
from s26_fakes import readings, setup
from s28_fakes import ANALYSIS, SHARED_VIDEO, FakeCollector


def test_sharing_off(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    collector = FakeCollector({(SHARED_VIDEO, "es"): ANALYSIS})
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_port
    base = f"http://127.0.0.1:{port}"
    try:
        # Case 1 · the ⚙ box unticked → sharing off
        assert request(port, "/share", {"share": False}) == (200, {"share": False})

        # Case 2 · a whole analysis from 0:00 → done, and no upload
        urllib.request.urlopen(urllib.request.Request(f"{base}/videos/esview?from=0&lang=es", method="POST"),
                               timeout=10)
        data = None
        for _ in range(300):
            try:
                data = json.loads(urllib.request.urlopen(f"{base}/videos/esview?at=0", timeout=10).read())
                if data["status"] != "running":
                    break
            except urllib.error.HTTPError:
                pass
            time.sleep(0.1)
        assert data and data["status"] == "done", f"FAIL S28 A4 · the analysis did not end done: {data}"
        time.sleep(1.5)
        assert collector.puts() == [], "FAIL S28 A4 · an analysis was uploaded with sharing off"

        # Case 3 · a video the collector holds in Spanish → its flags at once, with no reading
        before = len(readings(log))
        status, shared = request(port, f"/videos/{SHARED_VIDEO}?at=0&lang=es")
        assert status == 200 and shared.get("source") == "shared", f"FAIL S28 A4 · download with sharing off: {status}"
        assert [f["id"] for f in shared["flags"]] == [f["id"] for f in ANALYSIS["flags"]]
        assert len(readings(log)) == before, "FAIL S28 A4 · an LLM reading ran for a shared video"
    finally:
        httpd.shutdown()
        collector.stop()
    print("PASS S28 A4 · With sharing off nothing is uploaded, and downloading still works")
