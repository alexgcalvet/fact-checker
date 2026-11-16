"""The fakes that the S26 tests share: an invented English interview and its Spanish twin as yt-dlp caption
files, a fake `yt-dlp` that writes only the tracks it is asked for, a fake `claude` that logs every reading and answers by its schema, a failing `codex`, and a
Fact Check Tools API that records the language of each search (video_fakes.NoPublishedChecks).

The English video ("enview…") has an English original track (`en-orig`) and a machine-translated Spanish track (`es`)
that holds none of the English words. The Spanish video ("esview…") has only a Spanish original track (`es-orig`).
"""
import json
import sys
from pathlib import Path

from fact_checker import server
from video_fakes import NoPublishedChecks

ATTACK = {"en": "My rival is a liar", "es": "Mi rival es un mentiroso"}
FALSE = {"en": "unemployment fell by half in one year", "es": "el paro bajó a la mitad en un año"}
LINES = {
    "en-orig": [(0, "Welcome to the show tonight"), (3, f"{ATTACK['en']} and {FALSE['en']} thanks to us"),
                (20, "Thank you for coming tonight")],
    "es": [(0, "Bienvenidos al programa esta noche"), (3, "Mi rival miente y el desempleo cayó a la mitad gracias a"),
           (20, "Gracias por venir esta noche")],
    "es-orig": [(0, "Buenas noches y bienvenidos"), (3, f"{ATTACK['es']} y {FALSE['es']} gracias a nosotros"),
                (20, "Muchas gracias por venir")],
}
TRACKS = {"enview": ("en-orig", "es"), "esview": ("es-orig",)}
SOURCE = {"publisher": "Bureau of Labor Statistics", "url": "https://www.bls.gov/cps", "date": "2026-10-01"}

FAKE_YTDLP = """\
import os, shutil, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
video = args[-1].split("v=")[1]
asked = args[args.index("--sub-langs") + 1].split(",")
for name in os.listdir(os.environ["FAKE_CAPTIONS"]):
    if name.startswith(video + ".") and name.split(".")[1] in asked:
        shutil.copy(os.path.join(os.environ["FAKE_CAPTIONS"], name), out.replace("%(id)s", video) + name[len(video):])
print("20261110\\t30\\tInvented Channel\\tInvented interview")
"""

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else ""
schema = json.loads(opt("--json-schema"))["properties"]
prompt = opt("-p")
system = opt("--system-prompt")
lang = "es" if "Mi rival" in prompt or "el paro" in prompt else "en"
attack, false = json.loads(os.environ["FAKE_QUOTES"])
attack, false = attack[lang], false[lang]
source = json.loads(os.environ["FAKE_SOURCE"])
nothing = {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [], "claims": []}
answers = {
    "flags": nothing | {
        "flags": [{"quote": attack, "label": "ad_hominem", "closest": None, "speaker": "guest",
                   "reason": "An invented reason.", "confidence": 0.9}],
        "claims": [{"quote": false, "speaker": "guest", "queries": [false], "question": None, "kind": "fact",
                    "central": True, "repeats": None}]},
    "evidence": {"evidence": [{"quote": false, "findings": [source | {"says": "It fell from 12 % to 11 %."}]}]},
    "verdicts": {"verdicts": [
        {"quote": false, "verdict": "false", "reason": "An invented reason.", "confidence": 0.9, "sources": [source],
         "note": None, "controversy": None, "published": [], "earlier": None, "promise": None,
         "measures": [{"name": "Unemployment rate", "value": "11 %", "source": source["publisher"], "tier": 1,
                       "supports": False}]}]},
    "rulings": {"rulings": []},
    "speakers": {"speakers": []},
}
key = next(k for k in answers if k in schema)
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({"answer": key, "system": system, "prompt": prompt, "tools": opt("--tools")}) + "\\n")
answer = answers[key]
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "total_cost_usd": 0.0, "usage": {"input_tokens": 1, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 0, "output_tokens": 1}, "result": json.dumps(answer),
                  "structured_output": answer}))
"""

FAILING = "import sys\nsys.exit(1)\n"


def json3(lines: list[tuple[float, str]]) -> dict:
    """Word-by-word captions in YouTube's json3 shape: one event per line, a word every 0.5 s."""
    return {"events": [{"tStartMs": int(t * 1000), "segs": [{"utf8": (" " if i else "") + w, "tOffsetMs": i * 500}
                                                            for i, w in enumerate(text.split())]}
                       for t, text in lines]}


def setup(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """A helper home, the fake commands alone on PATH, the caption files; returns (home, reading log)."""
    bin_dir, captions, home = tmp_path / "bin", tmp_path / "captions", tmp_path / "home"
    for d in (bin_dir, captions, home):
        d.mkdir()
    for video, tracks in TRACKS.items():
        for track in tracks:
            (captions / f"{video}.{track}.json3").write_text(json.dumps(json3(LINES[track])))
    for name, code in {"yt-dlp": FAKE_YTDLP, "claude": FAKE_CLAUDE, "codex": FAILING}.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    log = tmp_path / "readings.jsonl"
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("FAKE_CAPTIONS", str(captions))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FAKE_QUOTES", json.dumps([ATTACK, FALSE]))
    monkeypatch.setenv("FAKE_SOURCE", json.dumps(SOURCE))
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    for name in ("HF_TOKEN", "FACT_CHECK_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)
    NoPublishedChecks.searches = []
    return home, log


def readings(log: Path) -> list[dict]:
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def text(reading: dict) -> str:
    """What the model reads: the system prompt and the message."""
    return f"{reading['system']}\n{reading['prompt']}"
