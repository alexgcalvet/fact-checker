# S5 A1 · The helper shares each person's speaking time and turns
#
# Story: The owner runs `fact-checker shared upload debate01 es` for an analysis whose voice turns are on the machine.
# The uploaded analysis carries, per person, their role, seconds spoken, number of turns and longest turn, and the list
# of voice turns by person; two turns of one voice with no other voice between them count as one. For an analysis with
# no voice turns on the machine, those fields are absent and the upload still succeeds.
#
# Setup: a temporary helper home whose `config.toml` sets `feedback_url` to a fake collector on a free local port, and
# FEEDBACK_ADMIN_TOKEN set to the fake's admin token. Its flag file is the invented debate of the API examples (guests
# Ana and Luis, host Marta) with a stale `spoken_s` per person. Its voice turns `voices/debate01.turns.json` hold 10
# minutes of invented diarizer turns: Marta 0–20, Ana 20–100 and again 101–160 (one voice, a short pause), Luis 160–300,
# Ana 300–350, Marta 350–370, Luis 370–500. A second flag file, intervw1, has no voice turns.
import json
import sys
from pathlib import Path

from fact_checker import cli
from fake_servers import FakeCollector, TOKEN

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "api-examples"
PEOPLE = {name: {"role": role, "person": name, "spoken_s": 999, "set_by": "llm"}
          for name, role in (("Ana", "guest"), ("Luis", "guest"), ("Marta", "host"))}
DEBATE = {
    "video_id": "debate01", "lang": "es", "spoken": "es", "status": "done", "published_at": "2026-11-10",
    "title": "Debate inventado", "channel": "Invented Channel", "duration": 600, "analysed_until": 600,
    "speakers": {"SPEAKER_00": "Ana", "SPEAKER_01": "Luis", "SPEAKER_02": "Marta"}, "people": PEOPLE,
    "claims": {"Ana": 10, "Luis": 8}, "questions": {"Ana": 4, "Luis": 3},
    "readers": {r: {"provider": "claude", "model": "opus"} for r in ("parts", "verdict", "judge", "search")},
    "flags": json.loads((EXAMPLES / "debate-flags.json").read_text())["flags"],
}
TURNS = [{"start": 0.0, "end": 20.0, "speaker": "SPEAKER_02"}, {"start": 20.0, "end": 100.0, "speaker": "SPEAKER_00"},
         {"start": 101.0, "end": 160.0, "speaker": "SPEAKER_00"}, {"start": 160.0, "end": 300.0, "speaker": "SPEAKER_01"},
         {"start": 300.0, "end": 350.0, "speaker": "SPEAKER_00"}, {"start": 350.0, "end": 370.0, "speaker": "SPEAKER_02"},
         {"start": 370.0, "end": 500.0, "speaker": "SPEAKER_01"}]


def run(monkeypatch, capsys, *args) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out


def test_speech_upload(tmp_path, monkeypatch, capsys):
    home = tmp_path / "helper"
    (home / "videos").mkdir(parents=True)
    (home / "voices").mkdir()
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.setenv("FEEDBACK_ADMIN_TOKEN", TOKEN)
    collector = FakeCollector()
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    (home / "videos" / "debate01.json").write_text(json.dumps(DEBATE))
    (home / "voices" / "debate01.turns.json").write_text(json.dumps(TURNS))
    interview = DEBATE | {"video_id": "intervw1", "people": {"Ana": PEOPLE["Ana"], "Marta": PEOPLE["Marta"]}}
    (home / "videos" / "intervw1.json").write_text(json.dumps(interview))
    try:
        # Case 1 · `shared upload debate01 es` with voice turns → each person's role, seconds spoken, turns and longest turn
        code, out = run(monkeypatch, capsys, "shared", "upload", "debate01", "es")
        assert code == 0, out
        sent = collector.puts()[-1]["body"]["analysis"]
        speech = {name: {k: p.get(k) for k in ("role", "spoken_s", "turns", "longest_s")} for name, p in sent["people"].items()}
        assert speech == {
            "Ana": {"role": "guest", "spoken_s": 189, "turns": 2, "longest_s": 140},
            "Luis": {"role": "guest", "spoken_s": 270, "turns": 2, "longest_s": 140},
            "Marta": {"role": "host", "spoken_s": 40, "turns": 2, "longest_s": 20},
        }, f"FAIL S5 A1 · people {sent['people']}"

        # Case 2 · the voice turns by person → in order, Ana's two turns at 20–100 and 101–160 merged into one
        assert sent.get("turns") == [
            {"start": 0, "end": 20, "person": "Marta"}, {"start": 20, "end": 160, "person": "Ana"},
            {"start": 160, "end": 300, "person": "Luis"}, {"start": 300, "end": 350, "person": "Ana"},
            {"start": 350, "end": 370, "person": "Marta"}, {"start": 370, "end": 500, "person": "Luis"},
        ], f"FAIL S5 A1 · turns {sent.get('turns')}"
        assert list(sent["summary"]) == ["Ana", "Luis"], "FAIL S5 A1 · the summary changed"

        # Case 3 · an analysis with no voice turns on the machine → uploaded, with no turns and no speech per person
        code, out = run(monkeypatch, capsys, "shared", "upload", "intervw1", "es")
        assert code == 0, f"FAIL S5 A1 · the upload without voice turns failed: {out}"
        sent = collector.puts()[-1]["body"]["analysis"]
        assert sent["video_id"] == "intervw1"
        assert "turns" not in sent, "FAIL S5 A1 · turns sent without voice turns"
        assert {n: p["role"] for n, p in sent["people"].items()} == {"Ana": "guest", "Marta": "host"}
        for name, p in sent["people"].items():
            assert not {"spoken_s", "turns", "longest_s"} & set(p), f"FAIL S5 A1 · speech of {name} without voice turns: {p}"
        print("PASS S5 A1 · The helper shares each person's speaking time and turns")
    finally:
        collector.stop()
