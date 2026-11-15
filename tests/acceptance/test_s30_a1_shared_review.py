"""S30 A1 (helper part) · Only the owner's approved analyses are served

Story: A stranger uploads an analysis of video "abcdefgh" in Spanish: the collector answers 202 and serves nothing for
it. The owner runs `fact-checker shared list` and sees one line: abcdefgh, es, opus, 2 flags, the uploader's install id
and the date. `fact-checker shared approve abcdefgh es` makes it served to anyone; `reject` on another one deletes it
and it is never served. An upload from the owner's own helper (with the admin token in its `.env`) is served at once.
A row shared before this slice is pending until the owner approves it.

Setup: a fake collector on a free local port that holds 2 pending uploads (abcdefgh and otherone, in Spanish), answers
the owner's list, approve and reject only with the admin token, answers 404 to a review of an unknown video, and records
every request with its Authorization header. A temporary helper home whose `config.toml` sets `feedback_url` to it.
Failing fake `claude` and `codex` commands on PATH. What the collector stores and serves is checked in
s30-a1-collector-review.test.ts.
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from fact_checker import analyses, cli
from s23_fakes import fail_clis
from s28_fakes import ANALYSIS

TOKEN = "invented-admin-token"
STRANGER = "11111111-1111-4111-8111-111111111111"
PENDING = [
    {"video_id": "abcdefgh", "lang": "es", "model": "opus", "flags": 2, "install_id": STRANGER,
     "received_at": "2026-11-15T10:00:00.000Z"},
    {"video_id": "otherone", "lang": "es", "model": "sonnet", "flags": 5, "install_id": STRANGER,
     "received_at": "2026-11-15T11:00:00.000Z"},
]


class ReviewCollector:
    def __init__(self):
        self.pending, self.requests = [dict(r) for r in PENDING], []
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, code, body):
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _record(self):
                url = urlparse(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                collector.requests.append({"method": self.command, "path": url.path, "query": parse_qs(url.query),
                                           "auth": self.headers.get("Authorization"),
                                           "body": json.loads(self.rfile.read(length)) if length else None})
                return url

            def do_GET(self):
                self._record()
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self._reply(401, {"error": "unauthorized"})
                self._reply(200, {"rows": collector.pending})

            def do_POST(self):
                url = self._record()
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self._reply(401, {"error": "unauthorized"})
                _, _, video, action = url.path.split("/")
                lang = parse_qs(url.query).get("lang", [""])[0]
                found = [r for r in collector.pending if (r["video_id"], r["lang"]) == (video, lang)]
                if not found:
                    return self._reply(404, {"error": "nothing pending"})
                collector.pending = [r for r in collector.pending if r not in found]
                self._reply(200, {"approved" if action == "approve" else "rejected": True})

            def do_PUT(self):
                self._record()
                self._reply(202, {"pending": True})

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()


def run(monkeypatch, capsys, *args) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out


def test_shared_review(tmp_path, monkeypatch, capsys):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    home.mkdir()
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.delenv("FEEDBACK_ADMIN_TOKEN", raising=False)
    collector = ReviewCollector()
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    try:
        # Case 1 · no admin token → the list names FEEDBACK_ADMIN_TOKEN and exits 1
        code, out = run(monkeypatch, capsys, "shared", "list")
        assert code == 1 and "FEEDBACK_ADMIN_TOKEN" in out, f"FAIL S30 A1 · no token: {code} {out!r}"

        # Case 2 · the token in .env → one line per pending upload: video, lang, model, flags, install id, date
        (home / ".env").write_text(f"FEEDBACK_ADMIN_TOKEN={TOKEN}\n")
        code, out = run(monkeypatch, capsys, "shared", "list")
        assert code == 0, f"FAIL S30 A1 · list exited {code}: {out!r}"
        line = next((x for x in out.splitlines() if "abcdefgh" in x), "")
        for part in ("abcdefgh", " es ", "opus", "2 flags", STRANGER, "2026-11-15"):
            assert part in f" {line} ", f"FAIL S30 A1 · the list line misses {part!r}: {line!r}"
        assert "otherone" in out and TOKEN not in out
        assert collector.requests[-1]["path"] == "/analyses" and collector.requests[-1]["auth"] == f"Bearer {TOKEN}"

        # Case 3 · approve abcdefgh es → POST /analyses/abcdefgh/approve?lang=es with the token; exit 0
        code, out = run(monkeypatch, capsys, "shared", "approve", "abcdefgh", "es")
        last = collector.requests[-1]
        assert code == 0, f"FAIL S30 A1 · approve exited {code}: {out!r}"
        assert (last["method"], last["path"], last["query"], last["auth"]) == \
            ("POST", "/analyses/abcdefgh/approve", {"lang": ["es"]}, f"Bearer {TOKEN}")

        # Case 4 · reject otherone es → POST /analyses/otherone/reject?lang=es; the list is then empty
        code, out = run(monkeypatch, capsys, "shared", "reject", "otherone", "es")
        last = collector.requests[-1]
        assert code == 0 and (last["method"], last["path"]) == ("POST", "/analyses/otherone/reject"), \
            f"FAIL S30 A1 · reject: {code} {last['path']}"
        code, out = run(monkeypatch, capsys, "shared", "list")
        assert code == 0 and "0 pending" in out, f"FAIL S30 A1 · empty list: {out!r}"

        # Case 5 · approve a video with nothing pending → the video named, exit 1
        code, out = run(monkeypatch, capsys, "shared", "approve", "zzzzzzzz", "en")
        assert code == 1 and "zzzzzzzz" in out, f"FAIL S30 A1 · unknown video: {code} {out!r}"

        # Case 6 · the owner's helper uploads → the PUT carries the admin token; a tester's helper sends none
        analyses.upload(home, collector.url, ANALYSIS)
        assert collector.requests[-1]["method"] == "PUT" and collector.requests[-1]["auth"] == f"Bearer {TOKEN}", \
            "FAIL S30 A1 · the owner's upload has no admin token"
        (home / ".env").write_text("")
        analyses.upload(home, collector.url, ANALYSIS)
        assert collector.requests[-1]["method"] == "PUT" and collector.requests[-1]["auth"] is None, \
            "FAIL S30 A1 · a tester's upload carries an Authorization header"

        # Case 7 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        collector.stop()
    print("PASS S30 A1 · Only the owner's approved analyses are served (the helper side)")
