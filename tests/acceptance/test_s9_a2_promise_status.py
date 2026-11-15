"""S9 A2 · A promise shows when it was made, its figure, its deadline and its status

Story: In an invented interview, the guest says "hemos cumplido lo que prometimos en vivienda". The check
finds the promise of 184,000 homes made in April 2023 for 2026, and that far fewer are delivered. The flag
file has a contradiction flag with the label "promise" that holds the date of the promise, the figure, the
deadline, the status "not met" and a dated source.
Edge cases: a promise that the check finds met or still in progress makes no flag; a promise that is
partly met makes a flag; a promise whose only source has no date makes no flag.

Setup: invented word-by-word captions with five claims of the guest about promises: homes (0 s), teachers
(10 s), trains (20 s), hospitals (30 s) and roads (40 s); a fake Fact Check Tools API that finds nothing; a
fake Claude whose part call lists the five claims as "promise", and whose check call judges them: homes
"false", status "not met", dated source; teachers "true", status "met", dated source; trains "false",
status "not met", undated source; hospitals "misleading", status "partly met", dated source; roads
"misleading", status "in progress", dated source; a temporary helper home.
"""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOMES = "hemos cumplido lo que prometimos en vivienda"
TEACHERS = "contratamos a los profesores que prometimos"
TRAINS = "terminamos la línea de tren que prometimos"
HOSPITALS = "abrimos todos los hospitales que prometimos"
ROADS = "las carreteras que prometimos ya están hechas"
HOMES_PROMISE = {"made": "2023-04", "figure": "184.000 viviendas", "deadline": "2026", "status": "not met"}
SOURCE = {"publisher": "El País", "url": "https://example.org/el-pais/viviendas-2025", "date": "2025-09-15"}


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=words(0, HOMES) + words(10, TEACHERS) + words(20, TRAINS)
                          + words(30, HOSPITALS) + words(40, ROADS), published_at="2026-11-10")


class NoPublishedChecks:
    def search(self, query, language):
        return []


def verdict(quote, answer, promise, source):
    return {"quote": quote, "verdict": answer, "reason": "Se entregaron muchas menos viviendas de las prometidas.",
            "confidence": 0.9, "sources": [source], "note": None, "measures": [], "controversy": None,
            "published": [], "earlier": None, "promise": promise}


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                verdict(HOMES, "false", HOMES_PROMISE, SOURCE),
                verdict(TEACHERS, "true",
                        {"made": "2022-01", "figure": "5.000 profesores", "deadline": "2024", "status": "met"},
                        SOURCE | {"url": "https://example.org/profesores"}),
                verdict(TRAINS, "false",
                        {"made": "2021-03", "figure": "una línea", "deadline": "2025", "status": "not met"},
                        {"publisher": "Un blog", "url": "https://example.org/blog", "date": None}),
                verdict(HOSPITALS, "misleading",
                        {"made": "2022-05", "figure": "10 hospitales", "deadline": "2025", "status": "partly met"},
                        SOURCE | {"url": "https://example.org/hospitales"}),
                verdict(ROADS, "misleading",
                        {"made": "2024-02", "figure": "300 km", "deadline": "2027", "status": "in progress"},
                        SOURCE | {"url": "https://example.org/carreteras"}),
            ]}
        return {"flags": [], "questions": [], "contradictions": [],
                "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "promise"}
                           for q in (HOMES, TEACHERS, TRAINS, HOSPITALS, ROADS)]}


def test_promise_status(tmp_path):
    run_analysis("promise", 0, transcript=FakeTranscript(), llm=FakeClaude(), factcheck=NoPublishedChecks(),
                 home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "promise.json").read_text())["flags"]
    by_quote = {f["quote"]: f for f in flags}

    # Case 1 · the guest says the homes promise was kept, the check finds it not met → a contradiction flag
    # "promise" with the date it was made, the figure, the deadline, the status and a dated source
    flag = by_quote.get(HOMES)
    assert flag, flags
    assert flag["type"] == "contradiction"
    assert flag["label"] == "promise"
    assert flag["speaker"] == "Invitado"
    assert flag["promise"] == HOMES_PROMISE
    assert flag["sources"] == [SOURCE]

    # Case 2 · the teachers promise is met → no flag
    assert TEACHERS not in by_quote, by_quote[TEACHERS]

    # Case 3 · the trains promise is not met, but its only source has no date → no flag
    assert TRAINS not in by_quote, by_quote[TRAINS]

    # Case 4 · the hospitals promise is partly met → a promise flag with the status "partly met"
    assert by_quote.get(HOSPITALS, {}).get("label") == "promise", flags
    assert by_quote[HOSPITALS]["promise"]["status"] == "partly met"

    # Case 5 · the roads promise is still in progress → no promise flag
    assert by_quote.get(ROADS, {}).get("label") != "promise", by_quote[ROADS]
    print("PASS S9 A2 · A promise shows when it was made, its figure, its deadline and its status")
