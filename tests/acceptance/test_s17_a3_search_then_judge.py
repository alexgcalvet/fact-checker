"""S17 A3 · A cheaper model searches, Opus judges

Story: For a part with two central figures, one reading by Haiku (S29) with web search returns the evidence with its
sources, and one reading by Opus with no tools turns that evidence into verdicts. A false figure still shows as
"Dato falso" with the same sources.

Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
gives two figures that carry his argument: one false, one right. The helper runs as it does for the person
(Helper._run), with a fake YouTube that returns these captions, a fake Fact Check Tools API that finds nothing and no
voices. The `claude` command is a fake on PATH: it writes the model, tools and prompt of each reading to a log, and
answers by the JSON schema it gets. The search answer gives one dated source for each figure. The verdict answer calls
the first figure false, citing the search's source and one more link that the search never found, and the second
figure true. A temporary helper home.
"""
import json
import os
import stat
import sys

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
TRUE = "la inflación cerró el año en el dos por ciento"
LINES = [
    (0, GUEST, f"Mire {FALSE} y además {TRUE} y eso lo cambia todo"),
    (20, HOST, "Muchas gracias por venir y buenas noches"),
]
WORDS = LINES[0][2].split()
SECOND = WORDS.index(FALSE.split()[0]) * 0.5
INE = {"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}
EUROSTAT = {"publisher": "Eurostat", "url": "https://ec.europa.eu/eurostat/ipc", "date": "2026-10-15"}
UNSEEN = {"publisher": "Un blog", "url": "https://example.org/inventado", "date": "2026-09-01"}


def verdict(quote, value, sources, measures):
    return {"quote": quote, "verdict": value, "reason": "Razón inventada.", "confidence": 0.9, "sources": sources,
            "note": None, "controversy": None, "published": [], "earlier": None, "promise": None, "measures": measures}


ANSWERS = {
    "flags": {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [],
              "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "fact",
                          "central": True, "repeats": None} for q in (FALSE, TRUE)]},
    "evidence": {"evidence": [
        {"quote": FALSE, "findings": [INE | {"says": "La tasa de paro bajó del 12 % al 11 %."}]},
        {"quote": TRUE, "findings": [EUROSTAT | {"says": "El IPC armonizado cerró en el 2,0 %."}]}]},
    "verdicts": {"verdicts": [
        verdict(FALSE, "false", [INE, UNSEEN],
                [{"name": "Paro EPA", "value": "11 %", "source": "INE", "tier": 1, "supports": False}]),
        verdict(TRUE, "true", [EUROSTAT],
                [{"name": "IPCA", "value": "2,0 %", "source": "Eurostat", "tier": 1, "supports": True}])]},
    "rulings": {"rulings": []},
}

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
schema = json.loads(opt("--json-schema"))
answers = json.load(open(os.environ["FAKE_CLAUDE_ANSWERS"]))
key = next(k for k in answers if k in schema["properties"])
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({"answer": key, "model": opt("--model"), "tools": opt("--tools"), "prompt": opt("-p")}) + "\\n")
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


def test_search_then_judge(tmp_path, monkeypatch):
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
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)
    home = tmp_path / "home"
    home.mkdir()

    server.Helper(home)._run("dos", 0)
    data = json.loads((home / "videos" / "dos.json").read_text())
    readings = [json.loads(x) for x in log.read_text().splitlines()]
    assert data["status"] == "done", data

    # Case 1 · a part with two central figures → one search reading, by Haiku with web search, for both figures
    search = [r for r in readings if r["answer"] == "evidence"]
    assert len(search) == 1, [r["answer"] for r in readings]
    assert search[0]["model"] == "haiku", search[0]["model"]
    assert set(search[0]["tools"].split(",")) == {"WebSearch", "WebFetch"}, search[0]["tools"]
    assert FALSE in search[0]["prompt"] and TRUE in search[0]["prompt"]

    # Case 2 · the evidence → one verdict reading, by Opus with no tools, that gets both figures and the sources
    # that the search found
    checks = [r for r in readings if r["answer"] == "verdicts"]
    assert len(checks) == 1, [r["answer"] for r in readings]
    assert checks[0]["model"] == "opus", checks[0]["model"]
    assert checks[0]["tools"] == "", checks[0]["tools"]
    for text in (FALSE, TRUE, INE["url"], EUROSTAT["url"]):
        assert text in checks[0]["prompt"], text

    # Case 3 · the false figure → one "Dato falso" flag at its second, with the source that the search found and
    # not the link that it never found; the right figure → no flag
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE)], found
    assert found[0]["sources"] == [INE], found[0]["sources"]
    print("PASS S17 A3 · A cheaper model searches, Opus judges")
