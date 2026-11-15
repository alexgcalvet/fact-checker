"""S5 A3 · A published fact-check about another event does not count

Story: A guest says 80,000 people crossed into Ceuta in two days. A published fact-check about a different
crossing says "hundreds" and is rated false. The check step says it is another event, so it gives no
source and no date, and no card is made from it.

Setup: invented captions with two claims, the Ceuta crossing and youth unemployment; a fake Fact Check
Tools API that returns a Maldita check about another Ceuta crossing (rated "Falso", 2021-05-20) and a
Newtral check about the same youth unemployment claim (rated "Falso", 2025-05-12); a fake Claude that
lists both claims, judges both false citing the published check with no date, and says the Maldita check
is about another event and the Newtral check about the same one; a temporary helper home.
"""
import json

from fact_checker.core.flags import PublishedCheck, Segment, Transcript
from fact_checker.server import run_analysis

CEUTA = "más de ochenta mil personas entraron en Ceuta en dos días"
YOUTH = "el paro juvenil se duplicó el año pasado"
MALDITA_URL = "https://maldita.es/bulo-ceuta-cientos/"
NEWTRAL_URL = "https://www.newtral.es/paro-juvenil-duplicado/"


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=words(0, CEUTA) + words(10, YOUTH), published_at="2026-11-10")


class FakeGoogle:
    def search(self, query, language):
        if "Ceuta" in query:
            return [PublishedCheck(claim="Cientos de personas cruzaron a nado la frontera de Ceuta", claimant="Redes",
                                   publisher="Maldita", site="maldita.es", url=MALDITA_URL, rating="Falso",
                                   review_date="2021-05-20")]
        return [PublishedCheck(claim="El paro juvenil se ha duplicado en un año", claimant="Varios",
                               publisher="Newtral", site="newtral.es", url=NEWTRAL_URL, rating="Falso",
                               review_date="2025-05-12")]


def verdict(quote, publisher, url, same_event):
    return {"quote": quote, "verdict": "false", "reason": "Un verificador lo desmintió.", "confidence": 0.9,
            "sources": [{"publisher": publisher, "url": url, "date": None}], "note": None,
            "published": [{"url": url, "same_event": same_event}]}


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [verdict(CEUTA, "Maldita", MALDITA_URL, False),
                                 verdict(YOUTH, "Newtral", NEWTRAL_URL, True)]}
        return {"flags": [], "claims": [{"quote": CEUTA, "speaker": "Invitado", "queries": ["Ceuta entrada"]},
                                        {"quote": YOUTH, "speaker": "Invitado", "queries": ["paro juvenil"]}]}


def test_other_event_ignored(tmp_path):
    run_analysis("events", 0, transcript=FakeTranscript(), llm=FakeClaude(), factcheck=FakeGoogle(), home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "events.json").read_text())["flags"]

    # Case 1 · the only source is a check about another event → no source, no date, no card
    assert not [f for f in flags if "Ceuta" in f["quote"]], flags

    # Case 2 · a check about the same event → the card cites it with its own date
    youth = [f for f in flags if f["quote"] == YOUTH]
    assert len(youth) == 1, flags
    assert youth[0]["sources"] == [{"publisher": "Newtral", "url": NEWTRAL_URL, "date": "2025-05-12"}]
    print("PASS S5 A3 · A published fact-check about another event does not count")
