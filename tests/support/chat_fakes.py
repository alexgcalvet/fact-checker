"""The fakes that the S23 tests share: an invented two-part interview, a Chat Completions server, a Tavily
search server, a Messages API server and failing `claude` and `codex` commands.

Each server runs on a free local port, records every request and answers by the schema it gets, in the shape of the
docs-built answers in tests/fakes/.
"""
import json
import os
import sys
from pathlib import Path

from fact_checker import server
from fact_checker.core import factcheck, judge, pipeline
from fact_checker.core.flags import Segment, Transcript
from fake_servers import FakeServer, NoPublishedChecks

FAKES = Path(__file__).parents[1] / "fakes"
HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
LINES = [
    (0, GUEST, f"Mire {FALSE} y eso lo cambia todo"),
    (40, HOST, "Muchas gracias por venir y buenas noches"),
]
SECOND = LINES[0][2].split().index(FALSE.split()[0]) * 0.5
INE = {"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}
RESULT = {"title": "Encuesta de Población Activa. Tercer trimestre", "url": INE["url"],
          "content": "La tasa de paro bajó del 12 % al 11 % en un año.", "score": 0.9, "published_date": INE["date"]}
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
}
# The schema of each kind of reading, to find it in the rules of a json_object request.
SCHEMAS = {"flags": pipeline.SCHEMA, "evidence": factcheck.SEARCH_SCHEMA, "verdicts": factcheck.SCHEMA,
           "rulings": judge.SCHEMA}

FAILING_CLI = """\
import os, sys
open(os.environ["FAKE_CLI_LOG"], "a").write(os.path.basename(sys.argv[0]) + " called\\n")
sys.exit(1)
"""


def fail_clis(tmp_path: Path, monkeypatch) -> Path:
    """Puts failing `claude` and `codex` commands first on PATH; each call is written to the returned log."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex"):
        (bin_dir / name).write_text(f"#!{sys.executable}\n{FAILING_CLI}")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLI_LOG", str(tmp_path / "cli.log"))
    monkeypatch.delenv("CODEX_BIN", raising=False)
    return tmp_path / "cli.log"


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


def fake_video(monkeypatch) -> None:
    """The invented interview, published fact-checks on (finding nothing), no voices."""
    for name in ("FACT_CHECK_PROVIDER", "HF_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY",
                 "CHAT_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)


def kind_of(body: dict) -> str:
    """The kind of a chat reading: from the schema of response_format, else from the schema in its first message."""
    fmt = body.get("response_format", {})
    if fmt.get("type") == "json_schema":
        return next(k for k in ANSWERS if k in fmt["json_schema"]["schema"]["properties"])
    rules = body["messages"][0]["content"]
    return next(k for k, schema in SCHEMAS.items() if json.dumps(schema) in rules)


class FakeChatAPI(FakeServer):
    """A Chat Completions API. With `reject_schema`, it answers a json_schema request with HTTP 400, as a server
    without structured outputs does. With `broken`, it answers that text to every part reading. Only the part
    reading whose PART holds the false figure finds the claim."""

    def __init__(self, reject_schema: bool = False, broken: str | None = None):
        super().__init__()
        self.reject_schema, self.broken, self.replies = reject_schema, broken, []
        self.base_url = f"http://127.0.0.1:{self.port}/v1"

    def answer(self, body):
        if self.reject_schema and body.get("response_format", {}).get("type") == "json_schema":
            return 400, {"error": {"message": "response_format json_schema is not supported by this model",
                                   "type": "invalid_request_error"}}
        kind = kind_of(body)
        first_part = kind == "flags" and FALSE in body["messages"][-1]["content"].split("PART:")[-1]
        text = self.broken if kind == "flags" and self.broken is not None else json.dumps(
            ANSWERS[kind] if kind != "flags" or first_part else NOTHING, ensure_ascii=False)
        reply = json.loads((FAKES / "chat-api" / "completion.json").read_text()) | {
            "id": f"chatcmpl-{len(self.requests)}", "model": body["model"]}
        if self.reject_schema:
            del reply["usage"]["prompt_tokens_details"]  # a local server may not report cached tokens
        reply["choices"][0]["message"]["content"] = text
        self.replies.append({"status": 200, "kind": kind, "content": text})
        return 200, reply

    def readings(self) -> list[tuple[dict, dict]]:
        """Each answered request with its kind: (request, reply record)."""
        answered = [r for r in self.requests
                    if not (self.reject_schema and r["body"].get("response_format", {}).get("type") == "json_schema")]
        return list(zip(answered, self.replies))


class FakeTavily(FakeServer):
    """The Tavily search API: one result, the INE figure, for every query."""

    def __init__(self):
        super().__init__()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def answer(self, body):
        reply = json.loads((FAKES / "tavily" / "search.json").read_text()) | {"query": body["query"]}
        reply["results"] = [RESULT]
        return 200, reply


class FakeMessagesAPI(FakeServer):
    """The Anthropic Messages API, answering by the schema of `output_config.format`."""

    def __init__(self):
        super().__init__()
        self.url = f"http://127.0.0.1:{self.port}"

    def answer(self, body):
        kind = next(k for k in ANSWERS if k in body["output_config"]["format"]["schema"]["properties"])
        reply = json.loads((FAKES / "anthropic-api" / "messages.json").read_text()) | {"model": body["model"]}
        reply["content"][-1]["text"] = json.dumps(ANSWERS[kind], ensure_ascii=False)
        return 200, reply
