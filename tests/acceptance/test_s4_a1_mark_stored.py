"""S4 A1 (helper part) · Marking a card keeps the mark on the laptop

Story: The person marks an ad hominem card "unfair" with the reason "es una pregunta, no un ataque". The
helper's marks log gets one line with the video, the flag, its words, its name, "unfair" and that reason.
Marking it again "correct" adds a second line; the latest mark is the one that counts. The extension part
is s4-a1-mark-buttons.test.ts; s4-a1-mark-a-card.sh runs both.

Setup: a temporary helper home with the flag file of one video holding one ad hominem flag; the helper
HTTP server on a free local port.
"""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker.server import Helper, handler
from fact_checker.store import Store

VIDEO = "abcdefgh"
FLAG = {"id": "ad_hominem-42.0", "t": 42.0, "speaker": "guest", "quote": "la oposición no tiene autoridad",
        "type": "fallacy", "label": "ad_hominem", "reason": "Ataca.", "confidence": 0.55, "related": None,
        "sources": [], "note": None, "on_player": True}


def post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status
    except urllib.error.HTTPError as e:
        return e.code


def test_mark_stored(tmp_path):
    Store(tmp_path).save({"video_id": VIDEO, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
                          "flags": [FLAG]})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    marks = tmp_path / "marks.jsonl"
    try:
        # Case 1 · an "unfair" mark with a reason → one line with video, flag, words, name, verdict, reason
        assert post(port, f"/videos/{VIDEO}/marks",
                    {"flag_id": FLAG["id"], "verdict": "unfair", "reason": "es una pregunta, no un ataque"}) == 200
        line = json.loads(marks.read_text().splitlines()[0])
        assert {k: line[k] for k in ("video_id", "flag_id", "quote", "label", "type", "verdict", "reason")} == {
            "video_id": VIDEO, "flag_id": FLAG["id"], "quote": FLAG["quote"], "label": "ad_hominem",
            "type": "fallacy", "verdict": "unfair", "reason": "es una pregunta, no un ataque"}
        assert line["confidence"] == 0.55

        # Case 2 · the same card marked "correct" → a second line; both are kept
        assert post(port, f"/videos/{VIDEO}/marks", {"flag_id": FLAG["id"], "verdict": "correct", "reason": ""}) == 200
        assert [json.loads(x)["verdict"] for x in marks.read_text().splitlines()] == ["unfair", "correct"]

        # Case 3 · a flag that the video does not have, or a verdict outside the two → rejected, no line
        assert post(port, f"/videos/{VIDEO}/marks", {"flag_id": "nope-1.0", "verdict": "unfair", "reason": ""}) == 404
        assert post(port, f"/videos/{VIDEO}/marks", {"flag_id": FLAG["id"], "verdict": "maybe", "reason": ""}) == 400
        assert len(marks.read_text().splitlines()) == 2
    finally:
        httpd.shutdown()
    print("PASS S4 A1 (helper) · Marking a card keeps the mark on the laptop")
