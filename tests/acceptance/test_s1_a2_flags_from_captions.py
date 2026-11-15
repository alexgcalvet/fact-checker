"""S1 A2 · Flags quote the exact words, at their second, from the closed list only

Story: From an invented 4-minute dialogue with 3 planted fallacies, the analysis returns flags whose
words appear word for word in the captions, whose second is when those words start, and whose name is
one of the 8 in the list. A name outside the list, or words that are not in the captions, give no flag;
an out-of-list name goes to the candidates log with its words.

Setup: the invented captions in tests/fakes/youtube/, parsed by the YouTube adapter; a fake Claude that
answers every part with the same five flags (three valid, one outside the list, one invented quote),
written with capitals and punctuation as a model would; a temporary helper home.
"""
import json
from pathlib import Path

from fact_checker.adapters.youtube import parse_json3
from fact_checker.server import run_analysis

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-dialogue.json3"

SCRIPTED = [
    {"quote": "La oposición no tiene autoridad para hablar.", "label": "ad_hominem", "speaker": "minister",
     "reason": "Attacks the critic instead of the criticism.", "confidence": 0.9},
    {"quote": "Ustedes, cuando gobernaron, subieron más los alquileres", "label": "tu_quoque", "speaker": "minister",
     "reason": "Answers a criticism by pointing at the critic's past.", "confidence": 0.85},
    {"quote": "O aprobamos nuestra ley o los alquileres seguirán subiendo", "label": "false_dilemma", "speaker": "minister",
     "reason": "Presents two options when there are more.", "confidence": 0.82},
    {"quote": "Piense en las familias que lo están pasando mal", "label": "appeal_to_emotion", "speaker": "minister",
     "reason": "Appeals to emotion.", "confidence": 0.7},
    {"quote": "Esta frase nunca se dijo en el programa", "label": "straw_man", "speaker": "host",
     "reason": "Invented.", "confidence": 0.95},
]


class FakeTranscript:
    def fetch(self, video_id):
        return parse_json3(json.loads(FAKE.read_text()), published_at="2026-11-10")


class FakeClaude:
    def complete(self, prompt, schema):
        return {"flags": [dict(f) for f in SCRIPTED]}


def test_flags_from_captions(tmp_path):
    run_analysis("invented", 0, transcript=FakeTranscript(), llm=FakeClaude(), home=tmp_path)
    data = json.loads((tmp_path / "videos" / "invented.json").read_text())
    by_label = {f["label"]: f for f in data["flags"]}

    # Case 1 · three valid fallacies → exactly three flags, one per planted fallacy, none duplicated
    assert data["status"] == "done"
    assert sorted(by_label) == ["ad_hominem", "false_dilemma", "tu_quoque"]
    assert len(data["flags"]) == 3

    # Case 2 · each flag quotes the caption words, not the model's punctuation → exact caption text
    assert by_label["ad_hominem"]["quote"] == "la oposición no tiene autoridad para hablar"
    assert by_label["tu_quoque"]["quote"] == "ustedes cuando gobernaron subieron más los alquileres"
    assert by_label["false_dilemma"]["quote"] == "o aprobamos nuestra ley o los alquileres seguirán subiendo"

    # Case 3 · each flag's second is when its first word starts → 42, 62 and 168 seconds
    assert abs(by_label["ad_hominem"]["t"] - 42.0) < 0.01
    assert abs(by_label["tu_quoque"]["t"] - 62.0) < 0.01
    assert abs(by_label["false_dilemma"]["t"] - 168.0) < 0.01
    for f in data["flags"]:
        assert f["type"] == "fallacy" and f["reason"] and 0 <= f["confidence"] <= 1

    # Case 4 · a name outside the list → no flag, one line in the candidates log with its words
    lines = [json.loads(x) for x in (tmp_path / "candidates.log").read_text().splitlines()]
    assert [(c["label"], c["quote"]) for c in lines] == [
        ("appeal_to_emotion", "piense en las familias que lo están pasando mal")]

    # Case 5 · words that are not in the captions → no flag and no candidate
    assert all("nunca se dijo" not in f["quote"] for f in data["flags"])
    print("PASS S1 A2 · Flags quote the exact words, at their second, from the closed list only")
