"""The fakes that the S24 tests share: a helper home with invented flags and marks, the helper HTTP server,
and a fake collector in the shape of tests/fakes/collector/marks.json.

The fake collector runs on a free local port, keeps every POST body, and answers a GET only with the admin token.
"""
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fact_checker.server import Helper, handler
from fact_checker.store import Store

VIDEO = "abcdefgh"
OLD_VIDEO = "zyxwvuts"
TOKEN = "invented-admin-token"
READERS = {"parts": {"provider": "claude", "model": "opus"}, "verdict": {"provider": "claude", "model": "opus"},
           "judge": {"provider": "claude", "model": "opus"}, "search": {"provider": "claude", "model": "sonnet"}}


def flag(id, t, type, label, quote):
    return {"id": id, "t": t, "speaker": "Invitado", "quote": quote, "type": type, "label": label,
            "reason": "Motivo inventado.", "confidence": 0.85, "related": None, "sources": [], "note": None,
            "on_player": True}


FALLACY = flag("ad_hominem-42.0", 42.0, "fallacy", "ad_hominem", "usted no sabe nada de esto")
FIGURE = flag("false-90.0", 90.0, "inaccuracy", "false", "el paro bajó a la mitad en un año")
LATER = flag("straw_man-120.0", 120.0, "fallacy", "straw_man", "ustedes quieren cerrar todas las empresas")
OLD = flag("false_dilemma-10.0", 10.0, "fallacy", "false_dilemma", "o subimos impuestos o cerramos hospitales")


def home_with_flags(home: Path) -> Store:
    """A helper home with a new flag file (with `readers`) of 3 flags, and an older one (no `readers`) whose usage log
    names the part model."""
    store = Store(home)
    store.save({"video_id": VIDEO, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
                "readers": READERS, "flags": [FALLACY, FIGURE, LATER]})
    store.save({"video_id": OLD_VIDEO, "published_at": "2026-11-01", "status": "done", "stop_reason": None,
                "flags": [OLD]})
    store.log_usage({"ts": "2026-11-01T10:00:00+00:00", "video_id": OLD_VIDEO, "step": "analyze_chunk",
                     "model": "sonnet"})
    return store


def start_helper(home: Path):
    """The helper HTTP server on a free local port; returns (port, stop)."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1], httpd.shutdown


def request(port, path, body=None, method=None):
    """A JSON request to the helper; returns (status, body)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class FakeCollector:
    """POST /marks keeps the body and answers {"stored": n}, or the status in `fail`. GET /marks?since= answers the rows
    received after `since`, only with `Authorization: Bearer <TOKEN>`."""

    def __init__(self, rows: list[dict] = (), fail: int | None = None):
        self.posts, self.reads, self.rows, self.fail = [], [], list(rows), fail
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, code, body):
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if collector.fail:
                    return self._reply(collector.fail, {"error": "refused"})
                collector.posts.append(body)
                now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                collector.rows += [m | {"install_id": body["install_id"], "helper_version": body["helper_version"],
                                        "received_at": now} for m in body["marks"]]
                self._reply(200, {"stored": len(body["marks"])})

            def do_GET(self):
                url = urlparse(self.path)
                collector.reads.append({"path": url.path, "query": parse_qs(url.query),
                                        "auth": self.headers.get("Authorization")})
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self._reply(401, {"error": "unauthorized"})
                since = parse_qs(url.query).get("since", [""])[0]
                self._reply(200, {"rows": [r for r in collector.rows if r["received_at"] > since]})

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
