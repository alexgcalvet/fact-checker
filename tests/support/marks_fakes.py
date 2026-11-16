"""The fakes that the S24 tests share: a helper home with invented flags and marks, and the helper HTTP server."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from fact_checker.server import Helper, handler
from fact_checker.store import Store

VIDEO = "abcdefgh"
OLD_VIDEO = "zyxwvuts"
READERS = {"parts": {"provider": "claude", "model": "opus"}, "verdict": {"provider": "claude", "model": "opus"},
           "judge": {"provider": "claude", "model": "opus"}, "search": {"provider": "claude", "model": "sonnet"}}


def shown_flag(id, t, type, label, quote):
    return {"id": id, "t": t, "speaker": "Invitado", "quote": quote, "type": type, "label": label,
            "reason": "Motivo inventado.", "confidence": 0.85, "related": None, "sources": [], "note": None,
            "on_player": True}


FALLACY = shown_flag("ad_hominem-42.0", 42.0, "fallacy", "ad_hominem", "usted no sabe nada de esto")
FIGURE = shown_flag("false-90.0", 90.0, "inaccuracy", "false", "el paro bajó a la mitad en un año")
LATER = shown_flag("straw_man-120.0", 120.0, "fallacy", "straw_man", "ustedes quieren cerrar todas las empresas")
OLD = shown_flag("false_dilemma-10.0", 10.0, "fallacy", "false_dilemma", "o subimos impuestos o cerramos hospitales")


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
