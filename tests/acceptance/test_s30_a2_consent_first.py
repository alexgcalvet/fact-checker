"""S30 A2 (helper part) · Nothing is shared before the person says yes

Story: A new tester has never answered. They click "✓ De acuerdo" on a card: a box asks "¿Compartir tus marcas y
análisis con el autor para mejorar el detector? Se envían el aviso, la frase, tu motivo y el vídeo; nada de tu equipo."
with "Sí, compartir", "No" and a link to the privacy notice (in English with an English browser). Until they answer,
the collector gets nothing. "Sí, compartir" sends that mark and later whole analyses; "No" keeps them on the laptop.
The next mark or analysis asks nothing.

Setup: s26_fakes (a fake `yt-dlp` with invented captions, a fake `claude` that answers by schema, a failing `codex`),
the S28 fake collector on a free local port (it records every PUT and POST), a temporary helper home whose
`config.toml` holds only `feedback_url` (a new install: never answered), and the helper's own HTTP server on another
free port. The box itself is checked in s30-a2-consent-question.test.ts; its answer reaches the helper as `POST /share`.
"""
import json
import threading
import time
import tomllib
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from fact_checker import server

from s24_fakes import request
from s26_fakes import setup
from s28_fakes import FakeCollector

EXAMPLE = Path(server.__file__).parent / "config.example.toml"


def analyse(base: str, video: str, lang: str) -> dict:
    urllib.request.urlopen(urllib.request.Request(f"{base}/videos/{video}?from=0&lang={lang}", method="POST"),
                           timeout=10)
    for _ in range(300):
        try:
            data = json.loads(urllib.request.urlopen(f"{base}/videos/{video}?at=0", timeout=10).read())
            if data["status"] != "running":
                return data
        except urllib.error.HTTPError:
            pass
        time.sleep(0.1)
    raise AssertionError(f"FAIL S30 A2 · the analysis of {video} did not finish in 30 s")


def mark(port: int, video: str, flag_id: str) -> tuple:
    return request(port, f"/videos/{video}/marks", {"flag_id": flag_id, "verdict": "correct", "reason": ""})


def test_consent_first(tmp_path, monkeypatch):
    home, _ = setup(tmp_path, monkeypatch)
    monkeypatch.delenv("FEEDBACK_ADMIN_TOKEN", raising=False)
    collector = FakeCollector()
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_port
    base = f"http://127.0.0.1:{port}"
    posts = lambda: [r for r in collector.requests if r["method"] == "POST"]  # noqa: E731
    try:
        # Case 1 · the settings that setup copies → no share_marks line: a new install has not answered
        assert "share_marks" not in tomllib.loads(EXAMPLE.read_text()), \
            "FAIL S30 A2 · config.example.toml answers the question for the person"

        # Case 2 · never answered → GET /share says null (not asked), not true
        assert request(port, "/share") == (200, {"share": None}), f"FAIL S30 A2 · {request(port, '/share')}"

        # Case 3 · never answered, a whole analysis → done, and no upload
        data = analyse(base, "esview", "es")
        assert data["status"] == "done" and data["flags"], f"FAIL S30 A2 · {data['status']}"
        time.sleep(1.5)
        assert collector.puts() == [], "FAIL S30 A2 · an analysis was uploaded before the answer"

        # Case 4 · never answered, a mark → kept, and nothing sent
        assert mark(port, "esview", data["flags"][0]["id"]) == (200, {"ok": True})
        time.sleep(1)
        assert posts() == [], "FAIL S30 A2 · a mark was sent before the answer"

        # Case 5 · "Sí, compartir" → share_marks = true; the next mark goes, and the next whole analysis uploads
        assert request(port, "/share", {"share": True}) == (200, {"share": True})
        assert tomllib.loads((home / "config.toml").read_text())["share_marks"] is True
        assert mark(port, "esview", data["flags"][-1]["id"]) == (200, {"ok": True})
        end = time.monotonic() + 2
        while not posts() and time.monotonic() < end:
            time.sleep(0.05)
        assert [m["flag_id"] for p in posts() for m in p["body"]["marks"]] == [data["flags"][-1]["id"]], \
            "FAIL S30 A2 · after yes, the new mark was not sent alone"
        assert analyse(base, "enview", "en")["status"] == "done"
        assert len(collector.wait_puts(1)) == 1, "FAIL S30 A2 · after yes, the whole analysis was not uploaded"

        # Case 6 · "No" → share_marks = false; GET /share says false; a mark sends nothing
        assert request(port, "/share", {"share": False}) == (200, {"share": False})
        assert request(port, "/share") == (200, {"share": False})
        sent = len(posts())
        assert mark(port, "enview", analyse(base, "enview", "en")["flags"][0]["id"]) == (200, {"ok": True})
        time.sleep(1)
        assert len(posts()) == sent, "FAIL S30 A2 · a mark was sent after no"
        assert len(collector.puts()) == 1, "FAIL S30 A2 · an analysis was uploaded after no"
    finally:
        httpd.shutdown()
        collector.stop()
    print("PASS S30 A2 · Nothing is shared before the person says yes (the helper side)")
