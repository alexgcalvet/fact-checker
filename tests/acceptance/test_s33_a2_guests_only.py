"""S33 A2 · The summary image leaves out the host

Story: In the invented interview, the person marks correct one flag of the host and two of Ana Ruiz, then exports the
summary. The export page has one card, Ana Ruiz's (S35); the card and its alt text show her two flags, and nothing of
the host.

Setup: a temporary helper home with the flag file of an invented interview: the voices "Presentador" (people: host) and
"Ana Ruiz (invitada)" (people: guest, person "Ana Ruiz"), one fallacy of the host and a false figure and a fallacy of
Ana Ruiz, all three marked correct through the store. The export page comes from the helper's own HTTP server on a
free local port; the alt text comes from `summary.card` and `summary.alt_text`, and the card page from the helper's
`summary_page`, as the PNG route builds it, with no thumbnail, both from the flag file with the same marks.
"""
import re
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker import server
from fact_checker.core import summary
from fact_checker.store import Store

HOST, GUEST = "Presentador", "Ana Ruiz (invitada)"
HOST_QUOTE = "la oposición no tiene autoridad para hablar de nada"
GUEST_FALSE = "el paro bajó a la mitad en un solo año"
GUEST_FALLACY = "mis rivales no saben gestionar ni su comunidad de vecinos"


def flag(id, t, speaker, quote, type, label):
    return {"id": id, "t": t, "speaker": speaker, "quote": quote, "type": type, "label": label,
            "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "sources": [], "note": None,
            "on_player": True}


FLAGS = [flag("fallacy-30.0", 30.0, HOST, HOST_QUOTE, "fallacy", "ad_hominem"),
         flag("false-600.0", 600.0, GUEST, GUEST_FALSE, "inaccuracy", "false"),
         flag("fallacy-900.0", 900.0, GUEST, GUEST_FALLACY, "fallacy", "ad_hominem")]
FILE = {"video_id": "entrevista", "published_at": "2026-11-10", "status": "done", "stop_reason": None, "lang": "es",
        "title": "Entrevista inventada a Ana Ruiz", "channel": "Canal inventado", "duration": 3720.0,
        "speakers": {"SPEAKER_00": HOST, "SPEAKER_01": GUEST},
        "people": {HOST: {"role": "host", "person": HOST, "spoken_s": 1260, "set_by": "llm"},
                   GUEST: {"role": "guest", "person": "Ana Ruiz", "spoken_s": 2460, "set_by": "llm"}},
        "flags": FLAGS}


def test_guests_only(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "thumbnail", lambda video_id, home: None)
    store = Store(tmp_path)
    store.save(FILE)
    for f in FLAGS:
        store.add_mark("entrevista", f, "correct", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_port}/videos/entrevista/summary",
                                      timeout=10).read().decode()
    finally:
        httpd.shutdown()
    marked = FILE | {"flags": [f | {"mark": "correct"} for f in FLAGS]}
    alt = summary.alt_text(summary.card(marked, GUEST))
    image = re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>", "", server.summary_page(marked, GUEST), flags=re.S))

    # Case 1 · the export page → one card, Ana Ruiz's, and none for the host
    assert page.count("summary.png?person=") == 1 and "person=Ana+Ruiz" in page, f"FAIL S33 A2 · cards {page!r}"
    assert summary.guests(marked) == [GUEST], f"FAIL S33 A2 · cards for {summary.guests(marked)}"

    # Case 2 · the alt text → Ana Ruiz and her two flags, nothing of the host
    assert "Ana Ruiz" in alt and "el paro bajó" in alt and "Ad hominem ×1" in alt, f"FAIL S33 A2 · alt text {alt!r}"
    assert HOST not in alt and "la oposición" not in alt, f"FAIL S33 A2 · the alt text shows the host: {alt!r}"

    # Case 3 · the image → Ana Ruiz and her two flags, nothing of the host
    assert "Ana Ruiz" in image and "el paro bajó" in image and "Ad hominem" in image, "FAIL S33 A2 · Ana Ruiz's card"
    assert HOST not in image and "la oposición" not in image, "FAIL S33 A2 · the image shows the host"
    print("PASS S33 A2 · The summary image leaves out the host")
