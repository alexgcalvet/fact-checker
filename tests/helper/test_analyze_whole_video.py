"""`fact-checker analyze <url>` reads the whole video as the helper does, with no tab open to follow.

An analysis started over HTTP follows the extension's playback second and pauses about ten minutes ahead of it when
nobody polls; the command must not stop there.
"""
import json
import sys

from fact_checker import cli, server
from fact_checker.core.flags import Segment, Transcript

VIDEO = "entera1234"
LINES = [Segment(t=float(t), text=f"frase número {t} del programa") for t in range(0, 1500, 10)]  # 25 minutes


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        return Transcript(segments=LINES, published_at="2026-11-10")


class FakeClaude:
    def __init__(self, *args, **kwargs):
        pass

    def complete(self, prompt, schema, tools=()):
        if "flags" in schema["properties"]:
            return {"flags": [], "claims": [], "questions": [], "contradictions": [], "positions": [], "context": []}
        return {"rulings": []}


def test_analyze_reads_past_the_horizon(tmp_path, monkeypatch):
    monkeypatch.setenv("FACT_CHECKER_HOME", str(tmp_path))
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "ClaudeCLI", FakeClaude)
    monkeypatch.setattr(sys, "argv", ["fact-checker", "analyze", f"https://www.youtube.com/watch?v={VIDEO}&t=60s"])

    cli.main()

    data = json.loads((tmp_path / "videos" / f"{VIDEO}.json").read_text())
    assert data["status"] == "done", data
    assert data["analysed_until"] >= LINES[-1].t
