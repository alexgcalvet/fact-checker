"""S16 A2 · A part sees what each speaker stated earlier in the whole video

Story: In an invented 30-minute interview the guest says at 3:00 "no vamos a quitar el Ministerio de Igualdad", and
at 25:00 "no habrá Ministerio de Igualdad". The part at 25:00 receives a list with "Invitado (3:00): no quitará el
Ministerio de Igualdad", and the contradiction flag at 25:00 quotes the words at 3:00 with their second.
Edge case: WHEN the part that holds 3:00 is not done yet (parts run from the playback second) THEN the list holds
only what finished parts before 25:00 stated.

Setup: invented word-by-word captions (one word every 0.5 s) of a 30-minute interview, each line in the voice of
SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado"). The guest states a position at 3:00 and another at 24:10,
and says the opposite of the 3:00 one at 25:00, far outside the 10 minutes of CONTEXT. A fake Claude that, in each
part tool call, lists the positions whose words are in that PART (quote, speaker and a one-line summary), and lists
the 25:00 contradiction with the 3:00 words as `earlier` only when its prompt holds the 3:00 line. The parts run one
at a time (scheduler.PARALLEL = 1), so which parts are finished before a part starts is fixed. A second run starts
at 24:00, so the part with 3:00 runs after the part with 25:00. A third run has an invented 140-minute talk where
every part states one position. A temporary helper home per run.
"""
import json
import re

from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FIRST = "no vamos a quitar el Ministerio de Igualdad"
OTHER = "vamos a bajar el IVA de la luz"
SECOND = "no habrá Ministerio de Igualdad en mi gobierno"
POSITIONS = {FIRST: "no quitará el Ministerio de Igualdad", OTHER: "bajará el IVA de la luz"}
LINE = "Invitado (3:00): no quitará el Ministerio de Igualdad"
OTHER_LINE = "Invitado (24:10): bajará el IVA de la luz"
LINES = [
    (0, HOST, "Buenas noches hoy hablamos de igualdad con nuestro invitado"),
    (180, GUEST, f"{FIRST} en ningún caso"),
    (1450, GUEST, f"{OTHER} y le digo más"),
    (1490, HOST, "¿Y qué pasará con ese ministerio si gobiernan?"),
    (1500, GUEST, f"{SECOND} se lo aseguro"),
    (1790, HOST, "Muchas gracias por venir y buenas noches"),
]


class FakeTranscript:
    def __init__(self, lines):
        self.lines = lines

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in self.lines for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class FakeClaude:
    def __init__(self, positions):
        self.positions = positions
        self.calls = []  # (part text, text before the PART)

    def complete(self, prompt, schema, tools=()):
        head, _, part = prompt.rpartition("PART:")
        self.calls.append((part, head))
        contradictions = []
        if SECOND in part and LINE in head:
            contradictions.append({"quote": SECOND, "earlier": FIRST, "speaker": "Invitado",
                                   "earlier_speaker": "Invitado", "confidence": 0.9,
                                   "reason": "A las 3:00 dijo que no quitaría el ministerio y ahora que no habrá."})
        return {"flags": [], "claims": [], "questions": [], "context": [], "contradictions": contradictions,
                "positions": [{"quote": q, "speaker": "Invitado", "summary": s}
                              for q, s in self.positions.items() if q in part]}

    def head_of(self, words):
        return next(head for part, head in self.calls if words in part)


def analyse(home, from_t, lines=LINES, positions=POSITIONS):
    claude = FakeClaude(positions)
    run_analysis("igualdad", from_t, transcript=FakeTranscript(lines), llm=claude, home=home)
    data = json.loads((home / "videos" / "igualdad.json").read_text())
    return [f for f in data["flags"] if f["type"] == "contradiction"], claude


def test_positions_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    found, claude = analyse(tmp_path / "from-start", 0)

    # Case 1 · the part at 25:00, after the part with 3:00 is done → its prompt lists the guest's 3:00 position with
    # its minute, and the 24:10 one
    head = claude.head_of(SECOND)
    assert LINE in head, head
    assert OTHER_LINE in head, head

    # Case 2 · the guest says the opposite at 25:00 → a contradiction flag at 25:00 that quotes the 3:00 words with
    # their second, though they are far outside the 10 minutes of CONTEXT
    assert len(found) == 1, found
    assert found[0]["t"] == 1500.0
    assert found[0]["speaker"] == "Invitado"
    assert found[0]["related"] == {"t": 180.0, "quote": FIRST}

    # Case 3 · the positions come out of the part tool calls → one Claude tool call per part, no extra one
    assert len(claude.calls) == len(scheduler.plan(FakeTranscript(LINES).fetch("igualdad"), 0))

    # Case 4 · the playback starts at 24:00, so the part with 3:00 is not done when the part at 25:00 starts → its
    # list holds the 24:10 position of a finished part, not the 3:00 one, and no contradiction is flagged
    found, claude = analyse(tmp_path / "from-24", 1440)
    head = claude.head_of(SECOND)
    assert OTHER_LINE in head, head
    assert LINE not in head, head
    assert found == [], found

    # Case 5 · the part with 3:00 runs last → it never lists a position stated later in the video
    assert OTHER_LINE not in claude.head_of(FIRST)

    # Case 6 · a 140-minute talk with one position per part → the last part gets at most 60 lines, the newest
    # position on a line of its own and the oldest one merged, not lost
    talk = [(60 + 120 * k, GUEST, f"posición número {k} del invitado") for k in range(70)]
    summaries = {text: f"defiende la posición {k}" for k, (_, _, text) in enumerate(talk)}
    _, claude = analyse(tmp_path / "long", 0, lines=talk, positions=summaries)
    head = claude.head_of(talk[-1][2])
    listed = [line for line in head.splitlines() if re.match(r"Invitado \(\d+:\d\d", line)]
    assert 1 <= len(listed) <= 60, len(listed)
    assert listed[-1].startswith("Invitado (2:17:00): defiende la posición 68"), listed[-1]
    assert re.search(r"defiende la posición 0\b", listed[0]), listed[0]
    for k in range(69):
        assert re.search(rf"defiende la posición {k}\b", head), k
    print("PASS S16 A2 · A part sees what each speaker stated earlier in the whole video")
