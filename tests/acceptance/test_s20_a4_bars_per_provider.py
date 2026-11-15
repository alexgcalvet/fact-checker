"""S20 A4 · Codex flags meet Codex bars

Story: With Codex as the provider and no Codex bars yet, a fallacy at confidence 0.6 goes to the side panel, not on
the player, though the Claude bar is 0.4. Once a Codex bars file sets the fallacy bar at 0.5, the same flag goes on
the player. With Claude as the provider, the Claude bars apply as before.

Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake LLM that returns one fallacy at 0.6
and no claims. The Claude bars file is a temporary thresholds.json with fallacy 0.4 and inaccuracy 0.6; the Codex
bars file, when it exists, is thresholds.codex.json beside it. run_analysis gets no thresholds, so it reads the bars
of the provider in FACT_CHECK_PROVIDER. A temporary helper home per run.
"""
import json
from pathlib import Path

from fact_checker import server
from fact_checker.adapters.youtube import parse_json3

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-claims.json3"


class FakeTranscript:
    def fetch(self, video_id):
        return parse_json3(json.loads(FAKE.read_text()), published_at="2026-11-10")


class FakeLLM:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [{"quote": "eso es lo que dicen los datos", "label": "vague_authority", "speaker": "guest",
                           "reason": "Vago.", "confidence": 0.6}], "claims": []}


def on_player(home: Path) -> bool:
    server.run_analysis("claims", 0, transcript=FakeTranscript(), llm=FakeLLM(), home=home)
    flags = json.loads((home / "videos" / "claims.json").read_text())["flags"]
    [fallacy] = [f for f in flags if f["type"] == "fallacy"]
    assert fallacy["confidence"] == 0.6, fallacy
    return fallacy["on_player"]


def test_bars_per_provider(tmp_path, monkeypatch):
    bars = tmp_path / "bars"
    bars.mkdir()
    (bars / "thresholds.json").write_text(json.dumps({"fallacy": 0.4, "inaccuracy": 0.6}))
    monkeypatch.setattr(server, "THRESHOLDS", bars / "thresholds.json")

    # Case 1 · Codex, no Codex bars file → the 0.6 fallacy meets the 0.8 default bar, not the Claude bar of 0.4:
    # side panel only
    monkeypatch.setenv("FACT_CHECK_PROVIDER", "codex")
    assert on_player(tmp_path / "codex-default") is False

    # Case 2 · Codex, a Codex bars file with fallacy 0.5 → the same flag goes on the player
    (bars / "thresholds.codex.json").write_text(json.dumps({"fallacy": 0.5, "inaccuracy": None}))
    assert on_player(tmp_path / "codex-tuned") is True

    # Case 3 · Claude (no provider set), the Codex file now at fallacy 0.9 → the Claude bar of 0.4 applies: on the player
    (bars / "thresholds.codex.json").write_text(json.dumps({"fallacy": 0.9, "inaccuracy": None}))
    monkeypatch.delenv("FACT_CHECK_PROVIDER")
    assert on_player(tmp_path / "claude") is True
    print("PASS S20 A4 · Codex flags meet Codex bars")
