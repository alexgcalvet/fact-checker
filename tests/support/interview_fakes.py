"""The invented interview with one false figure, and the readers that answer it: a `claude` command, failing `claude`
and `codex` commands, a Messages API server, a Chat Completions server and a Tavily search server.

The interview comes in three cuts. TWO_PARTS is a 50-second one in two parts: the guest gives the false figure in the
first 30 seconds and the host thanks him at second 40. ONE_PART moves the thanks to second 20, into the first part. THREE_PARTS is a 2.5-minute one: the host's greeting (0:00), the
guest's false figure (0:30) and the guest's stance on taxes (2:30).

Every fake names the kind of a reading from its JSON schema: `screen` (the cheap screen), `flags` (a part), `evidence`
(the figure search), `verdicts` and `rulings` (the judge), and answers it with `answer`. A part reading finds the false
figure only when its PART holds it; the screen answers "no" only for the greeting part. Each server runs on a free local
port, records every request and answers in the shape of the docs-built answers in tests/fakes/.
"""
import json
import os
import sys
from pathlib import Path

from fact_checker.core import factcheck, judge, pipeline
from fake_servers import FakeServer

FAKES = Path(__file__).parents[1] / "fakes"
HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
TWO_PARTS = [(0, GUEST, f"Mire {FALSE} y eso lo cambia todo"), (40, HOST, "Muchas gracias por venir y buenas noches")]
SECOND = TWO_PARTS[0][2].split().index(FALSE.split()[0]) * 0.5
ONE_PART = [TWO_PARTS[0], (20, HOST, TWO_PARTS[1][2])]  # the thanks at second 20, in the first part
GREETING = "Buenas noches y bienvenido al programa muchas gracias por venir esta noche"
STANCE = "Yo no voy a subir los impuestos a las familias en esta legislatura"
THREE_PARTS = [(0, HOST, GREETING), (30, GUEST, f"Mire {FALSE} y eso lo cambia todo"), (150, GUEST, STANCE)]
SMALL_TALK = "bienvenido"  # the word by which the fake screen knows the greeting part

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
KINDS = ("read", "flags", "evidence", "verdicts", "rulings")  # a schema property that names each kind
# The schema of each kind of reading, to find it in the rules of a json_object request.
SCHEMAS = {"flags": pipeline.SCHEMA, "evidence": factcheck.SEARCH_SCHEMA, "verdicts": factcheck.SCHEMA,
           "rulings": judge.SCHEMA}


def kind(schema: dict) -> str:
    name = next(k for k in KINDS if k in schema["properties"])
    return "screen" if name == "read" else name


def kind_of(body: dict) -> str:
    """The kind of a chat reading: from the schema of response_format, else from the schema in its first message."""
    fmt = body.get("response_format", {})
    if fmt.get("type") == "json_schema":
        return kind(fmt["json_schema"]["schema"])
    rules = body["messages"][0]["content"]
    return next(k for k, schema in SCHEMAS.items() if json.dumps(schema) in rules)


def answer(name: str, text: str) -> dict:
    """The answer of a reading of kind `name` whose message is `text`: the screen skips the greeting; a part reading
    finds the false figure only when its PART holds it."""
    if name == "screen":
        return {"read": SMALL_TALK not in text, "reason": "Saludo." if SMALL_TALK in text else "Hay datos."}
    if name == "flags":
        return ANSWERS["flags"] if FALSE in text.split("PART:")[-1] else NOTHING
    return ANSWERS[name]


FAKE_CLAUDE = f"""\
import json, os, sys
sys.path[:0] = [{str(Path(__file__).parent)!r}, {str(Path(__file__).parents[2] / "src" / "helper")!r}]
from interview_fakes import answer, kind
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
                  "structured_output": {{"reason": "?"}} if odd else answer(kind(schema), text), "total_cost_usd": 0.01,
                  "usage": usage}}))
"""
FAILING_CLI = """\
import os, sys
open(os.environ["FAKE_CLI_LOG"], "a").write(os.path.basename(sys.argv[0]) + " called\\n")
sys.exit(1)
"""
# A `claude` that answers each reading with the entry of FAKE_ANSWERS named by a property of its schema, and logs the
# kind, model, tools, prompt, arguments and five-minute cache setting of each reading. With a "nothing" entry, it
# answers it to every part reading after the first.
ANSWERING_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
schema = json.loads(opt("--json-schema"))
answers = json.load(open(os.environ["FAKE_ANSWERS"]))
key = next(k for k in answers if k in schema["properties"])
log = os.environ["FAKE_CLAUDE_LOG"]
earlier = [json.loads(x)["answer"] for x in open(log)] if os.path.exists(log) else []
answer = answers["nothing"] if key == "flags" and "flags" in earlier and "nothing" in answers else answers[key]
with open(log, "a") as f:
    f.write(json.dumps({"answer": key, "model": opt("--model"), "tools": opt("--tools"), "prompt": opt("-p"),
                        "args": args, "cache_5m": os.environ.get("FORCE_PROMPT_CACHING_5M")}) + "\\n")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "num_turns": 1, "duration_ms": 1000, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 3, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0,
                            "output_tokens": 10}, "result": json.dumps(answer), "structured_output": answer}))
"""


def fake_clis(run: Path, monkeypatch, claude: bool = True, answers: dict | None = None) -> tuple[Path, Path]:
    """Puts a `claude` command and a failing `codex` command first on PATH. The `claude` is ANSWERING_CLAUDE with
    `answers`, else the fake that answers the interview, or a failing one when `claude` is false. Returns the log of
    the answering `claude` and the log of the failing commands."""
    bin_dir = run / "bin"
    bin_dir.mkdir(parents=True)
    body = ANSWERING_CLAUDE if answers is not None else FAKE_CLAUDE if claude else FAILING_CLI
    for name, code in (("claude", body), ("codex", FAILING_CLI)):
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    if answers is not None:
        (run / "answers.json").write_text(json.dumps(answers))
        monkeypatch.setenv("FAKE_ANSWERS", str(run / "answers.json"))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(run / "claude.jsonl"))
    monkeypatch.setenv("FAKE_CLI_LOG", str(run / "cli.log"))
    monkeypatch.delenv("CODEX_BIN", raising=False)
    return run / "claude.jsonl", run / "cli.log"


def fail_clis(tmp_path: Path, monkeypatch) -> Path:
    """Puts failing `claude` and `codex` commands first on PATH; each call is written to the returned log."""
    return fake_clis(tmp_path, monkeypatch, claude=False)[1]


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def has_limits(schema) -> bool:
    if isinstance(schema, dict):
        return any(k in schema for k in ("minimum", "maximum", "maxItems")) or any(
            has_limits(v) for k, v in schema.items() if k != "properties") or any(
            has_limits(v) for v in schema.get("properties", {}).values())
    return isinstance(schema, list) and any(has_limits(v) for v in schema)


class FakeMessagesAPI(FakeServer):
    """The Anthropic Messages API, answering by the schema of `output_config.format`. It rejects a schema with
    `minimum`, `maximum` or `maxItems` with HTTP 400, as the docs say the API does. With `pause_search`, it pauses the
    first search request with `pause_turn` after one search."""

    def __init__(self, pause_search: bool = False):
        super().__init__()
        self.url, self.pause_search = f"http://127.0.0.1:{self.port}", pause_search

    def answer(self, body):
        schema = body["output_config"]["format"]["schema"]
        if has_limits(schema):
            return 400, {"type": "error", "error": {"type": "invalid_request_error", "message": "unsupported schema"}}
        name = kind(schema)
        reply = json.loads((FAKES / "anthropic-api" / "messages.json").read_text()) | {
            "id": f"msg_{len(self.requests)}", "model": body["model"]}
        if name == "evidence" and self.pause_search:
            self.pause_search = False
            reply["content"] = [
                {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": FALSE}},
                {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1",
                 "content": [{"type": "web_search_result", "url": INE["url"], "title": "Paro",
                              "encrypted_content": "(secret removed)", "page_age": None}]}]
            reply["stop_reason"] = "pause_turn"
            reply["usage"]["server_tool_use"]["web_search_requests"] = 1
            return 200, reply
        reply["content"][-1]["text"] = json.dumps(answer(name, body["messages"][-1]["content"]), ensure_ascii=False)
        return 200, reply

    def kinds(self) -> list[tuple[str, dict]]:
        return [(kind(r["body"]["output_config"]["format"]["schema"]), r["body"]) for r in self.requests]


class FakeChatAPI(FakeServer):
    """A Chat Completions API, answering by the schema of `response_format`. With `reject_schema`, it answers a
    json_schema request with HTTP 400, as a server without structured outputs does, and a json_object request by the
    schema in its rules. With `broken`, it answers that text to every part reading."""

    def __init__(self, reject_schema: bool = False, broken: str | None = None):
        super().__init__()
        self.reject_schema, self.broken, self.replies = reject_schema, broken, []
        self.base_url = f"http://127.0.0.1:{self.port}/v1"

    def answer(self, body):
        if self.reject_schema and body.get("response_format", {}).get("type") == "json_schema":
            return 400, {"error": {"message": "response_format json_schema is not supported by this model",
                                   "type": "invalid_request_error"}}
        name = kind_of(body)
        text = self.broken if name == "flags" and self.broken is not None else json.dumps(
            answer(name, body["messages"][-1]["content"]), ensure_ascii=False)
        reply = json.loads((FAKES / "chat-api" / "completion.json").read_text()) | {
            "id": f"chatcmpl-{len(self.requests)}", "model": body["model"]}
        if self.reject_schema:
            del reply["usage"]["prompt_tokens_details"]  # a local server may not report cached tokens
        reply["choices"][0]["message"]["content"] = text
        self.replies.append({"status": 200, "kind": name, "content": text})
        return 200, reply

    def readings(self) -> list[tuple[dict, dict]]:
        """Each answered request with its kind: (request, reply record)."""
        answered = [r for r in self.requests
                    if not (self.reject_schema and r["body"].get("response_format", {}).get("type") == "json_schema")]
        return list(zip(answered, self.replies))

    def kinds(self) -> list[tuple[str, dict]]:
        return [(kind_of(r["body"]), r["body"]) for r in self.requests]


class FakeTavily(FakeServer):
    """The Tavily search API: one result, the INE figure, for every query."""

    def __init__(self):
        super().__init__()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def answer(self, body):
        reply = json.loads((FAKES / "tavily" / "search.json").read_text()) | {"query": body["query"]}
        reply["results"] = [RESULT]
        return 200, reply
