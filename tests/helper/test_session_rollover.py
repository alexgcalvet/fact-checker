"""A conversation whose context passes 150k tokens goes on in a new session, which gets the positions list."""
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

FIRST = "no vamos a subir el IVA de la luz"
LINES = [(0, "Buenas noches y bienvenidos"), (60, FIRST), (200, "frase del programa"), (330, "otra frase más")]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=[Segment(t=float(t + i * 0.5), text=w) for t, text in LINES
                                    for i, w in enumerate(text.split())], published_at="2026-11-10")


class FakeClaude:
    """Grows the session as Claude Code does, by 100k tokens a reading."""

    def __init__(self):
        self.readings = []

    def complete(self, prompt, schema):
        session = prompt.session
        self.readings.append((session.id, session.turns, prompt.data))
        session.turns += 1
        session.tokens += 100_000
        part = prompt.data.rpartition("PART:")[2]
        return {"flags": [], "claims": [], "questions": [], "contradictions": [], "context": [],
                "positions": [{"quote": FIRST, "speaker": "Invitado", "summary": "no subirá el IVA"}] if FIRST in part else []}


def test_new_session_carries_positions(tmp_path):
    claude = FakeClaude()
    run_analysis("largo", 0, transcript=FakeTranscript(), llm=claude, home=tmp_path, context_mode="conversation")
    ids = [r[0] for r in claude.readings]
    assert ids[0] == ids[1] != ids[2] == ids[3], ids
    assert claude.readings[2][1] == 0
    assert "no subirá el IVA" in claude.readings[2][2]
    assert "no subirá el IVA" not in claude.readings[3][2]
