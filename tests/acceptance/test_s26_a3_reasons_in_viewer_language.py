"""S26 A3 · Reasons come in the viewer's language, quotes stay as said

Story: A person with a Spanish browser clicks "Analizar este vídeo" on that English interview: the extension sends its
language, and the part, fact-check and judge readings ask for reasons in Spanish about an English conversation; the
flag file says `lang` "es" and the quote stays English. An English viewer of a Spanish video gets readings that ask
for English reasons. With no language sent, the reasons follow the video's language.

Setup: s26_fakes, the same fake commands as A2, and the helper's own HTTP server on a free local port in a temporary
helper home. Each case posts `/videos/<id>?from=0` with or without `lang`, as the extension does, then reads the flag
file with GET until it is no longer running. What the extension sends is checked in
s26-a3-analyze-sends-language.test.ts.
"""
import json
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker import server

from s26_fakes import ATTACK, readings, setup, text


def analyse(home, video: str, query: str) -> dict:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}/videos/{video}"
    try:
        urllib.request.urlopen(urllib.request.Request(f"{url}?from=0{query}", method="POST"), timeout=10)
        for _ in range(300):
            try:
                data = json.loads(urllib.request.urlopen(url, timeout=10).read())
                if data["status"] != "running":
                    return data
            except urllib.error.HTTPError:
                pass
            time.sleep(0.1)
        raise AssertionError("FAIL S26 A3 · the analysis did not finish in 30 s")
    finally:
        httpd.shutdown()


def by_kind(log) -> dict:
    return {r["answer"]: text(r) for r in readings(log)}


def test_spanish_viewer_of_an_english_video(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    data = analyse(home, "enview", "&lang=es")
    seen = by_kind(log)

    # Case 1 · a Spanish viewer, an English video → reasons asked in Spanish about an English conversation
    assert data["status"] == "done", f"FAIL S26 A3 · {data['status']} ({data['stop_reason']})"
    assert (data.get("lang"), data.get("spoken")) == ("es", "en"), \
        f"FAIL S26 A3 · lang {data.get('lang')!r}, spoken {data.get('spoken')!r}"
    assert "English conversation" in seen["flags"] and "reason: one short sentence in Spanish" in seen["flags"], \
        "FAIL S26 A3 · the part reading does not ask for Spanish reasons about an English conversation"
    assert "reason: one short sentence in Spanish" in seen["verdicts"], \
        "FAIL S26 A3 · the verdict reading does not ask for a Spanish reason"
    assert "one short reason in Spanish" in seen["rulings"], "FAIL S26 A3 · the judge does not rule in Spanish"
    for kind in ("flags", "verdicts", "rulings"):
        assert "sentence in English" not in seen[kind] and "reason in English" not in seen[kind], \
            f"FAIL S26 A3 · the {kind} reading asks for English reasons"

    # Case 2 · the quote → the English words, as said
    attacks = [f["quote"] for f in data["flags"] if f["label"] == "ad_hominem"]
    assert attacks == [ATTACK["en"]], f"FAIL S26 A3 · quotes {attacks}"


def test_english_viewer_of_a_spanish_video(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    data = analyse(home, "esview", "&lang=en")
    seen = by_kind(log)

    # Case 3 · an English viewer, a Spanish video → reasons asked in English about a Spanish conversation
    assert (data.get("lang"), data.get("spoken")) == ("en", "es"), \
        f"FAIL S26 A3 · lang {data.get('lang')!r}, spoken {data.get('spoken')!r}"
    assert seen["flags"].startswith("You analyse Spanish conversations."), "FAIL S26 A3 · not a Spanish conversation"
    assert "reason: one short sentence in English" in seen["flags"], "FAIL S26 A3 · the part reading asks no English"
    assert "reason: one short sentence in English" in seen["verdicts"], "FAIL S26 A3 · the verdict asks no English"
    assert "one short reason in English" in seen["rulings"], "FAIL S26 A3 · the judge does not rule in English"
    attacks = [f["quote"] for f in data["flags"] if f["label"] == "ad_hominem"]
    assert attacks == [ATTACK["es"]], f"FAIL S26 A3 · quotes {attacks}"


def test_no_language_sent(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    data = analyse(home, "enview", "")

    # Case 4 · no language sent → the reasons follow the video's language
    assert (data.get("lang"), data.get("spoken")) == ("en", "en"), \
        f"FAIL S26 A3 · lang {data.get('lang')!r}, spoken {data.get('spoken')!r}"
    assert "reason: one short sentence in English" in by_kind(log)["flags"], "FAIL S26 A3 · not English reasons"
    print("PASS S26 A3 · Reasons come in the viewer's language, quotes stay as said")
