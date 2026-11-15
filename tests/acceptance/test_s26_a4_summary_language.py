"""S26 A4 · The shareable card follows the interface language

Story: A person whose flag file says `lang` "en" exports the card (S35): the image says "claims, false or misleading",
"False." and "Detected with AI", and the page says "Alt text, ready to copy" above an alt text that starts
"Profile of". A file with `lang` "es", or none, keeps the Spanish texts.

Setup: an invented flag file with one guest and a false figure marked correct, saved three times in a temporary helper
home: with `lang` "en", with `lang` "es" and with no `lang`. The image page is built from the card and the image
template, as the PNG route builds it but with no thumbnail; the share page and the alt text come from the helper's own
HTTP server on a free local port.
"""
import re
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker import server
from fact_checker.core import summary
from fact_checker.store import Store

FLAG = {"id": "false-10.0", "t": 10.0, "speaker": "Ann Lee (guest)", "quote": "unemployment fell by half in one year",
        "type": "inaccuracy", "label": "false", "reason": "It fell from 12 % to 11 %.", "confidence": 0.9,
        "related": None, "sources": [{"publisher": "BLS", "url": "https://www.bls.gov/x", "date": "2026-10-01"}],
        "note": None, "on_player": True}
FILE = {"published_at": "2026-11-10", "status": "done", "stop_reason": None, "title": "An invented interview",
        "channel": "Invented Channel", "duration": 60.0, "speakers": {}, "flags": [FLAG]}
LANGS = {"enfile": {"lang": "en"}, "esfile": {"lang": "es"}, "oldfile": {}}


def test_summary_language(tmp_path):
    store = Store(tmp_path)
    for video, lang in LANGS.items():
        store.save(FILE | {"video_id": video} | lang)
        store.add_mark(video, FLAG, "correct", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    get = lambda path: urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_port}{path}", timeout=10).read().decode()
    html = lambda video: summary.page(summary.card(store.load(video) | {"flags": [FLAG | {"mark": "correct"}]},
                                                   FLAG["speaker"]), server.SUMMARY_TEMPLATE.read_text())
    # The image's words, without the markup, styles or line breaks.
    words = lambda video: " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>", "", html(video), flags=re.S)).split())
    try:
        # Case 1 · lang "en" → the card in English: the hook, the verdict of the flag and the footer
        for text in ("claims, false or misleading", "False.", "Detected with AI"):
            assert text in words("enfile"), f"FAIL S26 A4 · the English image lacks {text!r}"
        for text in ("datos, falsos", "Falso.", "Detectado con IA"):
            assert text not in words("enfile"), f"FAIL S26 A4 · the English image still says {text!r}"
        assert '<html lang="en">' in html("enfile"), "FAIL S26 A4 · the English image page is not lang en"

        # Case 2 · lang "en" → the share page and the alt text in English
        page, alt = get("/videos/enfile/summary"), get("/videos/enfile/summary.txt")
        assert "Alt text, ready to copy" in page and 'lang="en"' in page, "FAIL S26 A4 · the share page is not English"
        assert alt.startswith("Profile of Ann Lee in «An invented interview»"), f"FAIL S26 A4 · alt text {alt[:60]!r}"
        assert "0:10" in alt and "False." in alt, f"FAIL S26 A4 · alt text {alt!r}"

        # Case 3 · lang "es", or no lang (an older file) → the Spanish texts
        for video in ("esfile", "oldfile"):
            image, page, alt = words(video), get(f"/videos/{video}/summary"), get(f"/videos/{video}/summary.txt")
            assert "datos, falsos o engañosos" in image and "Detectado con IA" in image, \
                f"FAIL S26 A4 · {video}: the image is not Spanish"
            assert "Texto alternativo, listo para copiar" in page, f"FAIL S26 A4 · {video}: the share page is not Spanish"
            assert alt.startswith("Ficha de Ann Lee en «An invented interview»") and "Falso." in alt, \
                f"FAIL S26 A4 · {video}: alt text {alt[:80]!r}"
    finally:
        httpd.shutdown()
    print("PASS S26 A4 · The shareable card follows the interface language")
