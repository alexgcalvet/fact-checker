"""S33 A3 · A role the person sets holds, and the image follows

Story: The reading took a guest for the host. The person sets that speaker to guest from the side panel and exports the
summary again. The export now has a card for that speaker (S35). When the analysis later names the voices again, the
role the person set stays.

Setup: a temporary helper home with the flag file of the invented interview of s33_fakes, where the reading named both
voices host: "Presentador" and "Ana Ruiz (invitada)". Ana Ruiz has one false figure marked correct. The helper's own
HTTP server runs on a free local port. The later naming is a new analysis of the same video with the voice turns of
s33_fakes and a fake model that again names Ana Ruiz host.
"""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker import server
from fact_checker.server import run_analysis
from fact_checker.store import Store
from s33_fakes import GUEST, HOST, FakeModel, FakeTranscript, FakeVoices

ANA = "Ana Ruiz (invitada)"
QUOTE = "el paro bajó a la mitad en un solo año"
FLAG = {"id": "false-1300.0", "t": 1300.0, "speaker": ANA, "quote": QUOTE, "type": "inaccuracy", "label": "false",
        "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "sources": [], "note": None,
        "on_player": True}
FILE = {"video_id": "entrevista", "published_at": "2026-11-10", "status": "done", "stop_reason": None, "lang": "es",
        "title": "Entrevista inventada a Ana Ruiz", "channel": "Canal inventado", "duration": 3750.0,
        "speakers": {HOST: "Presentador", GUEST: ANA},
        "people": {"Presentador": {"role": "host", "person": "Presentador", "spoken_s": 1260, "set_by": "llm"},
                   ANA: {"role": "host", "person": "Ana Ruiz", "spoken_s": 2460, "set_by": "llm"}},
        "flags": [FLAG]}


def test_role_set_by_person(tmp_path):
    store = Store(tmp_path)
    store.save(FILE)
    store.add_mark("entrevista", FLAG, "correct", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}/videos/entrevista"

    def export():
        """The export page (S35): one card and its alt text per guest."""
        return urllib.request.urlopen(f"{base}/summary", timeout=10).read().decode()

    def post(body):
        req = urllib.request.Request(f"{base}/people", method="POST", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status
        except urllib.error.HTTPError as e:
            return e.code

    try:
        # Case 1 · Ana Ruiz taken for the host → the summary leaves her out
        assert QUOTE not in export(), "FAIL S33 A3 · the summary shows a speaker read as host"

        # Case 2 · the person sets Ana Ruiz to guest → 200, kept with set_by person, and the summary shows her
        assert post({"name": ANA, "role": "guest"}) == 200, "FAIL S33 A3 · POST /people did not answer 200"
        entry = store.load("entrevista")["people"][ANA]
        assert entry["role"] == "guest" and entry["set_by"] == "person", f"FAIL S33 A3 · entry {entry}"
        assert "Ana Ruiz" in export() and QUOTE in export(), f"FAIL S33 A3 · the summary does not follow: {export()!r}"

        # Case 3 · a name not in the speakers, or a role other than host or guest → 400, the file unchanged
        assert post({"name": "Nadie", "role": "guest"}) == 400, "FAIL S33 A3 · an unknown name did not answer 400"
        assert post({"name": ANA, "role": "moderadora"}) == 400, "FAIL S33 A3 · a bad role did not answer 400"
        people = store.load("entrevista")["people"]
        assert "Nadie" not in people and people[ANA]["role"] == "guest", f"FAIL S33 A3 · people changed: {people}"
    finally:
        httpd.shutdown()

    # Case 4 · a later naming reads Ana Ruiz as host again → the role the person set stays
    named = {HOST: ("Presentador", "host", "Presentador"), GUEST: (ANA, "host", "Ana Ruiz")}
    run_analysis("entrevista", 0, transcript=FakeTranscript(), llm=FakeModel(named), home=tmp_path,
                 voices=FakeVoices())
    people = store.load("entrevista")["people"]
    assert people[ANA]["role"] == "guest" and people[ANA]["set_by"] == "person", \
        f"FAIL S33 A3 · the later naming overwrote the person's role: {people[ANA]}"
    assert people[ANA]["spoken_s"] == 2460, f"FAIL S33 A3 · seconds of speech {people[ANA]}"
    assert people["Presentador"]["role"] == "host" and people["Presentador"]["set_by"] == "llm", \
        f"FAIL S33 A3 · host entry {people['Presentador']}"
    print("PASS S33 A3 · A role the person sets holds, and the image follows")
