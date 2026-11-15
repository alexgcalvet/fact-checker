"""S8 A1 · A speaker who contradicts themself gets a flag at the second statement

Story: In an invented interview, the guest says "no vamos a subir el IVA" and, four minutes later,
"subiremos el IVA de la luz el año que viene". When the helper analyses it, the flag file has a
contradiction flag at the second of the second statement, quoting it, with the first statement and its
second as the earlier utterance.
Edge case: when the audio puts the two statements in different voices, no contradiction flag is made.

Setup: invented word-by-word captions (one word every 0.5 s) over four parts (0-30, 30-150, 150-270 and
270-390 s), each word in the voice of its line: SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado").
The guest says the IVA pair at 6 s and 250 s; the host proposes freezing pensions at 40 s and the guest
rejects it at 280 s. A fake Claude that, in each part call, lists the contradictions whose second
statement is in that PART, both pinned on "Invitado" by both names; it lists no fallacy, claim or
question. A second run uses the same captions without voices. The real bars of thresholds.json; a
temporary helper home.
"""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FIRST = "no vamos a subir el IVA"
SECOND = "subiremos el IVA de la luz el año que viene"
PROPOSAL = "congelar las pensiones el año que viene"
REJECTION = "no vamos a congelar las pensiones"
LINES = [
    (0, HOST, "Buenas noches hoy hablamos de impuestos con nuestro invitado"),
    (6, GUEST, f"Gracias por invitarme lo digo claro {FIRST} en esta legislatura"),
    (40, HOST, f"Hay quien propone {PROPOSAL} para cuadrar las cuentas"),
    (250, GUEST, f"Y le adelanto una cosa {SECOND} para pagar la transición"),
    (280, GUEST, f"Mire nosotros {REJECTION} pase lo que pase"),
]
FIRST_T = 6 + 6 * 0.5
SECOND_T = 250 + 5 * 0.5


class FakeTranscript:
    def __init__(self, with_voices):
        self.with_voices = with_voices

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice if self.with_voices else None)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        names = {HOST: "Presentadora", GUEST: "Invitado"} if self.with_voices else {}
        return Transcript(segments=segments, published_at="2026-11-10", speakers=names)


def contradiction(quote, earlier):
    return {"quote": quote, "earlier": earlier, "speaker": "Invitado", "earlier_speaker": "Invitado",
            "reason": f"Antes dijo «{earlier}» y ahora «{quote}».", "confidence": 0.9}


CONTRADICTIONS = [contradiction(SECOND, FIRST), contradiction(REJECTION, PROPOSAL)]


class FakeClaude:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, schema, tools=()):
        self.calls += 1
        part = prompt.split("PART:")[-1]
        return {"flags": [], "claims": [], "questions": [],
                "contradictions": [c for c in CONTRADICTIONS if c["quote"] in part]}


def analyse(tmp_path, with_voices):
    claude = FakeClaude()
    run_analysis("taxes", 0, transcript=FakeTranscript(with_voices), llm=claude, home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "taxes.json").read_text())["flags"]
    return [f for f in flags if f["type"] == "contradiction"], claude.calls


def test_self_contradiction(tmp_path):
    found, calls = analyse(tmp_path / "voices", with_voices=True)
    by_quote = {f["quote"]: f for f in found}

    # Case 1 · the guest says the opposite four minutes later, in the same voice → a contradiction flag at
    # the second of the second statement, with the first statement as the earlier utterance
    flag = by_quote.get(SECOND)
    assert flag, found
    assert flag["label"] == "self"
    assert flag["t"] == SECOND_T
    assert flag["speaker"] == "Invitado"
    assert flag["related"] == {"t": FIRST_T, "quote": FIRST}
    assert flag["reason"] == CONTRADICTIONS[0]["reason"]

    # Case 2 · the model pins the host's proposal on the guest, but the audio puts it in the host's voice
    # → no contradiction flag
    assert REJECTION not in by_quote
    assert len(found) == 1, found

    # Case 3 · the contradictions come from the part tool calls → one Claude tool call per part, no extra one
    assert calls == 4

    # Case 4 · a video without voices, and the model names the same speaker for both statements → both
    # pairs flagged, since only the model's names tell the speakers apart
    found, _ = analyse(tmp_path / "no-voices", with_voices=False)
    by_quote = {f["quote"]: f for f in found}
    assert by_quote.get(SECOND, {}).get("related") == {"t": FIRST_T, "quote": FIRST}, found
    assert by_quote.get(REJECTION, {}).get("related", {}).get("quote") == PROPOSAL, found
    print("PASS S8 A1 · A speaker who contradicts themself gets a flag at the second statement")
