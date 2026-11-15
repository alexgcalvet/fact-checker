"""S16 A3 · Every extracted figure is logged with what happened to it

Story: A part of an invented video yields three figures: one becomes a "Dato falso" flag, one checks out as right,
and one is cut by the budget. The claims log of the video has three lines with their second, speaker and outcome:
`flagged`, `ok` and `unchecked`.

Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
gives three figures in its only part (0-30 s). A fake Fact Check Tools API that finds nothing. A fake Claude whose
part tool call lists the three figures as claims, and whose fact-check tool call (the one with web tools) gives a
false verdict with a dated source and a tier-1 measure against for the first figure, a true verdict for the second,
and no verdict for the third, as when the check runs out of its budget. A second run gives the run a budget of one
Claude tool call (scheduler.CALLS_PER_HOUR = 1), so the budget refuses the fact-check tool call of the part. A
temporary helper home per run.
"""
import json

from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
TRUE = "la inflación cerró el año en el dos por ciento"
CUT = "hay tres millones de viviendas vacías"
LINES = [
    (0, GUEST, f"Mire {FALSE} y además {TRUE} y le digo más {CUT} en España"),
    (20, HOST, "Muchas gracias por venir y buenas noches"),
]
WORDS = LINES[0][2].split()
SECONDS = {q: next(i * 0.5 for i in range(len(WORDS)) if WORDS[i:i + len(q.split())] == q.split())
           for q in (FALSE, TRUE, CUT)}


class FakeTranscript:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class NoPublishedChecks:
    def search(self, query, language):
        return []


def verdict(quote, value, measures):
    return {"quote": quote, "verdict": value, "reason": "Razón inventada.", "confidence": 0.9,
            "sources": [{"publisher": "INE", "url": f"https://www.ine.es/{len(quote)}", "date": "2026-10-01"}],
            "note": None, "measures": measures, "controversy": None, "published": [], "earlier": None,
            "promise": None}


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            against = {"name": "Paro EPA", "value": "1", "source": "INE", "tier": 1, "supports": False}
            return {"verdicts": [verdict(FALSE, "false", [against]), verdict(TRUE, "true", [])]}
        part = prompt.split("PART:")[-1]
        return {"flags": [], "questions": [], "contradictions": [], "context": [],
                "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "fact"}
                           for q in (FALSE, TRUE, CUT) if q in part]}


def analyse(home):
    run_analysis("cifras", 0, transcript=FakeTranscript(), llm=FakeClaude(), factcheck=NoPublishedChecks(), home=home)
    data = json.loads((home / "videos" / "cifras.json").read_text())
    log = home / "claims.jsonl"
    rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return data, rows


def test_claims_log(tmp_path, monkeypatch):
    data, rows = analyse(tmp_path / "checked")

    # Case 1 · a part yields three figures: one false, one right and one without a verdict → three lines in the
    # claims log, each with the video, the second of the figure, its speaker and its outcome
    assert sorted((r["t"], r["outcome"]) for r in rows) == [
        (SECONDS[FALSE], "flagged"), (SECONDS[TRUE], "ok"), (SECONDS[CUT], "unchecked")], rows
    for r in rows:
        assert r["video_id"] == "cifras" and r["speaker"] == "Invitado", r

    # Case 2 · the flagged figure → a "Dato falso" flag in the flag file at the same second
    assert [(f["t"], f["label"]) for f in data["flags"] if f["type"] == "inaccuracy"] == [(SECONDS[FALSE], "false")]

    # Case 3 · the claims log holds no transcript → no quote and no words of a figure in any line
    for r in rows:
        assert set(r) == {"video_id", "t", "speaker", "outcome"}, r
        for quote in (FALSE, TRUE, CUT):
            assert quote not in json.dumps(r, ensure_ascii=False), r

    # Case 4 · the budget refuses the fact-check tool call of the part → its three figures are logged `unchecked`
    monkeypatch.setattr(scheduler, "CALLS_PER_HOUR", 1)
    data, rows = analyse(tmp_path / "budget")
    assert data["stop_reason"] == "budget", data["stop_reason"]
    assert sorted((r["t"], r["outcome"]) for r in rows) == [
        (SECONDS[FALSE], "unchecked"), (SECONDS[TRUE], "unchecked"), (SECONDS[CUT], "unchecked")], rows
    print("PASS S16 A3 · Every extracted figure is logged with what happened to it")
