"""S22 A1 · The settings file picks the provider and a model per step

Story: The person writes `parts = "sonnet"` and `verdict = "opus"` under `[models]` in the settings file and analyses
an invented interview with one false figure. The usage log shows each part read by `sonnet`, each verdict by `opus`,
the search by `haiku` and the judge by `opus`. With no settings file, the same video shows today's models: `opus` for
parts, verdicts and judge, `haiku` for the search and the screen (S29).
Edge case: WHEN the file says `provider = "codex"` and `FACT_CHECK_PROVIDER=claude` is set THEN every reading runs
Claude Code.

Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
does for the person (Helper._run), with a fake YouTube that returns these captions, a fake Fact Check Tools API that
finds nothing and no voices. The `claude` command is a fake on PATH: it writes the --model of each reading to a log and
answers by the JSON schema it gets; only the first part reading finds the claim. The `codex` command is a fake on PATH
that logs every call and fails. A temporary helper home per run, with `config.toml` written by the case.
"""
import json
import os
import stat
import sys
from pathlib import Path

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
LINES = [
    (0, GUEST, f"Mire {FALSE} y eso lo cambia todo"),
    (40, HOST, "Muchas gracias por venir y buenas noches"),
]
INE = {"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}
NOTHING = {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [], "claims": []}
ANSWERS = {
    "flags": NOTHING | {"claims": [{"quote": FALSE, "speaker": "Invitado", "queries": [FALSE], "question": None,
                                    "kind": "fact", "central": True, "repeats": None}]},
    "evidence": {"evidence": [{"quote": FALSE, "findings": [INE | {"says": "La tasa de paro bajó del 12 % al 11 %."}]}]},
    "verdicts": {"verdicts": [
        {"quote": FALSE, "verdict": "false", "reason": "Razón inventada.", "confidence": 0.9, "sources": [INE],
         "note": None, "controversy": None, "published": [], "earlier": None, "promise": None,
         "measures": [{"name": "Paro EPA", "value": "11 %", "source": "INE", "tier": 1, "supports": False}]}]},
    "rulings": {"rulings": []},
    "read": {"read": True, "reason": "Hay un dato."},
}

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
schema = json.loads(opt("--json-schema"))
answers = json.load(open(os.environ["FAKE_ANSWERS"]))
key = next(k for k in answers if k in schema["properties"])
log = os.environ["FAKE_CLAUDE_LOG"]
earlier = [json.loads(x)["answer"] for x in open(log)] if os.path.exists(log) else []
answer = answers[key] if key != "flags" or "flags" not in earlier else answers["nothing"]
with open(log, "a") as f:
    f.write(json.dumps({"answer": key, "model": opt("--model")}) + "\\n")
usage = {"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 5}
print(json.dumps({"type": "result", "is_error": False, "api_error_status": None, "result": "",
                  "structured_output": answer, "total_cost_usd": 0.01, "usage": usage}))
"""

FAKE_CODEX = """\
import os, sys
open(os.environ["FAKE_CODEX_LOG"], "a").write("codex called\\n")
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


def analyse(tmp_path, monkeypatch, name: str, config: str | None):
    """Runs the helper on the invented interview in a new home; returns the flag file, the usage log and the fake
    Claude's log."""
    run = tmp_path / name
    bin_dir, home = run / "bin", run / "home"
    bin_dir.mkdir(parents=True)
    home.mkdir()
    script(bin_dir / "claude", FAKE_CLAUDE)
    script(bin_dir / "codex", FAKE_CODEX)
    (run / "answers.json").write_text(json.dumps(ANSWERS | {"nothing": NOTHING}))
    if config is not None:
        (home / "config.toml").write_text(config)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_ANSWERS", str(run / "answers.json"))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(run / "claude.jsonl"))
    monkeypatch.setenv("FAKE_CODEX_LOG", str(run / "codex.log"))
    server.Helper(home)._run("roles1", 0)
    data = json.loads((home / "videos" / "roles1.json").read_text())
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    readings = [json.loads(x) for x in (run / "claude.jsonl").read_text().splitlines()]
    return data, usage, readings, run / "codex.log"


def models_by_step(usage) -> dict:
    return {step: sorted({u["model"] for u in usage if u["step"] == step}) for step in sorted({u["step"] for u in usage})}


def test_models_per_role(tmp_path, monkeypatch):
    monkeypatch.delenv("FACT_CHECK_PROVIDER", raising=False)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)

    # Case 1 · parts = sonnet and verdict = opus in the settings file → each step runs its own model; the missing
    # roles take the provider's defaults
    data, usage, readings, _ = analyse(tmp_path, monkeypatch, "configured",
                                       '[models]\nparts = "sonnet"\nverdict = "opus"\n')
    assert data["status"] == "done", data
    assert models_by_step(usage) == {"analyze_chunk": ["sonnet"], "fact_check": ["opus"], "judge": ["opus"],
                                     "search": ["haiku"], "screen": ["haiku"]}, usage
    assert len([u for u in usage if u["step"] == "analyze_chunk"]) == 2, usage
    by_answer = {r["answer"]: r["model"] for r in readings}
    assert by_answer == {"flags": "sonnet", "verdicts": "opus", "evidence": "haiku", "rulings": "opus",
                         "read": "haiku"}, readings
    assert [(f["label"], f["quote"]) for f in data["flags"] if f["type"] == "inaccuracy"] == [("false", FALSE)], data

    # Case 2 · no settings file → today's models: opus reads, gives verdicts and judges; haiku searches and screens
    data, usage, readings, _ = analyse(tmp_path, monkeypatch, "default", None)
    assert data["status"] == "done", data
    assert models_by_step(usage) == {"analyze_chunk": ["opus"], "fact_check": ["opus"], "judge": ["opus"],
                                     "search": ["haiku"], "screen": ["haiku"]}, usage

    # Case 3 · the file says codex and FACT_CHECK_PROVIDER=claude is set → every reading runs Claude Code
    monkeypatch.setenv("FACT_CHECK_PROVIDER", "claude")
    data, usage, readings, codex_log = analyse(tmp_path, monkeypatch, "override",
                                               'provider = "codex"\n[models]\nparts = "sonnet"\n')
    assert not codex_log.exists(), codex_log.read_text()
    assert data["status"] == "done", data
    assert sorted({r["answer"] for r in readings}) == ["evidence", "flags", "read", "rulings", "verdicts"], readings
    assert models_by_step(usage)["analyze_chunk"] == ["sonnet"], usage
    print("PASS S22 A1 · The settings file picks the provider and a model per step")
