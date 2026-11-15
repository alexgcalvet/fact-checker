"""S7 A1 · A dodged question is flagged at the end of its answer

Story: In an invented interview, the host asks "¿cuántas viviendas se han entregado?" and the guest talks
about the housing law. When the helper analyses it, the flag file has a "question" flag with status
"dodged" at the second the answer ends; it holds the host's question and a reason.
Edge case: when the guest answers with another figure, "184.000 viviendas entregadas o en proceso", the
question is still "dodged".

Setup: invented word-by-word captions (one word every 0.5 s) of four questions and their answers over two
parts (0-30 s and 30-150 s); the third question sits in the first part and its answer ends in the second.
A fake Claude that, in each part call, lists the questions whose answer ends in that PART: the first three
dodged (the second because it gives another figure), the fourth answered; it lists no fallacy and no
claim. The real bars of thresholds.json (no bar for questions); a temporary helper home.
"""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

Q1 = "¿Cuántas viviendas se han entregado?"
A1 = "Mire lo importante es que hemos aprobado la primera ley de vivienda de la democracia"
Q2 = "¿Y cuántas se han terminado este año?"
A2 = "Tenemos 184.000 viviendas entregadas o en proceso"
Q3 = "¿Cuándo bajarán los alquileres?"
A3 = "Lo que le digo es que la oposición votó en contra de todas nuestras medidas"
Q4 = "¿Mantendrá el bono joven?"
A4 = "Sí lo mantendremos el año que viene con el mismo importe"
LINES = [(0, Q1), (3, A1), (14, Q2), (18, A2), (25, Q3), (31, A3), (40, Q4), (43, A4)]


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


def end(start, text):
    return start + (len(text.split()) - 1) * 0.5


def tail(text, n=5):
    return " ".join(text.split()[-n:])


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=[s for start, text in LINES for s in words(start, text)], published_at="2026-11-10")


def question(q, a, status, confidence):
    return {"question": q, "answer_end": tail(a), "speaker": "Invitado", "status": status,
            "reason": f"Se preguntó «{q}» y la respuesta no lo dice.", "confidence": confidence}


QUESTIONS = [question(Q1, A1, "dodged", 0.9), question(Q2, A2, "dodged", 0.7), question(Q3, A3, "dodged", 0.85),
             question(Q4, A4, "answered", 0.9)]


class FakeClaude:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, schema, tools=()):
        self.calls += 1
        part = prompt.split("PART:")[-1]
        return {"flags": [], "claims": [], "questions": [q for q in QUESTIONS if q["answer_end"] in part]}


def test_dodged_question(tmp_path):
    claude = FakeClaude()
    run_analysis("questions", 0, transcript=FakeTranscript(), llm=claude, home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "questions.json").read_text())["flags"]
    questions = [f for f in flags if f["type"] == "question"]
    by_question = {f["related"]["quote"]: f for f in questions}

    # Case 1 · the guest talks about the housing law → a dodged question flag at the end of the answer,
    # with the host's question and a reason
    first = by_question.get(Q1)
    assert first, flags
    assert first["answer"] == "dodged"
    assert first["t"] == end(3, A1)
    assert first["reason"] == QUESTIONS[0]["reason"]
    assert first["speaker"] == "Invitado"

    # Case 2 · the guest answers with another figure ("entregadas o en proceso") → still dodged
    second = by_question.get(Q2)
    assert second and second["answer"] == "dodged", flags
    assert second["t"] == end(18, A2)

    # Case 3 · the question sits in the first part, its answer ends in the second → flagged at the end of
    # the answer, with the question from the context
    third = by_question.get(Q3)
    assert third and third["answer"] == "dodged", flags
    assert third["t"] == end(31, A3)

    # Case 4 · an answered question → no flag
    assert Q4 not in by_question
    assert len(questions) == 3, questions

    # Case 5 · no bar for questions → on the player from 0.8 confidence
    assert first["on_player"] is True
    assert second["on_player"] is False

    # Case 6 · the questions come from the part tool calls → one Claude tool call per part, no extra one
    assert claude.calls == 2
    print("PASS S7 A1 · A dodged question is flagged at the end of its answer")
