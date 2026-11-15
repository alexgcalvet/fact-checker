"""S27 A1 · A mark reaches the collector by itself

Story: A tester marks an ad hominem card as fair. Within a second the author's collector gets one request with that
mark only (video, second, type, label, quote, confidence, verdict, reason, provider, model, helper version, install id),
and the card answers at once even when the collector is slow. The tester marks a false-figure card: the next request
holds only that mark. Two marks given at the same instant are each sent once. Edge case: a changed verdict of a sent
mark goes out again with the new verdict.

Setup: a temporary helper home with a flag file of 3 flags that names its readers (claude, opus), and an older flag
file of 1 flag with no readers whose usage log names the part model "sonnet". `config.toml` sets `feedback_url` to a
fake collector on a free local port; a second fake collector holds each request 2 seconds before it answers. The
helper HTTP server on another free port. Failing fake `claude` and `codex` commands on PATH. No `/feedback` request
is made: every send comes from the marks.
"""
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from s23_fakes import fail_clis
from s24_fakes import FALLACY, FIGURE, LATER, OLD, OLD_VIDEO, VIDEO, FakeCollector, home_with_flags, request, \
    start_helper

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
MARK_FIELDS = {"video_id", "flag_id", "t", "type", "label", "quote", "confidence", "verdict", "reason", "provider",
               "model"}


def wait_for(check, seconds=1.0):
    """True as soon as `check()` holds, False after `seconds`."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return check()


class SlowCollector:
    """Answers each POST /marks after 2 seconds and keeps its body."""

    def __init__(self):
        self.posts = []
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                time.sleep(2)
                collector.posts.append(body)
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()


def mark(port, video, flag, verdict, reason=""):
    return request(port, f"/videos/{video}/marks", {"flag_id": flag["id"], "verdict": verdict, "reason": reason})


def test_mark_sends_itself(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    home_with_flags(home)
    collector, slow = FakeCollector(), SlowCollector()
    (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
    port, stop = start_helper(home)
    try:
        # Case 1 · one mark → within a second one request holds that mark only, with every field
        assert mark(port, VIDEO, FALLACY, "correct", "sí") == (200, {"ok": True})
        assert wait_for(lambda: len(collector.posts) == 1), collector.posts
        body = collector.posts[0]
        assert set(body) == {"install_id", "helper_version", "marks"}
        assert UUID.fullmatch(body["install_id"]), body["install_id"]
        assert isinstance(body["helper_version"], str) and body["helper_version"]
        assert body["marks"] == [{
            "video_id": VIDEO, "flag_id": FALLACY["id"], "t": 42.0, "type": "fallacy", "label": "ad_hominem",
            "quote": FALLACY["quote"], "confidence": 0.85, "verdict": "correct", "reason": "sí",
            "provider": "claude", "model": "opus"}]
        assert str(tmp_path) not in json.dumps(body)

        # Case 2 · a second mark → the next request holds only that mark, with the same install id
        mark(port, VIDEO, FIGURE, "unfair", "es 11 %")
        assert wait_for(lambda: len(collector.posts) == 2), collector.posts
        assert [(m["flag_id"], m["verdict"], m["reason"]) for m in collector.posts[1]["marks"]] == [
            (FIGURE["id"], "unfair", "es 11 %")]
        assert collector.posts[1]["install_id"] == body["install_id"]

        # Case 3 · a sent mark changes its verdict → it goes out again with the new verdict
        mark(port, VIDEO, FIGURE, "correct")
        assert wait_for(lambda: len(collector.posts) == 3), collector.posts
        assert [(m["flag_id"], m["verdict"]) for m in collector.posts[2]["marks"]] == [(FIGURE["id"], "correct")]

        # Case 4 · two marks at the same instant → each one is sent exactly once
        both = [threading.Thread(target=mark, args=(port, VIDEO, LATER, "unfair")),
                threading.Thread(target=mark, args=(port, OLD_VIDEO, OLD, "correct"))]
        for t in both:
            t.start()
        for t in both:
            t.join()
        sent = lambda: [m["flag_id"] for p in collector.posts[3:] for m in p["marks"]]
        assert wait_for(lambda: len(sent()) >= 2), collector.posts
        time.sleep(0.5)
        assert sorted(sent()) == sorted([LATER["id"], OLD["id"]]), sent()
        old = next(m for p in collector.posts[3:] for m in p["marks"] if m["flag_id"] == OLD["id"])
        assert (old["provider"], old["model"], old["t"]) == (None, "sonnet", 10.0)

        # Case 5 · a collector that takes 2 seconds → the mark is answered at once, and still reaches it
        (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{slow.url}"\n')
        began = time.monotonic()
        assert mark(port, VIDEO, FALLACY, "unfair", "no") == (200, {"ok": True})
        assert time.monotonic() - began < 0.5
        assert wait_for(lambda: len(slow.posts) == 1, 4), slow.posts
        assert [m["flag_id"] for m in slow.posts[0]["marks"]] == [FALLACY["id"]]

        # Case 6 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
        collector.stop()
        slow.stop()
    print("PASS S27 A1 · A mark reaches the collector by itself")
