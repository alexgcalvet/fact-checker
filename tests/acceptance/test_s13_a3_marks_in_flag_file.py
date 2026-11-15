"""S13 A3 · The helper returns the person's latest mark on each flag

Story: The person marked a card unfair and then correct. When the extension asks for the flag file, that flag
comes with the mark "correct", and flags with no mark come without one.

Setup: a temporary helper home with the flag file of one video holding two flags, and a marks log line of
another video that shares the id of the second flag; the helper HTTP server on a free local port.
"""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker.server import Helper, handler
from fact_checker.store import Store

VIDEO = "abcdefgh"
OTHER = "zyxwvuts"


def flag(id, t, label):
    return {"id": id, "t": t, "speaker": "guest", "quote": f"frase {t}", "type": "fallacy", "label": label,
            "reason": "Motivo.", "confidence": 0.85, "related": None, "sources": [], "note": None, "on_player": True}


MARKED = flag("ad_hominem-42.0", 42.0, "ad_hominem")
UNMARKED = flag("straw_man-90.0", 90.0, "straw_man")


def request(port, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read())


def test_marks_in_flag_file(tmp_path):
    store = Store(tmp_path)
    store.save({"video_id": VIDEO, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
                "flags": [MARKED, UNMARKED]})
    store.save({"video_id": OTHER, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
                "flags": [UNMARKED]})
    store.add_mark(OTHER, UNMARKED, "unfair", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        # Case 1 · a flag marked unfair, then correct → the flag file comes with the mark "correct"
        request(port, f"/videos/{VIDEO}/marks", {"flag_id": MARKED["id"], "verdict": "unfair", "reason": "no"})
        request(port, f"/videos/{VIDEO}/marks", {"flag_id": MARKED["id"], "verdict": "correct", "reason": ""})
        flags = {f["id"]: f for f in request(port, f"/videos/{VIDEO}")["flags"]}
        assert flags[MARKED["id"]]["mark"] == "correct"

        # Case 2 · a flag with no mark in this video (only in another video) → no mark
        assert "mark" not in flags[UNMARKED["id"]]

        # Case 3 · the flag file on disk → keeps no mark; the marks log stays the only record
        assert all("mark" not in f for f in store.load(VIDEO)["flags"])
    finally:
        httpd.shutdown()
    print("PASS S13 A3 · The helper returns the person's latest mark on each flag")
