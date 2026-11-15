"""S19 A1 · A new analysis reads the parts as one conversation

Story: The person opens an invented video and the helper starts its analysis as it does for the extension. Every part
reading continues the same Claude Code conversation, not a fresh reading with a short window.

Setup: an invented 6-minute transcript with one numbered line every 10 seconds, served by a fake YouTube. A fake
Claude records the conversation (session) that each part reading names, and finds nothing. No Fact Check Tools key and
no voices. The helper starts the analysis from second 0 as the extension's first request does (Helper.start), and the
test waits until the flag file says done. A temporary helper home.
"""
import json
import time

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript

VIDEO = "conversa1"
LINES = [Segment(t=float(t), text=f"frase número {t} del programa") for t in range(0, 360, 10)]


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        return Transcript(segments=LINES, published_at="2026-11-10")


class FakeClaude:
    sessions = []

    def __init__(self, *args, **kwargs):
        pass

    def complete(self, prompt, schema, tools=()):
        if "flags" in schema["properties"]:
            session = getattr(prompt, "session", None)
            FakeClaude.sessions.append(session and session.id)
            if session:
                session.turns += 1
            return {"flags": [], "claims": [], "questions": [], "contradictions": [], "positions": [], "context": []}
        return {"rulings": []}


def test_parts_continue_one_conversation(tmp_path, monkeypatch):
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "ClaudeCLI", FakeClaude)
    FakeClaude.sessions = []
    helper = server.Helper(tmp_path)

    # Case 1 · the extension's first request → the analysis of the whole short video ends done
    helper.start(VIDEO, 0)
    path = tmp_path / "videos" / f"{VIDEO}.json"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not (path.exists() and json.loads(path.read_text())["status"] != "running"):
        time.sleep(0.1)
    data = json.loads(path.read_text())
    assert data["status"] == "done", data

    # Case 2 · every part reading → names a conversation, and all name the same one
    assert len(FakeClaude.sessions) >= 3, FakeClaude.sessions
    assert None not in FakeClaude.sessions, FakeClaude.sessions
    assert len(set(FakeClaude.sessions)) == 1, FakeClaude.sessions
