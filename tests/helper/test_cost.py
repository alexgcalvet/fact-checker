"""The cost: what each reading logs about its tokens, cost and time."""
import json
import os
import sys
import threading

from pytest import approx

from fact_checker import analyses, server
from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fact_checker.core.flags import Prompt, Session
from fact_checker.core.prices import cost
from fact_checker.server import run_analysis
from first_part_fakes import CAPTIONS, flag_file, GuessingModel, PART_S, wait_for
from interview_fakes import FALSE, INE, ONE_PART, SECOND
from video_fakes import fake_video


# S17 A1 · Every Claude reading logs its tokens and cost
#
# Story: The helper analyses an invented video. Each line of the usage log has, beside the step and duration, the input,
# cached and output tokens and the cost in dollars of that reading, such as `"cost_usd": 0.106`; the flag file's
# `cost_usd` holds the sum for the video.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
# gives one false figure that carries his argument. The helper runs as it does for the person (Helper._run), with a fake
# YouTube that returns these captions, a fake Fact Check Tools API that finds nothing and no voices. The `claude` command
# is a fake on PATH: it answers by the JSON schema it gets (part, search, verdict or judge) as `claude -p
# --output-format json` does, each with its own invented token counts and `total_cost_usd`. A temporary helper home.

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


def test_cost_log(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}")
    fake.chmod(0o755)
    (tmp_path / "readings.json").write_text(json.dumps(READINGS))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_READINGS", str(tmp_path / "readings.json"))
    fake_video(monkeypatch, ONE_PART)
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


# S31 A4 · The time to the first part is logged
#
# Story: After an analysis with part readings of 0.2 seconds, the flag file holds `first_flags_s`, the seconds from the
# start of the analysis to the first part written, such as 0.4; later parts do not change it, and a shared copy of the
# analysis leaves it out.
#
# Setup: the invented interview of S31 A1 (captions with no voices, four parts), read whole with no viewer and no speaker
# separation, by a fake model whose part readings take 0.2 s, in a thread so the test can read the flag file while the
# analysis runs. A second run whose captions cannot be fetched. A temporary helper home per run.

class NoCaptions:
    def fetch(self, video_id):
        raise RuntimeError("yt-dlp failed")


def test_first_flags_logged(tmp_path):
    run = threading.Thread(target=run_analysis, args=("tiempo01", 0), daemon=True,
                           kwargs={"transcript": CAPTIONS, "llm": GuessingModel(), "home": tmp_path / "one"})
    run.start()

    # Case 1 · the first part is written → the flag file holds first_flags_s, at least one part reading and under 2 s
    first = wait_for(lambda: (flag_file(tmp_path / "one", "tiempo01") or {}).get("first_flags_s"), timeout=5)
    assert first is not None, "FAIL S31 A4 · no first_flags_s after the first part"
    assert PART_S <= first < 2, f"FAIL S31 A4 · first_flags_s is {first}"

    # Case 2 · every part is done → first_flags_s keeps its value, and the shared copy leaves it out
    run.join(timeout=15)
    data = flag_file(tmp_path / "one", "tiempo01")
    assert data["status"] == "done" and data["first_flags_s"] == first, data
    assert "first_flags_s" not in analyses.strip(data), "FAIL S31 A4 · the shared copy carries first_flags_s"

    # Case 3 · the captions cannot be fetched → the analysis stops with no first_flags_s
    run_analysis("tiempo01", 0, transcript=NoCaptions(), llm=GuessingModel(), home=tmp_path / "none")
    data = flag_file(tmp_path / "none", "tiempo01")
    assert data["status"] == "stopped" and "first_flags_s" not in data, data
    print("PASS S31 A4 · The time to the first part is logged")


# Long prompts cost more on some models: the whole request takes the higher price once its prompt passes the bar.

def usage_prices(fresh, read=0, out=0):
    return {"input_tokens": fresh, "cache_creation_input_tokens": 0, "cache_read_input_tokens": read,
            "output_tokens": out}


def test_haiku_prompt_over_100k_pays_five_times():
    assert cost("claude-haiku-5-5", usage_prices(100_000, out=1_000_000)) == approx(0.01 + 0.50)
    # Cache reads count toward the prompt length.
    assert cost("claude-haiku-5-5", usage_prices(1, read=100_000, out=1_000_000)) == approx((1 * 0.50 + 100_000 * 0.05) / 1e6 + 2.50)


def test_grok_prompt_at_200k_pays_double():
    assert cost("grok-4.7", usage_prices(199_999)) == approx(199_999 * 2 / 1e6)
    assert cost("grok-4.7", usage_prices(200_000, out=1_000_000)) == approx(0.8 + 12)


def test_grok_searches_have_no_published_price():
    assert cost("grok-4.7", usage_prices(1_000), searches=3) is None


# A resumed Claude Code session reports a total cost that keeps growing; a resumed reading is priced from its tokens.

USAGE = {"input_tokens": 1000, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 100000, "output_tokens": 500}


def test_resumed_reading_costs_its_tokens(tmp_path, monkeypatch):
    totals = tmp_path / "totals"
    totals.write_text("0.10\n2.15\n")
    fake = tmp_path / "claude"
    fake.write_text(f'#!/bin/sh\nt=$(head -1 {totals}); sed -i "" 1d {totals} 2>/dev/null || sed -i 1d {totals}\n'
                    f'echo \'{{"is_error": false, "usage": {json.dumps(USAGE)}, "structured_output": {{}}, '
                    f'"total_cost_usd": \'$t\'}}\'\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    llm, session = ClaudeCLI(tmp_path, model="opus"), Session()
    costs = [llm.complete(Prompt("reglas", "parte", session), {"type": "object"}).usage["cost_usd"] for _ in range(2)]
    # Opus: 1000 × 4 + 2000 × 5 + 100000 × 0.20 + 500 × 20 dollars per million tokens.
    assert costs == [0.10, 0.044], costs
