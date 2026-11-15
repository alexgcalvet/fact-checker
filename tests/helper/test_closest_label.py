"""A fallacy that the model names outside the list becomes a flag of the listed label it is a form of."""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

QUOTE = "el partido socialista en la oposición no pidió la dimisión de ana pastor"
OTHER = "esto es como lo que hacían en los años treinta"


class FakeTranscript:
    def fetch(self, video_id):
        words = f"{QUOTE} {OTHER}".split()
        return Transcript(segments=[Segment(t=i * 0.5, text=w) for i, w in enumerate(words)], published_at=None)


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [
            {"quote": QUOTE, "label": "whataboutism", "closest": "tu_quoque", "speaker": "Invitado",
             "reason": "Responde con lo que hizo el otro partido.", "confidence": 0.8},
            {"quote": OTHER, "label": "false_analogy", "closest": None, "speaker": "Invitado",
             "reason": "Compara dos épocas sin base.", "confidence": 0.7},
        ], "claims": []}


def test_closest_listed_label(tmp_path):
    run_analysis("closest", 0, transcript=FakeTranscript(), llm=FakeClaude(), home=tmp_path, thresholds={})
    flags = json.loads((tmp_path / "videos" / "closest.json").read_text())["flags"]
    assert [(f["label"], f["quote"]) for f in flags] == [("tu_quoque", QUOTE)]
    names = [json.loads(line)["label"] for line in (tmp_path / "candidates.log").read_text().splitlines()]
    assert names == ["whataboutism", "false_analogy"]
