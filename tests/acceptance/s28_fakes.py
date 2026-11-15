"""The fakes that the S28 helper tests share: a fake collector of shared analyses and an invented shared analysis.

The fake collector runs on a free local port. `PUT /analyses/<id>?lang=` keeps the body and answers 201;
`GET /analyses/<id>?lang=` answers the analysis it holds for that video and language, else 404. It records every
request: method, path, query, headers and body.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SHARED_VIDEO = "sharedv1"


def _flag(id, t, type, label, quote):
    return {"id": id, "t": t, "speaker": "Invitado", "quote": quote, "type": type, "label": label,
            "reason": "Motivo inventado.", "confidence": 0.9, "related": None,
            "sources": [{"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}]
            if type == "inaccuracy" else [], "note": None, "on_player": True,
            "judge": {"verdict": "keep", "reason": "Se sostiene."}}


# A whole Spanish analysis of an invented video, as a helper uploads it.
ANALYSIS = {
    "video_id": SHARED_VIDEO, "lang": "es", "spoken": "es", "status": "done", "published_at": "2026-11-10",
    "title": "Entrevista inventada", "channel": "Canal inventado", "duration": 23.0, "speakers": {},
    "readers": {"parts": {"provider": "claude", "model": "opus"}, "verdict": {"provider": "claude", "model": "opus"},
                "judge": {"provider": "claude", "model": "opus"}, "search": {"provider": "claude", "model": "sonnet"}},
    "cost_usd": 7.9, "analysed_until": 23.0, "helper_version": "0.1.0",
    "flags": [_flag("ad_hominem-3.0", 3.0, "fallacy", "ad_hominem", "mi rival es un mentiroso"),
              _flag("false-5.0", 5.0, "inaccuracy", "false", "el paro bajó a la mitad en un año")],
}


class FakeCollector:
    def __init__(self, analyses: dict | None = None):
        self.analyses = dict(analyses or {})  # (video_id, lang) -> analysis
        self.requests = []
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
                body = json.loads(self.rfile.read(length)) if length else None
                collector.requests.append({"method": self.command, "path": url.path, "query": parse_qs(url.query),
                                           "headers": dict(self.headers), "body": body})
                return url.path.removeprefix("/analyses/"), parse_qs(url.query).get("lang", [""])[0], body

            def do_PUT(self):
                video, lang, body = self._record()
                collector.analyses[(video, lang)] = body["analysis"]
                self._reply(201, {"stored": True})

            def do_GET(self):
                video, lang, _ = self._record()
                found = collector.analyses.get((video, lang))
                self._reply(200, found) if found else self._reply(404, {"error": "not found"})

            def do_POST(self):
                self._record()
                self._reply(200, {"stored": 0})

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def puts(self) -> list[dict]:
        return [r for r in self.requests if r["method"] == "PUT"]

    def wait_puts(self, n: int, seconds: float = 5) -> list[dict]:
        end = time.monotonic() + seconds
        while len(self.puts()) < n and time.monotonic() < end:
            time.sleep(0.05)
        return self.puts()

    def stop(self):
        self.httpd.shutdown()
