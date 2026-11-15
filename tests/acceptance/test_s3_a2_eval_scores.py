"""S3 A2 · The eval scores flags against the expected ones

Story: Two invented dialogues hold 4 expected fallacies. The model returns 3 fallacies: 2 on the expected
words with the expected name, 1 elsewhere. The eval reports fallacy precision 67% and recall 50%. A flag
with the expected name that quotes only part of the expected words counts as right if it shares at least
half of their words.

Setup: a temporary golden folder with two short dialogues; a fake Claude that answers every part with the
same three fallacies (one exact, one with 4 of the 6 expected words, one on a fair argument) and no claims.
"""
import json

from fact_checker.cli import run_eval

DIALOGUES = {
    "one.json": {
        "title": "one", "published_at": "2026-01-15",
        "lines": [
            {"t": 0, "speaker": "host", "text": "qué opina de la propuesta de la oposición"},
            {"t": 4, "speaker": "guest", "text": "la oposición no tiene autoridad para hablar"},
            {"t": 9, "speaker": "guest", "text": "o aprobamos la ley o llega el caos"},
            {"t": 14, "speaker": "guest", "text": "la ley reduce los plazos de los permisos de obra"},
        ],
        "expected": [
            {"type": "fallacy", "label": "ad_hominem", "quote": "la oposición no tiene autoridad para hablar"},
            {"type": "fallacy", "label": "false_dilemma", "quote": "o aprobamos la ley o llega el caos"},
        ],
    },
    "two.json": {
        "title": "two", "published_at": "2026-01-15",
        "lines": [
            {"t": 0, "speaker": "host", "text": "por qué subió el precio del alquiler"},
            {"t": 4, "speaker": "guest", "text": "desde que gobierna mi partido todo ha mejorado en el país"},
            {"t": 10, "speaker": "guest", "text": "todos los expertos dicen que vamos bien"},
        ],
        "expected": [
            {"type": "fallacy", "label": "false_cause", "quote": "desde que gobierna mi partido todo ha mejorado"},
            {"type": "fallacy", "label": "vague_authority", "quote": "todos los expertos dicen que vamos bien"},
        ],
    },
}

SCRIPTED = [
    {"quote": "La oposición no tiene autoridad para hablar", "label": "ad_hominem", "speaker": "guest",
     "reason": "Ataca a la persona.", "confidence": 0.9},
    {"quote": "todos los expertos dicen", "label": "vague_authority", "speaker": "guest",
     "reason": "Autoridad sin nombre.", "confidence": 0.8},
    {"quote": "la ley reduce los plazos de los permisos de obra", "label": "hasty_generalization",
     "speaker": "guest", "reason": "Generaliza.", "confidence": 0.7},
]


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [dict(f) for f in SCRIPTED], "claims": []}


def test_eval_scores(tmp_path, capsys):
    for name, dialogue in DIALOGUES.items():
        (tmp_path / name).write_text(json.dumps(dialogue, ensure_ascii=False))

    report = run_eval(tmp_path, llm=FakeClaude(), factcheck=None)
    out = capsys.readouterr().out

    # Case 1 · 2 of the 3 fallacy flags match an expected one → precision 2/3
    assert abs(report["fallacy"]["precision"] - 2 / 3) < 0.01

    # Case 2 · 2 of the 4 expected fallacies are found → recall 1/2
    assert abs(report["fallacy"]["recall"] - 0.5) < 0.01

    # Case 3 · a flag that shares 4 of the 6 expected words, with the expected name → counts as right
    assert report["fallacy"]["matched"] == 2

    # Case 4 · the printed table shows the fallacy row with 67% and 50%
    row = next(line for line in out.splitlines() if line.startswith("fallacy"))
    assert "67%" in row and "50%" in row
    print("PASS S3 A2 · The eval scores flags against the expected ones")
