"""S28 A1 · A whole analysis uploads its flags; a partial one does not

Story: A tester with sharing on clicks "Analizar este vídeo" at 0:00 on an invented 23-second interview. When the
analysis ends, the collector gets one upload for that video and language "es": the flags, the judge's verdicts, the
readers (claude, opus), `lang`, `spoken`, the cost, the helper version and the counts of checked claims and
questions per speaker (S35), and no mark, stop reason or other field.
The tester starts another video at 0:15: its analysis ends with the first 15 seconds unread, and nothing is uploaded.

Setup: s26_fakes (a fake `yt-dlp` with invented captions, a fake `claude` that answers by schema, a failing `codex`),
a temporary helper home whose `config.toml` points `feedback_url` to the S28 fake collector on a free local port, and
the helper's own HTTP server on another free port. Each case posts `/videos/<id>?from=<s>&lang=es` as the extension
does, then polls the flag file until it is no longer running.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker import server

from s26_fakes import setup
from s28_fakes import FakeCollector

ALLOWED = {"video_id", "lang", "spoken", "status", "published_at", "title", "channel", "duration", "speakers",
           "claims", "questions", "readers", "cost_usd", "analysed_until", "helper_version", "flags"}


def analyse(base: str, video: str, start: int) -> dict:
    urllib.request.urlopen(urllib.request.Request(f"{base}/videos/{video}?from={start}&lang=es", method="POST"),
                           timeout=10)
    for _ in range(300):
        try:
            data = json.loads(urllib.request.urlopen(f"{base}/videos/{video}?at={start}", timeout=10).read())
            if data["status"] != "running":
                return data
        except urllib.error.HTTPError:
            pass
        time.sleep(0.1)
    raise AssertionError(f"FAIL S28 A1 · the analysis of {video} did not finish in 30 s")


def test_whole_analysis_uploads(tmp_path, monkeypatch):
    home, _ = setup(tmp_path, monkeypatch)
    collector = FakeCollector()
    (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        # Case 1 · the whole video read from 0:00 → one PUT /analyses/esview?lang=es
        data = analyse(base, "esview", 0)
        assert data["status"] == "done", f"FAIL S28 A1 · {data['status']} ({data.get('stop_reason')})"
        puts = collector.wait_puts(1)
        assert len(puts) == 1, f"FAIL S28 A1 · {len(puts)} uploads after a whole analysis"
        put = puts[0]
        assert put["path"] == "/analyses/esview" and put["query"] == {"lang": ["es"]}, \
            f"FAIL S28 A1 · uploaded to {put['path']} {put['query']}"

        # Case 2 · the body → the install id and the stripped analysis, nothing else
        body = put["body"]
        assert set(body) == {"install_id", "analysis"}, f"FAIL S28 A1 · body fields {sorted(body)}"
        assert body["install_id"] == (home / "install-id").read_text().strip(), "FAIL S28 A1 · not the install id"
        shared = body["analysis"]
        assert set(shared) <= ALLOWED, f"FAIL S28 A1 · extra fields {sorted(set(shared) - ALLOWED)}"
        assert {"flags", "readers", "lang", "spoken", "cost_usd", "helper_version", "status"} <= set(shared), \
            f"FAIL S28 A1 · missing fields {sorted({'flags', 'readers', 'lang', 'spoken', 'cost_usd', 'helper_version'} - set(shared))}"
        assert (shared["video_id"], shared["lang"], shared["spoken"], shared["status"]) == ("esview", "es", "es", "done")
        assert shared["readers"]["parts"] == {"provider": "claude", "model": "opus"}, \
            f"FAIL S28 A1 · readers {shared['readers']}"

        # Case 3 · the flags → the same flags as the local file, with no mark
        local = json.loads((home / "videos" / "esview.json").read_text())
        assert shared["flags"] and [f["id"] for f in shared["flags"]] == [f["id"] for f in local["flags"]], \
            "FAIL S28 A1 · the uploaded flags differ from the local ones"
        assert all("mark" not in f for f in shared["flags"]), "FAIL S28 A1 · a mark was uploaded"

        # Case 4 · a video started at 0:15 → done, the first 15 seconds unread, no upload
        data = analyse(base, "enview", 15)
        assert data["status"] == "done", f"FAIL S28 A1 · {data['status']} ({data.get('stop_reason')})"
        assert all(f["t"] >= 15 for f in data["flags"]), "FAIL S28 A1 · the first 15 seconds were read"
        time.sleep(1.5)
        assert len(collector.puts()) == 1, "FAIL S28 A1 · a partial analysis was uploaded"
    finally:
        httpd.shutdown()
        collector.stop()
    print("PASS S28 A1 · A whole analysis uploads its flags; a partial one does not")
