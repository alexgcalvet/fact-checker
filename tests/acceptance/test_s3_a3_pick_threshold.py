"""S3 A3 · The eval picks the bar per type and saves it

Story: The fallacy flags of a run have confidences 0.9 right, 0.85 right, 0.7 wrong, 0.6 right, 0.5 wrong;
the inaccuracy flags are all wrong. With "save", the eval writes fallacy 0.85 and inaccuracy "never" to the
thresholds file.

Setup: a temporary golden folder with one dialogue that expects three fallacies and no inaccuracy; a fake
Claude that returns five fallacies (three on the expected words at 0.9, 0.85 and 0.6, two on fair lines at
0.7 and 0.5) and five claims that it then judges false with dated sources; a fake Fact Check Tools API that
finds nothing; a temporary thresholds file.
"""
import json

from fact_checker.cli import run_eval

LINES = [
    "la oposición no tiene autoridad para hablar",
    "o aprobamos la ley o llega el caos",
    "todos los expertos dicen que vamos bien",
    "la ley reduce los plazos de los permisos de obra",
    "el plan prevé cuatro mil viviendas nuevas",
    "el paro en enero fue del once por ciento",
    "la deuda pública bajó el año pasado",
    "el salario mínimo subió en febrero",
]
DIALOGUE = {
    "title": "bars", "published_at": "2026-01-15",
    "lines": [{"t": i * 3, "speaker": "guest", "text": text} for i, text in enumerate(LINES)],
    "expected": [
        {"type": "fallacy", "label": "ad_hominem", "quote": LINES[0]},
        {"type": "fallacy", "label": "false_dilemma", "quote": LINES[1]},
        {"type": "fallacy", "label": "vague_authority", "quote": LINES[2]},
    ],
}
FLAGS = [
    (LINES[0], "ad_hominem", 0.9), (LINES[1], "false_dilemma", 0.85), (LINES[3], "false_cause", 0.7),
    (LINES[2], "vague_authority", 0.6), (LINES[4], "hasty_generalization", 0.5),
]
CLAIMS = [LINES[4], LINES[5], LINES[6], LINES[7], LINES[3]]


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                {"quote": q, "verdict": "false", "reason": "No.", "confidence": 0.95,
                 "sources": [{"publisher": "INE", "url": f"https://www.ine.es/{i}", "date": "2025-12-01"}],
                 "note": None} for i, q in enumerate(CLAIMS)]}
        return {"flags": [{"quote": q, "label": l, "speaker": "guest", "reason": "r", "confidence": c}
                          for q, l, c in FLAGS],
                "claims": [{"quote": q, "speaker": "guest", "queries": [q]} for q in CLAIMS]}


class NoPublishedChecks:
    def search(self, query, language):
        return []


def test_pick_threshold(tmp_path):
    golden = tmp_path / "golden"
    golden.mkdir()
    (golden / "bars.json").write_text(json.dumps(DIALOGUE, ensure_ascii=False))
    saved = tmp_path / "thresholds.json"

    report = run_eval(golden, llm=FakeClaude(), factcheck=NoPublishedChecks(), save_to=saved)

    # Case 1 · fallacies right at 0.9 and 0.85, wrong at 0.7 → the lowest bar with precision ≥ 0.80 is 0.85
    assert report["fallacy"]["bar"] == 0.85

    # Case 2 · five inaccuracy flags, all wrong → no bar: "never"
    assert report["inaccuracy"]["bar"] is None

    # Case 3 · with save → the thresholds file holds fallacy 0.85 and inaccuracy null
    assert json.loads(saved.read_text()) == {"fallacy": 0.85, "inaccuracy": None}
    print("PASS S3 A3 · The eval picks the bar per type and saves it")
