"""S17 A2 · Only central figures are checked, each once per video

Story: Parts of an invented video yield five figures: one said in passing, one that carries the guest's argument,
and the same central figure said again ten minutes later in other words, plus two more central ones. Three are
checked; the passing one is logged `skipped`, and the repeated one `repeated`, pointing to the first.

Setup: invented word-by-word captions (one word every 0.5 s) of a 12-minute interview. In the part 0:00-0:30 the
guest ("Invitado") gives a figure in passing and two central figures; in the part that holds minute 11 he says the
first central figure again in other words, and one more central figure. A fake Fact Check Tools API that finds
nothing. A fake Claude: its part tool call lists the figures of the PART, marks the passing one as not central, and
marks the repeated one as a repeat of the line of the already checked figures that holds the first central figure;
its fact-check tool call finds every figure it gets right. The parts run one at a time (scheduler.PARALLEL = 1), so
the part of minute 11 runs after the first part. A temporary helper home.
"""
import json
import re

from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
PASSING = "hace dos años había veinte mil autobuses"
FIRST = "el paro bajó a la mitad en un año"
SECOND_ONE = "la inflación cerró el año en el dos por ciento"
REPEAT = "el desempleo se redujo a la mitad en doce meses"
THIRD = "hay tres millones de viviendas vacías"
LINES = [
    (0, GUEST, f"Como {PASSING} le digo que {FIRST} y que {SECOND_ONE} en España"),
    (20, HOST, "Muchas gracias y sigamos con la vivienda"),
    (660, GUEST, f"Insisto en que {REPEAT} y además {THIRD} en este país"),
    (680, HOST, "Muchas gracias por venir y buenas noches"),
]
CENTRAL = (FIRST, SECOND_ONE, REPEAT, THIRD)


def second(quote):
    for start, _, text in LINES:
        words = text.split()
        for i in range(len(words)):
            if words[i:i + len(quote.split())] == quote.split():
                return start + i * 0.5


class FakeTranscript:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class NoPublishedChecks:
    def search(self, query, language):
        return []


class FakeClaude:
    def __init__(self):
        self.part_prompts = []
        self.check_prompts = []

    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            self.check_prompts.append(prompt)
            return {"verdicts": [
                {"quote": q, "verdict": "true", "reason": "Correcto.", "confidence": 0.9,
                 "sources": [{"publisher": "INE", "url": "https://www.ine.es/x", "date": "2026-10-01"}],
                 "note": None, "measures": [], "controversy": None, "published": [], "earlier": None, "promise": None}
                for q in (PASSING, *CENTRAL) if q in prompt]}
        self.part_prompts.append(prompt)
        head, _, part = prompt.rpartition("PART:")
        listed = next((line for line in head.splitlines() if FIRST in line and re.match(r"\s*\d+\.", line)), None)
        claims = []
        for q in (PASSING, *CENTRAL):
            if q in part:
                repeats = int(re.match(r"\s*(\d+)\.", listed)[1]) if q == REPEAT and listed else None
                claims.append({"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "fact",
                               "central": q != PASSING, "repeats": repeats})
        return {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [], "claims": claims}


def test_claim_triage(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    claude = FakeClaude()
    run_analysis("triaje", 0, transcript=FakeTranscript(), llm=claude, factcheck=NoPublishedChecks(), home=tmp_path)
    data = json.loads((tmp_path / "videos" / "triaje.json").read_text())
    rows = [json.loads(line) for line in (tmp_path / "claims.jsonl").read_text().splitlines()]
    assert data["status"] == "done", data

    # Case 1 · the part of minute 11 → its prompt lists the central figure already checked in the first part
    later = next(p for p in claude.part_prompts if REPEAT in p.rpartition("PART:")[2])
    assert any(FIRST in line and re.match(r"\s*\d+\.", line) for line in later.rpartition("PART:")[0].splitlines()), \
        "the first central figure is not listed as already checked"

    # Case 2 · five figures → only the three distinct central ones reach a fact-check tool call
    checked = "\n".join(claude.check_prompts)
    assert all(q in checked for q in (FIRST, SECOND_ONE, THIRD)), checked
    assert PASSING not in checked and REPEAT not in checked, checked

    # Case 3 · the claims log → the passing figure `skipped`, the repeated one `repeated` with the second of the first
    # one, the three checked ones `ok`
    outcomes = {r["t"]: r for r in rows}
    assert len(rows) == 5, rows
    assert outcomes[second(PASSING)]["outcome"] == "skipped", rows
    assert outcomes[second(REPEAT)]["outcome"] == "repeated", rows
    assert outcomes[second(REPEAT)]["repeats"] == second(FIRST), rows
    for q in (FIRST, SECOND_ONE, THIRD):
        assert outcomes[second(q)]["outcome"] == "ok", (q, rows)

    # Case 4 · the claims log still holds no transcript → no quote of a figure in any line
    for r in rows:
        assert r["video_id"] == "triaje" and r["speaker"] == "Invitado", r
        for q in (PASSING, *CENTRAL):
            assert q not in json.dumps(r, ensure_ascii=False), r
    print("PASS S17 A2 · Only central figures are checked, each once per video")
