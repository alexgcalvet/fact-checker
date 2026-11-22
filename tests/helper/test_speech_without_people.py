"""An analysis from before roles has `speakers` but no `people`: its named voices still get their speaking time."""
from fact_checker import analyses


def test_named_voices_stand_in_for_people():
    data = {"video_id": "abcdefgh", "lang": "es", "status": "done", "speakers": {"SPEAKER_00": "Ana", "SPEAKER_01": "Luis"},
            "flags": []}
    turns = [{"start": 0, "end": 30, "speaker": "SPEAKER_00"}, {"start": 30, "end": 40, "speaker": "SPEAKER_01"}]
    people = analyses.strip(data, "v1", turns)["people"]
    assert set(people) == {"Ana", "Luis"}
    assert people["Ana"]["spoken_s"] == 30
    assert "role" not in people["Ana"]


def test_no_turns_no_people():
    data = {"video_id": "abcdefgh", "lang": "es", "status": "done", "speakers": {"SPEAKER_00": "Ana"}, "flags": []}
    assert "people" not in analyses.strip(data, "v1")
