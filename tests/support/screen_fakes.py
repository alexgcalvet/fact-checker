"""The fakes that the S29 tests share: an invented three-part interview (a greeting, a false figure, a
stated position), a `claude` command, a Messages API server and a Chat Completions server that answer every kind of
reading, and a failing `codex` command.

Every fake names the kind of a reading from its JSON schema: `screen` (the cheap screen), `flags` (a part), `evidence`
(the figure search), `verdicts` and `rulings` (the judge). The screen answers "no" only for the greeting part.
"""
import json
import os
import sys
from pathlib import Path

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript
from fake_servers import FakeServer, NoPublishedChecks

FAKES = Path(__file__).parents[1] / "fakes"
HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
GREETING = "Buenas noches y bienvenido al programa muchas gracias por venir esta noche"
FALSE = "el paro bajó a la mitad en un año"
STANCE = "Yo no voy a subir los impuestos a las familias en esta legislatura"
LINES = [(0, HOST, GREETING), (30, GUEST, f"Mire {FALSE} y eso lo cambia todo"), (150, GUEST, STANCE)]
SMALL_TALK = "bienvenido"  # the word by which the fake screen knows the greeting part
INE = {"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}
NOTHING = {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [], "claims": []}
CLAIM = {"quote": FALSE, "speaker": "Invitado", "queries": [FALSE], "question": None, "kind": "fact", "central": True,
         "repeats": None}
ANSWERS = {
    "evidence": {"evidence": [{"quote": FALSE, "findings": [INE | {"says": "La tasa de paro bajó del 12 % al 11 %."}]}]},
    "verdicts": {"verdicts": [
        {"quote": FALSE, "verdict": "false", "reason": "Razón inventada.", "confidence": 0.9, "sources": [INE],
         "note": None, "controversy": None, "published": [], "earlier": None, "promise": None,
         "measures": [{"name": "Paro EPA", "value": "11 %", "source": "INE", "tier": 1, "supports": False}]}]},
    "rulings": {"rulings": []},
}
KINDS = ("read", "flags", "evidence", "verdicts", "rulings")  # a schema property that names each kind


def kind(schema: dict) -> str:
    name = next(k for k in KINDS if k in schema["properties"])
    return "screen" if name == "read" else name


def answer(schema: dict, text: str) -> dict:
    """The answer of a reading of this kind whose message is `text`: the screen skips the greeting; a part reading
    finds the false figure only when its PART holds it."""
    name = kind(schema)
    if name == "screen":
        return {"read": SMALL_TALK not in text, "reason": "Saludo." if SMALL_TALK in text else "Hay datos."}
    if name == "flags":
        return NOTHING | {"claims": [CLAIM]} if FALSE in text.split("PART:")[-1] else NOTHING
    return ANSWERS[name]


FAKE_CLAUDE = f"""\
import json, os, sys
sys.path[:0] = [{str(Path(__file__).parent)!r}, {str(Path(__file__).parents[2] / "src" / "helper")!r}]
from screen_fakes import answer, kind
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
schema, text = json.loads(opt("--json-schema")), args[1]
if kind(schema) == "screen" and os.environ.get("FAKE_SCREEN_FAILS"):
    sys.exit(1)
odd = kind(schema) == "screen" and os.environ.get("FAKE_SCREEN_ODD")
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({{"kind": kind(schema), "model": opt("--model"), "tools": opt("--tools"), "text": text}}) + "\\n")
usage = {{"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 5}}
print(json.dumps({{"type": "result", "is_error": False, "api_error_status": None, "result": "",
                  "structured_output": {{"reason": "?"}} if odd else answer(schema, text), "total_cost_usd": 0.01, "usage": usage}}))
"""
FAILING_CLI = """\
import os, sys
open(os.environ["FAKE_CLI_LOG"], "a").write(os.path.basename(sys.argv[0]) + " called\\n")
sys.exit(1)
"""


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


def fake_video(monkeypatch) -> None:
    """The invented interview, published fact-checks on (finding nothing), no voices, no provider override."""
    for name in ("FACT_CHECK_PROVIDER", "HF_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY",
                 "CHAT_API_KEY", "CODEX_BIN", "FAKE_SCREEN_FAILS", "FAKE_SCREEN_ODD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)


def fake_clis(run: Path, monkeypatch, claude: bool = True) -> tuple[Path, Path]:
    """Puts a `claude` command (the answering fake, or a failing one) and a failing `codex` command first on PATH.
    Returns the fake Claude's log and the failing commands' log."""
    bin_dir = run / "bin"
    bin_dir.mkdir(parents=True)
    for name, body in (("claude", FAKE_CLAUDE if claude else FAILING_CLI), ("codex", FAILING_CLI)):
        (bin_dir / name).write_text(f"#!{sys.executable}\n{body}")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(run / "claude.jsonl"))
    monkeypatch.setenv("FAKE_CLI_LOG", str(run / "cli.log"))
    return run / "claude.jsonl", run / "cli.log"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


class FakeMessagesAPI(FakeServer):
    """The Anthropic Messages API, answering by the schema of `output_config.format`."""

    def __init__(self):
        super().__init__()
        self.url = f"http://127.0.0.1:{self.port}"

    def answer(self, body):
        schema = body["output_config"]["format"]["schema"]
        out = json.loads((FAKES / "anthropic-api" / "messages.json").read_text()) | {"model": body["model"]}
        out["content"][-1]["text"] = json.dumps(answer(schema, body["messages"][-1]["content"]), ensure_ascii=False)
        return 200, out

    def kinds(self) -> list[tuple[str, dict]]:
        return [(kind(r["body"]["output_config"]["format"]["schema"]), r["body"]) for r in self.requests]


class FakeChatAPI(FakeServer):
    """A Chat Completions API, answering by the schema of `response_format`."""

    def __init__(self):
        super().__init__()
        self.base_url = f"http://127.0.0.1:{self.port}/v1"

    def answer(self, body):
        schema = body["response_format"]["json_schema"]["schema"]
        out = json.loads((FAKES / "chat-api" / "completion.json").read_text()) | {"model": body["model"]}
        out["choices"][0]["message"]["content"] = json.dumps(answer(schema, body["messages"][-1]["content"]),
                                                             ensure_ascii=False)
        return 200, out

    def kinds(self) -> list[tuple[str, dict]]:
        return [(kind(r["body"]["response_format"]["json_schema"]["schema"]), r["body"]) for r in self.requests]
