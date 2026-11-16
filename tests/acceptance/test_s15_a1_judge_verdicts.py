"""S15 A1 · The judge rules on every flag once the analysis ends

Story: The helper analyses an invented 10-minute interview with a fallacy, a false figure, a disputed figure and
a context card. Before the flag file says done, one more Claude reading gets the whole transcript with speakers
and minutes and the three non-context flags. In the done file, the fallacy keeps its verdict, the false figure
says "puntualización: 49,8 M frente a 49,4 M, el fondo se sostiene", the disputed figure is kept (S32), and the
fallacy passes from "Luis" to "Ana Ruiz"; each original label, speaker and reason is still there.
Edge case: WHEN the judge's Claude reading fails THEN the file still ends done, with the flags as found and no
verdicts.

Setup: invented word-by-word captions (one word every 0.5 s) of a 10-minute interview, each line in the voice of
SPEAKER_00 ("Luis") or SPEAKER_01 ("Ana Ruiz"); the fallacy sits in a line that the voices give to Luis. A fake
Fact Check Tools API that finds nothing. A fake Claude that answers each part call with the flag, claim and
context of that part, each fact-check call with a false verdict (one tier-1 measure against) and a disputed one
(one measure for, one against), and the judge call (the call whose schema has `rulings`) with: keep the fallacy
and give it to "Ana Ruiz", "nitpick" the false figure, answer "drop" for the disputed one. The judge call records its prompt,
its tools and the file status at that moment. A second fake judge raises an error; a third run has a sparse
2.5-hour interview. A temporary helper home.
"""
import json
import re

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALLACY = "ustedes no tienen ninguna autoridad moral para hablar de nada"
FALSE = "España recibió cuarenta y nueve coma ocho millones de turistas"
DISPUTED = "el paro juvenil es el más alto de toda Europa"
NAME = "Marta Gil"
NITPICK = "49,8 M frente a 49,4 M, el fondo se sostiene"
LINES = [
    (0, HOST, "Buenas noches hoy entrevistamos al líder de la oposición"),
    (60, GUEST, f"Gracias Luis el ministro {NAME} no ha resuelto nada"),
    (180, HOST, FALLACY),
    (300, GUEST, FALSE),
    (420, GUEST, DISPUTED),
    (590, HOST, "Muchas gracias por venir y buenas noches"),
]


# The same interview over 2.5 hours: the false and the disputed figures after the second hour.
LONG = LINES[:3] + [(7500, GUEST, FALSE), (8000, GUEST, DISPUTED), (9000, HOST, LINES[-1][2])]


def ids(lines):
    start = {text: t for t, _, text in lines}
    return {"fallacy": f"ad_hominem-{start[FALLACY]:.1f}", "false": f"false-{start[FALSE]:.1f}",
            "disputed": f"disputed-{start[DISPUTED]:.1f}"}


IDS = ids(LINES)


class FakeTranscript:
    def __init__(self, lines=LINES):
        self.lines = lines

    def fetch(self, video_id):
        segments = [Segment(t=t + i * 0.5, text=w, speaker=voice)
                    for t, voice, text in self.lines for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Luis", GUEST: "Ana Ruiz"})


class NoPublishedChecks:
    def search(self, query, language):
        return []


def measure(supports, tier=1):
    return {"name": "medida inventada", "value": "1", "source": "INE", "tier": tier, "supports": supports}


def verdict(quote, measures):
    return {"quote": quote, "verdict": "false", "reason": "Las fuentes dan otra cifra.", "confidence": 0.9,
            "sources": [{"publisher": "INE", "url": f"https://www.ine.es/{len(quote)}", "date": "2026-10-01"}],
            "note": None, "published": [], "measures": measures, "controversy": None}


class FakeClaude:
    def __init__(self, home, video_id, ids, judge_fails=False):
        self.home, self.video_id, self.ids, self.judge_fails = home, video_id, ids, judge_fails
        self.judge_calls = []

    def complete(self, prompt, schema, tools=()):
        if "rulings" in schema["properties"]:
            status = json.loads((self.home / "videos" / f"{self.video_id}.json").read_text())["status"]
            self.judge_calls.append({"prompt": prompt, "tools": tools, "status": status})
            if self.judge_fails:
                raise RuntimeError("claude -p error: overloaded")
            return {"rulings": [
                {"id": self.ids["fallacy"], "verdict": "keep", "reason": "El ataque es suyo y no argumenta.",
                 "speaker": "Ana Ruiz"},
                {"id": self.ids["false"], "verdict": "nitpick", "reason": NITPICK, "speaker": None},
                {"id": self.ids["disputed"], "verdict": "drop", "reason": "Una medida creíble lo respalda.",
                 "speaker": None},
            ]}
        if "verdicts" in schema["properties"]:
            return {"verdicts": [verdict(FALSE, [measure(False)]),
                                 verdict(DISPUTED, [measure(False), measure(True, tier=2)])]}
        part = prompt.split("PART:")[-1]
        return {
            "flags": [{"quote": FALLACY, "label": "ad_hominem", "closest": "ad_hominem", "speaker": "Luis",
                       "reason": "Ataca a la persona.", "confidence": 0.9}] if FALLACY in part else [],
            "claims": [{"quote": q, "speaker": "Ana Ruiz", "queries": [q], "question": None, "kind": "fact"}
                       for q in (FALSE, DISPUTED) if q in part],
            "questions": [], "contradictions": [],
            "context": [{"name": NAME, "kind": "person", "speaker": "Ana Ruiz",
                         "sentence": "Ministro de Transportes.", "confidence": 0.95}] if NAME in part else [],
        }


def analyse(home, judge_fails=False, lines=LINES):
    claude = FakeClaude(home, "entrevista", ids(lines), judge_fails)
    run_analysis("entrevista", 0, transcript=FakeTranscript(lines), llm=claude, judge=claude,
                 factcheck=NoPublishedChecks(), home=home)
    return json.loads((home / "videos" / "entrevista.json").read_text()), claude.judge_calls


def test_judge_verdicts(tmp_path):
    data, calls = analyse(tmp_path)
    flags = {f["id"]: f for f in data["flags"]}
    assert set(IDS.values()) <= set(flags), list(flags)

    # Case 1 · the analysis of every part ends → one Claude reading, without web tools, before the file says done
    assert len(calls) == 1, calls
    assert calls[0]["tools"] == ()
    assert calls[0]["status"] == "running"
    assert data["status"] == "done"

    # Case 2 · the judge's reading → the whole transcript with speakers and minutes, and the three non-context flags
    prompt = calls[0]["prompt"]
    for _, _, text in LINES:
        assert text in prompt, text
    # The judge reads blind (2026-11-16): each speaker as a label with no name, such as "Speaker 2".
    assert re.search(rf"5:00\W+Speaker \d+\W+{FALSE}", prompt), "no speaker and minute on the 5:00 line"
    assert "Ana Ruiz" not in prompt.split("CONVERSATION")[-1], "the judge reads the guest's name"
    assert re.search(rf"9:50\W+Speaker \d+\W+Muchas gracias", prompt), "no speaker and minute on the 9:50 line"
    for id in IDS.values():
        assert id in prompt, id
    context = [f for f in data["flags"] if f["type"] == "context"]
    assert context and context[0]["id"] not in prompt

    # Case 3 · the fallacy → keeps its verdict and passes from Luis to Ana Ruiz, the original speaker kept
    fallacy = flags[IDS["fallacy"]]
    assert fallacy["judge"]["verdict"] == "keep"
    assert fallacy["judge"]["speaker"] == "Ana Ruiz"
    assert (fallacy["speaker"], fallacy["label"], fallacy["reason"]) == ("Luis", "ad_hominem", "Ataca a la persona.")

    # Case 4 · the false figure → "puntualización" with the judge's reason; still labelled false
    false = flags[IDS["false"]]
    assert false["judge"]["verdict"] == "nitpick"
    assert false["judge"]["reason"] == NITPICK
    assert (false["label"], false["speaker"], false["reason"]) == ("false", "Ana Ruiz", "Las fuentes dan otra cifra.")

    # Case 5 · the judge answers "drop" for the disputed figure → kept (S32: the judge drops no flag)
    disputed = flags[IDS["disputed"]]
    assert disputed["judge"]["verdict"] == "keep"
    assert disputed["label"] == "disputed"

    # Case 6 · the context card → no verdict
    assert "judge" not in context[0]
    print("PASS S15 A1 · The judge rules on every flag once the analysis ends")


def test_judge_fails(tmp_path):
    data, calls = analyse(tmp_path, judge_fails=True)

    # Case 7 · the judge's Claude reading fails → the file still ends done, with the flags as found and no verdicts
    assert len(calls) == 1
    assert data["status"] == "done", data["stop_reason"]
    assert set(IDS.values()) <= {f["id"] for f in data["flags"]}
    assert not [f for f in data["flags"] if "judge" in f]
    print("PASS S15 A1 · a failed judge leaves the file done with the flags as found")


def test_one_reading_per_two_hours(tmp_path):
    data, calls = analyse(tmp_path, lines=LONG)

    # Case 8 · a 2.5-hour interview → one judge reading per started two hours, each flag judged in one of them
    assert len(calls) == 2, len(calls)
    judged = [f for f in data["flags"] if "judge" in f]
    assert {f["id"] for f in judged} == set(ids(LONG).values()), judged
    for f in judged:
        assert sum(f["id"] in c["prompt"] for c in calls) == 1, f["id"]
    print("PASS S15 A1 · one judge reading per started two video-hours")
