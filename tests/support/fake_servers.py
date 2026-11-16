"""Fakes that several suites share: a local JSON server and a published fact-check search that finds nothing."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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


class NoPublishedChecks:
    def __init__(self, key):
        pass

    def search(self, query, language):
        return []
