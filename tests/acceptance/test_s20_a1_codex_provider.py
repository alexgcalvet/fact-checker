"""S20 A1 · One setting routes every reading through Codex

Story: The person starts the helper with FACT_CHECK_PROVIDER=codex and analyses an invented 30-second interview with
one false figure. Every reading (part, search, verdict, judge) runs Codex, never Claude Code: the search with live
web search, the others with no web search, all by the account's default model (no -m: S22). The false figure shows
as "Dato falso", and the usage log names the model of each reading, "codex-default", with its tokens.

Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01
("Invitado") gives one false figure. The helper runs as it does for the person (Helper._run), with a fake YouTube that
returns these captions, a fake Fact Check Tools API that finds nothing and no voices. FACT_CHECK_PROVIDER is codex and
CODEX_BIN is unset. The `codex` command is a fake on PATH: it writes the model, the config overrides and the stdin
prompt of each reading to a log, and answers by the JSON schema file it gets, as the event stream of
tests/fakes/codex-cli/exec.jsonl with that answer as the agent message. The `claude` command is a fake on PATH that
logs every call and fails. A temporary helper home.
"""
import json
import os
import stat
import sys
from pathlib import Path

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript

EVENTS = Path(__file__).parents[1] / "fakes" / "codex-cli" / "exec.jsonl"
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
    "verdicts": {"verdicts": [
        {"quote": FALSE, "verdict": "false", "reason": "Razón inventada.", "confidence": 0.9, "sources": [INE],
         "note": None, "controversy": None, "published": [], "earlier": None, "promise": None,
         "measures": [{"name": "Paro EPA", "value": "11 %", "source": "INE", "tier": 1, "supports": False}]}]},
    "rulings": {"rulings": []},
}

FAKE_CODEX = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
config = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "-c")
config = {k: v.strip('"') for k, v in config.items()}
schema = json.load(open(opt("--output-schema")))
answers = json.load(open(os.environ["FAKE_CODEX_ANSWERS"]))
key = next(k for k in answers if k in schema["properties"])
with open(os.environ["FAKE_CODEX_LOG"], "a") as f:
    f.write(json.dumps({"answer": key, "model": opt("-m"), "web_search": config.get("web_search"),
                        "args": args, "prompt": sys.stdin.read()}) + "\\n")
for line in open(os.environ["FAKE_CODEX_EVENTS"]):
    event = json.loads(line)
    if event["type"] == "item.completed":
        event["item"]["text"] = json.dumps(answers[key])
    print(json.dumps(event))
"""

FAKE_CLAUDE = """\
import os, sys
open(os.environ["FAKE_CLAUDE_LOG"], "a").write("claude called\\n")
sys.exit(1)
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


def script(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n{body}")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def test_codex_provider(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script(bin_dir / "codex", FAKE_CODEX)
    script(bin_dir / "claude", FAKE_CLAUDE)
    (tmp_path / "answers.json").write_text(json.dumps(ANSWERS))
    log, claude_log = tmp_path / "readings.jsonl", tmp_path / "claude.log"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CODEX_ANSWERS", str(tmp_path / "answers.json"))
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log))
    monkeypatch.setenv("FAKE_CODEX_EVENTS", str(EVENTS))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(claude_log))
    monkeypatch.setenv("FACT_CHECK_PROVIDER", "codex")
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text("screen = false\n")  # S29: no screen readings here

    server.Helper(home)._run("dos", 0)
    data = json.loads((home / "videos" / "dos.json").read_text())
    readings = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []

    # Case 1 · the provider is codex → the part, search, verdict and judge readings all run Codex; Claude Code never runs
    assert not claude_log.exists(), claude_log.read_text()
    assert data["status"] == "done", data
    assert sorted({r["answer"] for r in readings}) == ["evidence", "flags", "rulings", "verdicts"], \
        [r["answer"] for r in readings]

    # Case 2 · the search → live web search; every other reading → web search disabled; no -m, the account's default
    for r in readings:
        want = (None, "live") if r["answer"] == "evidence" else (None, "disabled")
        assert (r["model"], r["web_search"]) == want, (r["answer"], r["model"], r["web_search"])
    assert FALSE in next(r["prompt"] for r in readings if r["answer"] == "evidence")

    # Case 3 · the false figure → one "Dato falso" flag at its second, with the source that the search found
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE)], found
    assert found[0]["sources"] == [INE], found[0]["sources"]

    # Case 4 · the usage log → one line per reading with the model "codex-default" and its tokens: input without the
    # cached part, the cached part as cache reads, the output; no dollar cost
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    assert sorted(u["step"] for u in usage) == ["analyze_chunk", "fact_check", "judge", "search"], usage
    for u in usage:
        assert u["model"] == "codex-default", u
        assert (u["input_tokens"], u["cache_read_input_tokens"], u["output_tokens"]) == (315, 24448, 122), u
        assert u["cost_usd"] == 0, u
    print("PASS S20 A1 · One setting routes every reading through Codex")
