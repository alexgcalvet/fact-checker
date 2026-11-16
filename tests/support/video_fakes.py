"""The invented videos that the helper reads in the tests: their captions, their voices, and a published fact-check
search that finds nothing."""
import json
from pathlib import Path

from fact_checker import server
from fact_checker.adapters.youtube import parse_json3
from fact_checker.core.flags import Segment, Transcript

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
VOICES = {HOST: "Presentadora", GUEST: "Invitado"}


def spoken(lines) -> list[Segment]:
    """The words of each line, one every 0.5 s from its start: (start, text) lines with no voice, or
    (start, voice, text) lines in that voice."""
    return [Segment(t=line[0] + i * 0.5, text=w, speaker=line[1] if len(line) == 3 else None)
            for line in lines for i, w in enumerate(line[-1].split())]


class FakeTranscript:
    """The captions of an invented video: each fetch gives `segments`, with the other Transcript fields as given."""

    def __init__(self, segments: list[Segment], published_at: str | None = "2026-11-10", **fields):
        self.segments, self.published_at, self.fields = segments, published_at, fields

    def fetch(self, video_id):
        return Transcript(segments=list(self.segments), published_at=self.published_at, **self.fields)


class FakeVoices:
    """A speaker separation that finds `found`: a list of voice turns."""

    def __init__(self, found: list[dict]):
        self.found = found

    def turns(self, video_id):
        return self.found


class NoPublishedChecks:
    """The Fact Check Tools API: finds nothing, and records each search as (query, language)."""
    searches: list = []

    def __init__(self, key=None):
        pass

    def search(self, query, language):
        NoPublishedChecks.searches.append((query, language))
        return []


def fake_video(monkeypatch, lines) -> None:
    """Every video is the voiced `lines`, read by the voices of VOICES; published fact-checks on, finding nothing; no
    voices from the audio; no provider, API key or Codex path from the environment."""
    for name in ("FACT_CHECK_PROVIDER", "HF_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY",
                 "CHAT_API_KEY", "CODEX_BIN", "FAKE_SCREEN_FAILS", "FAKE_SCREEN_ODD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.setattr(server, "YouTube", lambda *args: FakeTranscript(spoken(lines), speakers=VOICES))
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)


class JSON3Captions:
    """The captions of a recorded json3 file in tests/fakes/youtube/, as the YouTube adapter parses them."""

    def __init__(self, path: Path):
        self.path = path

    def fetch(self, video_id):
        return parse_json3(json.loads(self.path.read_text()), published_at="2026-11-10")
