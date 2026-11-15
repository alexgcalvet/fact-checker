"""S3 A4 (helper part) · Only flags above their type's bar reach the player

Story: With bars fallacy 0.5 and inaccuracy 0.9, the helper marks a 0.55 fallacy for the player and a
0.85 inaccuracy not. The extension part is s3-a4-on-player.test.ts; s3-a4-bar-per-type.sh runs both.

Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake Claude that returns one
fallacy at 0.55 and one claim it judges false at 0.85 with a dated source; no published checks.
"""
import json
from pathlib import Path

from fact_checker.adapters.youtube import parse_json3
from fact_checker.server import run_analysis

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-claims.json3"


class FakeTranscript:
    def fetch(self, video_id):
        return parse_json3(json.loads(FAKE.read_text()), published_at="2026-11-10")


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [{"quote": "el paro juvenil se duplicó el año pasado", "verdict": "false",
                                  "reason": "No.", "confidence": 0.85, "note": None,
                                  "sources": [{"publisher": "INE", "url": "https://www.ine.es/x", "date": "2025-10-28"}]}]}
        return {"flags": [{"quote": "eso es lo que dicen los datos", "label": "vague_authority", "speaker": "guest",
                           "reason": "Vago.", "confidence": 0.55}],
                "claims": [{"quote": "el paro juvenil se duplicó el año pasado", "speaker": "guest", "queries": ["paro"]}]}


class NoPublishedChecks:
    def search(self, query, language):
        return []


def test_on_player_by_type(tmp_path):
    run_analysis("claims", 0, transcript=FakeTranscript(), llm=FakeClaude(), factcheck=NoPublishedChecks(),
                 home=tmp_path, thresholds={"fallacy": 0.5, "inaccuracy": 0.9})
    flags = {f["type"]: f for f in json.loads((tmp_path / "videos" / "claims.json").read_text())["flags"]}

    # Case 1 · a 0.55 fallacy with the fallacy bar at 0.5 → marked for the player
    assert flags["fallacy"]["on_player"] is True

    # Case 2 · a 0.85 inaccuracy with the inaccuracy bar at 0.9 → not marked
    assert flags["inaccuracy"]["on_player"] is False
    print("PASS S3 A4 (helper) · Only flags above their type's bar reach the player")
