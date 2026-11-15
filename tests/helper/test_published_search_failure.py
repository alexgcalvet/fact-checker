"""A network error in the search for published fact-checks does not stop the analysis of the video."""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

QUOTE = "la oposición no tiene ninguna autoridad moral"


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=[Segment(t=i * 0.5, text=w) for i, w in enumerate(QUOTE.split())],
                          published_at="2026-11-10")


class FailingGoogle:
    def search(self, query, language):
        raise ConnectionResetError(54, "Connection reset by peer")


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if tools:
            return {"verdicts": []}
        return {"flags": [{"quote": QUOTE, "label": "ad_hominem", "speaker": "Invitado",
                           "reason": "Ataca a la persona.", "confidence": 0.9}],
                "claims": [{"quote": QUOTE, "speaker": "Invitado", "queries": ["oposición autoridad"]}]}


def test_search_failure_keeps_analysis(tmp_path):
    run_analysis("reset", 0, transcript=FakeTranscript(), llm=FakeClaude(), factcheck=FailingGoogle(),
                 home=tmp_path, thresholds={})
    data = json.loads((tmp_path / "videos" / "reset.json").read_text())
    assert data["status"] == "done", data["stop_reason"]
    assert [f["label"] for f in data["flags"]] == ["ad_hominem"]
