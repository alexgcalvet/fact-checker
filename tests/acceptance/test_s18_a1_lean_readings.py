"""S18 A1 · Every reading uses the five-minute cache and medium effort

Story: The helper analyses an invented video with a fake Claude Code that records how it is called. Every reading (part,
search, verdict, judge) asks for medium effort and the five-minute cache, and the search reading may use web search but
not open pages.

Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
gives one false figure that carries his argument. The helper runs as it does for the person (Helper._run), with a fake
YouTube that returns these captions, a fake Fact Check Tools API that finds nothing and no voices. The `claude` command
is a fake on PATH: it writes the arguments and the FORCE_PROMPT_CACHING_5M variable (the documented Claude Code setting
of the five-minute cache) of each reading to a log, and answers by the JSON schema it gets. A temporary helper home.
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
SECOND = LINES[0][2].split().index(FALSE.split()[0]) * 0.5
INE = {"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}

ANSWERS = {
    "flags": {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [],
              "claims": [{"quote": FALSE, "speaker": "Invitado", "queries": [FALSE], "question": None, "kind": "fact",
                          "central": True, "repeats": None}]},
    "evidence": {"evidence": [{"quote": FALSE, "findings": [INE | {"says": "La tasa de paro bajó del 12 % al 11 %."}]}]},
    "verdicts": {"verdicts": [{"quote": FALSE, "verdict": "false", "reason": "Bajó un punto.", "confidence": 0.9,
                               "sources": [INE], "note": None, "controversy": None, "published": [], "earlier": None,
                               "promise": None, "measures": [{"name": "Paro EPA", "value": "11 %", "source": "INE",
                                                              "tier": 1, "supports": False}]}]},
    "rulings": {"rulings": [{"id": f"false-{SECOND:.1f}", "verdict": "keep", "reason": "Se sostiene.",
                             "speaker": None}]},
}

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
schema = json.loads(args[args.index("--json-schema") + 1])
answers = json.load(open(os.environ["FAKE_CLAUDE_ANSWERS"]))
key = next(k for k in answers if k in schema["properties"])
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({"answer": key, "args": args, "cache_5m": os.environ.get("FORCE_PROMPT_CACHING_5M")}) + "\\n")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "num_turns": 1, "duration_ms": 1000, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 3, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0,
                            "output_tokens": 10}, "result": json.dumps(answers[key]),
                  "structured_output": answers[key]}))
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


def values(args, name):
    """The values of each `name` flag, as `--name value ...` up to the next option or as `--name=value`."""
    out = []
    for i, a in enumerate(args):
        if a == name:
            for v in args[i + 1:]:
                if v.startswith("-"):
                    break
                out += [x for x in v.split(",") if x]
        elif a.startswith(f"{name}="):
            out += [x for x in a.split("=", 1)[1].split(",") if x]
    return out


def test_lean_readings(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "answers.json").write_text(json.dumps(ANSWERS))
    log = tmp_path / "readings.jsonl"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_ANSWERS", str(tmp_path / "answers.json"))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("FORCE_PROMPT_CACHING_5M", raising=False)
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)
    home = tmp_path / "home"
    home.mkdir()

    server.Helper(home)._run("ligera", 0)
    data = json.loads((home / "videos" / "ligera.json").read_text())
    readings = [json.loads(x) for x in log.read_text().splitlines()]
    assert data["status"] == "done", data

    # Case 1 · the part, search, verdict and judge readings → each one runs
    assert sorted(r["answer"] for r in readings) == sorted(ANSWERS), [r["answer"] for r in readings]

    # Case 2 · every reading → asks for medium effort
    for r in readings:
        assert values(r["args"], "--effort") == ["medium"], (r["answer"], r["args"])

    # Case 3 · every reading → asks for the five-minute cache through FORCE_PROMPT_CACHING_5M=1
    for r in readings:
        assert r["cache_5m"] == "1", (r["answer"], r["cache_5m"])

    # Case 4 · the search reading → may use WebSearch and may not open pages (WebFetch is not offered, or is denied)
    search = next(r for r in readings if r["answer"] == "evidence")
    usable = set(values(search["args"], "--tools")) - set(values(search["args"], "--disallowedTools"))
    assert "WebSearch" in usable, search["args"]
    assert "WebFetch" not in usable, search["args"]
    print("PASS S18 A1 · Every reading uses the five-minute cache and medium effort")
