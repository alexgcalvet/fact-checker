"""S10 A1 · A named person gets one context card, at the first mention

Story: In an invented interview, the guest names "Marta Gil" at minute 3 and again at minute 9, in
another part. When the helper analyses it, the flag file has one context flag for Marta Gil, at the
second of the first mention, with one sentence saying who he is.
Edge case: when the later part is analysed before the earlier one, the file still keeps one context flag,
at the first mention.

Setup: invented word-by-word captions (one word every 0.5 s) over four parts (0-30, 150-270, 270-390 and
510-630 s), each word in the voice of its line: SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado").
The guest names Marta Gil at 180 s and at 540 s. A fake Claude that, in each part call, lists the
context of each name in that PART, with the same sentence each time; it lists no fallacy, claim, question
or contradiction. A second run starts at second 500, so the part of minute 9 is planned first, and the fake
answers the part of minute 3 late. The real bars of thresholds.json; a temporary helper home.
"""
import json
import time

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
NAME = "Marta Gil"
SENTENCE = "Ministro de Transportes del Gobierno de España desde noviembre de 2023."
FIRST_LINE = f"Como dijo el ministro {NAME} los trenes van a llegar a su hora"
LINES = [
    (0, HOST, "Buenas noches hoy hablamos de trenes con nuestro invitado"),
    (180, GUEST, FIRST_LINE),
    (300, HOST, "Pero los retrasos siguen en todas las líneas del país"),
    (540, GUEST, f"Ya se lo expliqué a {NAME} la semana pasada en el ministerio"),
]
FIRST_T = 180 + 4 * 0.5


class FakeTranscript:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10",
                          speakers={HOST: "Presentadora", GUEST: "Invitado"})


class FakeClaude:
    def __init__(self, slow_first=False):
        self.calls = 0
        self.slow_first = slow_first

    def complete(self, prompt, schema, tools=()):
        self.calls += 1
        part = prompt.split("PART:")[-1]
        if self.slow_first and FIRST_LINE in part:
            time.sleep(0.5)
        context = [{"name": NAME, "kind": "person", "speaker": "Invitado", "sentence": SENTENCE,
                    "confidence": 0.95}] if NAME in part else []
        return {"flags": [], "claims": [], "questions": [], "contradictions": [], "context": context}


def analyse(home, from_t=0, slow_first=False):
    claude = FakeClaude(slow_first)
    run_analysis("trains", from_t, transcript=FakeTranscript(), llm=claude, home=home)
    flags = json.loads((home / "videos" / "trains.json").read_text())["flags"]
    return [f for f in flags if f["type"] == "context"], claude.calls


def test_first_mention(tmp_path):
    found, calls = analyse(tmp_path / "in-order")

    # Case 1 · the guest names Marta Gil at minute 3 → a context flag at the second of the first
    # mention, with the name as said and one sentence on who he is
    assert found, "no context flag"
    flag = found[0]
    assert flag["label"] == "person"
    assert flag["quote"] == NAME
    assert flag["t"] == FIRST_T
    assert flag["reason"] == SENTENCE

    # Case 2 · the guest names him again at minute 9, in another part → no second context flag
    assert len(found) == 1, found

    # Case 3 · the context comes from the part tool calls → one Claude tool call per part, no extra one
    assert calls == 4

    # Case 4 · the part of minute 9 is analysed before the part of minute 3 → still one context flag, at
    # the first mention
    found, _ = analyse(tmp_path / "out-of-order", from_t=500, slow_first=True)
    assert [f["t"] for f in found] == [FIRST_T], found
    print("PASS S10 A1 · A named person gets one context card, at the first mention")
