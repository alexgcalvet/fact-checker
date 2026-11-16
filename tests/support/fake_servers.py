"""Fakes of local servers that several suites share: a JSON server, and the feedback collector."""
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TOKEN = "invented-admin-token"


class FakeServer:
    """A local JSON server on a free port. It records every POST and answers it with `answer(body)`: the status code
    and the reply, a dict or a raw string."""

    def __init__(self):
        self.requests, self.lock = [], threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with fake.lock:
                    fake.requests.append({"path": self.path, "headers": self.headers, "body": body})
                    code, reply = fake.answer(body)
                raw = (reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def stop(self):
        self.httpd.shutdown()


class FakeCollector:
    """The feedback collector on a free local port, in the shape of tests/fakes/collector/marks.json. It records every
    request: method, path, query, Authorization header and body.

    - POST /marks keeps the body in `posts` and its marks as rows, and answers {"stored": n}. It waits `delay` seconds
      first, and answers the status in `fail` instead when it is set.
    - GET /marks?since= answers the rows received after `since`, only with `Authorization: Bearer <TOKEN>`.
    - PUT /analyses/<id>?lang= keeps the analysis and answers 201.
    - GET /analyses/<id>?lang= answers the analysis it holds for that video and language, else 404.
    - GET /analyses answers the `pending` uploads, and POST /analyses/<id>/approve|reject?lang= takes one off them,
      both only with the admin token; a review of a video with nothing pending answers 404.
    """

    def __init__(self, rows: list[dict] = (), analyses: dict | None = None, pending: list[dict] = (),
                 fail: int | None = None, delay: float = 0):
        self.rows, self.analyses, self.pending = list(rows), dict(analyses or {}), [dict(r) for r in pending]
        self.fail, self.delay, self.requests, self.posts = fail, delay, [], []
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
                                           "auth": self.headers.get("Authorization"), "body": body})
                return url.path, parse_qs(url.query), body

            def _admin(self):
                return self.headers.get("Authorization") == f"Bearer {TOKEN}"

            def do_POST(self):
                path, query, body = self._record()
                if path == "/marks":
                    time.sleep(collector.delay)
                    if collector.fail:
                        return self._reply(collector.fail, {"error": "refused"})
                    collector.posts.append(body)
                    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                    collector.rows += [m | {"install_id": body["install_id"], "helper_version": body["helper_version"],
                                            "received_at": now} for m in body["marks"]]
                    return self._reply(200, {"stored": len(body["marks"])})
                if not self._admin():
                    return self._reply(401, {"error": "unauthorized"})
                _, _, video, action = path.split("/")
                lang = query.get("lang", [""])[0]
                found = [r for r in collector.pending if (r["video_id"], r["lang"]) == (video, lang)]
                if not found:
                    return self._reply(404, {"error": "nothing pending"})
                collector.pending = [r for r in collector.pending if r not in found]
                self._reply(200, {"approved" if action == "approve" else "rejected": True})

            def do_GET(self):
                path, query, _ = self._record()
                if path.startswith("/analyses/"):
                    found = collector.analyses.get((path.removeprefix("/analyses/"), query.get("lang", [""])[0]))
                    return self._reply(200, found) if found else self._reply(404, {"error": "not found"})
                if not self._admin():
                    return self._reply(401, {"error": "unauthorized"})
                if path == "/analyses":
                    return self._reply(200, {"rows": collector.pending})
                since = query.get("since", [""])[0]
                self._reply(200, {"rows": [r for r in collector.rows if r["received_at"] > since]})

            def do_PUT(self):
                path, query, body = self._record()
                collector.analyses[(path.removeprefix("/analyses/"), query.get("lang", [""])[0])] = body["analysis"]
                self._reply(201, {"stored": True})

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
