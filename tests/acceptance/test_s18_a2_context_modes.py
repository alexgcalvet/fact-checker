"""S18 A2 · A part gets its context as a short window or as one long conversation

Story: The helper analyses an invented 20-minute interview twice. With the short window, each part reading holds the 3
minutes before it and the list of earlier positions. With the long conversation, the parts are read in order in one
Claude Code session that each reading resumes, and each reading sends only its own 2 minutes; a contradiction between
minute 1 and minute 18 is flagged in both.

Setup: invented word-by-word captions (one word every 0.5 s) of a 20-minute interview: one numbered line every 30 s,
each in the voice of SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado"). The guest states a position at 1:00 and
says the opposite at 18:00. The helper runs run_analysis from second 0 with the real Claude Code adapter
(ClaudeCLI(home, model="opus")); the `claude` command is a fake on PATH that keeps sessions as Claude Code does: a
reading with --session-id starts a session, a reading with --resume continues it and fails for an unknown one. Each
reading's prompt is logged. In each part reading, the fake lists the 1:00 position when its PART holds it, and lists
the 18:00 contradiction with the 1:00 words as `earlier` only when it has seen the 1:00 words: earlier in the same
session, or before the PART of this prompt. The window run reads one part at a time (scheduler.PARALLEL = 1); the
conversation run keeps the helper's parallel setting. A temporary helper home per run.
"""
import json
import os
import re
import stat
import sys

from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FIRST = "no vamos a subir el IVA de la luz"
SECOND = "vamos a subir el IVA de la luz este mismo año"
STATEMENTS = {60: FIRST, 1080: SECOND}


def line(t):
    return STATEMENTS.get(t, f"frase número {t} del programa")


LINES = [(t, GUEST if t in STATEMENTS or t % 60 else HOST, line(t)) for t in range(0, 1200, 30)]
NUMBERED = {t: text for t, _, text in LINES if t not in STATEMENTS}

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
prompt = opt("-p")
sessions = os.environ["FAKE_CLAUDE_SESSIONS"]
seen = ""
if opt("--resume"):
    path = os.path.join(sessions, opt("--resume"))
    if not os.path.exists(path):
        print(json.dumps({"type": "result", "is_error": True, "api_error_status": None, "result": "No conversation found"}))
        sys.exit(1)
    seen = open(path).read()
    open(path, "a").write(prompt)
elif opt("--session-id"):
    path = os.path.join(sessions, opt("--session-id"))
    if os.path.exists(path):
        print(json.dumps({"type": "result", "is_error": True, "api_error_status": None, "result": "Session ID in use"}))
        sys.exit(1)
    open(path, "w").write(prompt)
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({"prompt": prompt, "session_id": opt("--session-id"), "resume": opt("--resume")}) + "\\n")
head, _, part = prompt.rpartition("PART:")
first, second = os.environ["FIRST"], os.environ["SECOND"]
answer = {"flags": [], "claims": [], "questions": [], "context": [], "contradictions": [], "positions": []}
if first in part:
    answer["positions"].append({"quote": first, "speaker": "Invitado", "summary": "no subirá el IVA de la luz"})
if second in part and first in seen + head:
    answer["contradictions"].append({"quote": second, "earlier": first, "speaker": "Invitado",
                                     "earlier_speaker": "Invitado", "confidence": 0.9,
                                     "reason": "Al minuto 1 dijo que no subiría el IVA y ahora que sí."})
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "num_turns": 1, "duration_ms": 1000, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 3, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0,
                            "output_tokens": 10}, "result": json.dumps(answer), "structured_output": answer}))
"""


class FakeTranscript:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


def analyse(tmp_path, monkeypatch, mode):
    run_dir = tmp_path / mode
    (run_dir / "sessions").mkdir(parents=True)
    bin_dir = run_dir / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    log = run_dir / "readings.jsonl"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_SESSIONS", str(run_dir / "sessions"))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FIRST", FIRST)
    monkeypatch.setenv("SECOND", SECOND)
    home = run_dir / "home"
    home.mkdir()
    run_analysis("iva", 0, transcript=FakeTranscript(), llm=ClaudeCLI(home, model="opus"), home=home,
                 context_mode=mode)
    data = json.loads((home / "videos" / "iva.json").read_text())
    assert data["status"] == "done", data
    readings = [json.loads(x) for x in log.read_text().splitlines()]
    return data, readings


def part_start(reading):
    """The second of the first line in the PART of a reading."""
    part = reading["prompt"].rpartition("PART:")[2]
    return min(t for t, text in [*NUMBERED.items(), *STATEMENTS.items()] if text in part)


def contradiction(data):
    return [(f["t"], f["related"]["t"]) for f in data["flags"] if f["type"] == "contradiction"]


def test_short_window(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    data, readings = analyse(tmp_path, monkeypatch, "window")

    # Case 1 · every part reading → holds the numbered lines of the 3 minutes before its part, and none older
    assert len(readings) > 5, len(readings)
    for r in readings:
        start = part_start(r)
        head = r["prompt"].rpartition("PART:")[0]
        for t, text in NUMBERED.items():
            if start - 180 <= t < start:
                assert text in head, (start, t)
            elif t < start - 180:
                assert text not in head, (start, t)

    # Case 2 · a part after 1:00 → its prompt lists the guest's 1:00 position with its minute
    late = [r for r in readings if part_start(r) > 240]
    assert late
    for r in late:
        assert "Invitado (1:00): no subirá el IVA de la luz" in r["prompt"], part_start(r)

    # Case 3 · the guest says the opposite at 18:00 → a contradiction flag at 18:00 that points to 1:00
    assert contradiction(data) == [(1080.0, 60.0)], contradiction(data)


def test_long_conversation(tmp_path, monkeypatch):
    data, readings = analyse(tmp_path, monkeypatch, "conversation")

    # Case 4 · the parts → read in time order, the first one starts a session and every other one resumes it
    starts = [part_start(r) for r in readings]
    assert len(starts) > 5 and starts == sorted(starts), starts
    session = readings[0]["session_id"]
    assert session and not readings[0]["resume"], readings[0]
    assert all(r["resume"] == session and not r["session_id"] for r in readings[1:]), readings[1:]

    # Case 5 · each reading → sends only its own part: no line said before its part, and no list of positions
    for r, start in zip(readings, starts):
        for t, text in [*NUMBERED.items(), *STATEMENTS.items()]:
            if t < start:
                assert text not in r["prompt"], (start, t)
        assert "(1:00)" not in r["prompt"], start

    # Case 6 · the guest says the opposite at 18:00 → a contradiction flag at 18:00 that points to 1:00
    assert contradiction(data) == [(1080.0, 60.0)], contradiction(data)
    print("PASS S18 A2 · A part gets its context as a short window or as one long conversation")
