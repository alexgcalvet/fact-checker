"""S17 A1 · Every Claude reading logs its tokens and cost

Story: The helper analyses an invented video. Each line of the usage log has, beside the step and duration, the input,
cached and output tokens and the cost in dollars of that reading, such as `"cost_usd": 0.106`; the flag file's
`cost_usd` holds the sum for the video.

Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
gives one false figure that carries his argument. The helper runs as it does for the person (Helper._run), with a fake
YouTube that returns these captions, a fake Fact Check Tools API that finds nothing and no voices. The `claude` command
is a fake on PATH: it answers by the JSON schema it gets (part, search, verdict or judge) as `claude -p
--output-format json` does, each with its own invented token counts and `total_cost_usd`. A temporary helper home.
"""
import json
import os
import stat
import sys

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
LINES = [
    (0, GUEST, f"Mire {FALSE} y eso lo cambia todo"),
    (20, HOST, "Muchas gracias por venir y buenas noches"),
]
WORDS = LINES[0][2].split()
SECOND = WORDS.index(FALSE.split()[0]) * 0.5
INE = {"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}


def usage(created, read, output):
    return {"input_tokens": 3, "cache_creation_input_tokens": created, "cache_read_input_tokens": read,
            "output_tokens": output}


# The answer of each reading, by a property of its JSON schema, with its invented usage and cost.
READINGS = {
    "flags": {"step": "analyze_chunk", "cost": 0.106, "usage": usage(9000, 4000, 1500), "num_turns": 1, "answer": {
        "flags": [], "questions": [], "contradictions": [], "positions": [], "context": [],
        "claims": [{"quote": FALSE, "speaker": "Invitado", "queries": [FALSE], "question": None, "kind": "fact",
                    "central": True, "repeats": None}]}},
    "evidence": {"step": "search", "cost": 0.031, "usage": usage(7000, 12000, 600), "num_turns": 3, "answer": {
        "evidence": [{"quote": FALSE, "findings": [INE | {"says": "La tasa de paro bajó del 12 % al 11 %."}]}]}},
    "verdicts": {"step": "fact_check", "cost": 0.052, "usage": usage(2500, 3000, 400), "num_turns": 1, "answer": {
        "verdicts": [{"quote": FALSE, "verdict": "false", "reason": "Bajó un punto.", "confidence": 0.9,
                      "sources": [INE], "note": None, "controversy": None, "published": [], "earlier": None,
                      "promise": None, "measures": [{"name": "Paro EPA", "value": "11 %", "source": "INE",
                                                     "tier": 1, "supports": False}]}]}},
    "rulings": {"step": "judge", "cost": 0.087, "usage": usage(6000, 0, 300), "num_turns": 1, "answer": {
        "rulings": [{"id": f"false-{SECOND:.1f}", "verdict": "keep", "reason": "Se sostiene.", "speaker": None}]}},
}

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
schema = json.loads(args[args.index("--json-schema") + 1])
readings = json.load(open(os.environ["FAKE_CLAUDE_READINGS"]))
key = next(k for k in readings if k in schema["properties"])
r = readings[key]
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "num_turns": r["num_turns"], "duration_ms": 1000, "total_cost_usd": r["cost"], "usage": r["usage"],
                  "result": json.dumps(r["answer"]), "structured_output": r["answer"]}))
"""


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class NoPublishedChecks:
    def __init__(self, key):
        pass

    def search(self, query, language):
        return []


def test_cost_log(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "readings.json").write_text(json.dumps(READINGS))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_READINGS", str(tmp_path / "readings.json"))
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text("screen = false\n")  # S29: no screen readings here

    server.Helper(home)._run("coste", 0)
    data = json.loads((home / "videos" / "coste.json").read_text())
    lines = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    assert data["status"] == "done", data

    # Case 1 · the part, search, verdict and judge readings of the video → one usage line each, named by its step
    assert sorted(x["step"] for x in lines) == sorted(r["step"] for r in READINGS.values()), lines

    # Case 2 · each line → beside its step and duration, the input, cached and output tokens and the cost in
    # dollars of that reading
    for r in READINGS.values():
        line = next(x for x in lines if x["step"] == r["step"])
        assert isinstance(line["duration_s"], (int, float)), line
        for field, value in r["usage"].items():
            assert line.get(field) == value, (r["step"], field, line)
        assert line.get("cost_usd") == r["cost"], (r["step"], line)
        assert line["video_id"] == "coste", line

    # Case 3 · the flag file → `cost_usd` is the sum of the costs of its readings
    total = sum(r["cost"] for r in READINGS.values())
    assert abs(data.get("cost_usd", -1) - total) < 1e-6, (data.get("cost_usd"), total)
    print("PASS S17 A1 · Every Claude reading logs its tokens and cost")
