"""S22 A3 · An OpenAI-compatible API set by its address reads a video

Story: The person sets `provider = "openai"`, `base_url = "https://api.x.ai/v1"`, `key_env = "XAI_API_KEY"` and the
Grok models in the settings file. The same invented interview gives the same flags. Each reading sends the key of
`XAI_API_KEY` to that address, asks for JSON by the schema, the search adds web search, and the second part continues
the first by its response id. A Grok model in the price table shows its cost; one that is not there shows a null cost.

Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices.
`config.toml` says `provider = "openai"`, the models `grok-4.7` (parts, verdict, judge) and `grok-4.7-fast` (search),
and `[openai] base_url` points at a fake Responses API on a free local port (`http://127.0.0.1:<port>/v1`) with
`key_env = "XAI_API_KEY"`. XAI_API_KEY is set in the environment and OPENAI_API_KEY is not. The fake answers by the
schema in `text.format`, in the shape of tests/fakes/openai-api/responses.json (4,000 input tokens of which 3,000
cached, 500 output), with a new response id each time and a `web_search_call` item before a search answer. Only the
first part reading finds the claim. The `claude` and `codex` commands are fakes on PATH that log every call and fail.
A temporary helper home.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript

TEMPLATE = Path(__file__).parents[1] / "fakes" / "openai-api" / "responses.json"
HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
LINES = [
    (0, GUEST, f"Mire {FALSE} y eso lo cambia todo"),
    (40, HOST, "Muchas gracias por venir y buenas noches"),
]
SECOND = LINES[0][2].split().index(FALSE.split()[0]) * 0.5
KEY = "xai-invented-key"
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
}


class FakeResponsesAPI:
    """A local Responses API that records each request and answers by its schema."""

    def __init__(self):
        self.requests, self.replies, self.lock = [], [], threading.Lock()
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with api.lock:
                    api.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                    reply = api.answer(body)
                    api.replies.append(reply)
                raw = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def answer(self, body):
        key = next(k for k in ANSWERS if k in body["text"]["format"]["schema"]["properties"])
        first_part = key == "flags" and not any(
            "flags" in r["body"]["text"]["format"]["schema"]["properties"] for r in self.requests[:-1])
        answer = ANSWERS[key] if key != "flags" or first_part else NOTHING
        reply = json.loads(TEMPLATE.read_text()) | {"id": f"resp_{len(self.requests)}", "model": body["model"]}
        reply["output"][-1]["content"][0]["text"] = json.dumps(answer, ensure_ascii=False)
        if key == "evidence":
            reply["output"].insert(0, {"type": "web_search_call", "id": "ws_1", "status": "completed",
                                       "action": {"type": "search", "query": FALSE}})
        return reply


FAKE_CLI = """\
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


class NoPublishedChecks:
    def __init__(self, key):
        pass

    def search(self, query, language):
        return []


def test_openai_compatible(tmp_path, monkeypatch):
    for name in ("FACT_CHECK_PROVIDER", "OPENAI_API_KEY", "HF_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XAI_API_KEY", KEY)
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex"):
        (bin_dir / name).write_text(f"#!{sys.executable}\n{FAKE_CLI}")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLI_LOG", str(tmp_path / "cli.log"))
    monkeypatch.delenv("CODEX_BIN", raising=False)
    api = FakeResponsesAPI()
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text(
        'provider = "openai"\nscreen = false\n'
        '[models]\nparts = "grok-4.7"\nverdict = "grok-4.7"\njudge = "grok-4.7"\nsearch = "grok-4.7-fast"\n'
        f'[openai]\nbase_url = "{api.base_url}"\nkey_env = "XAI_API_KEY"\n')

    server.Helper(home)._run("grok1", 0)
    data = json.loads((home / "videos" / "grok1.json").read_text())
    sent = api.requests

    # Case 1 · the OpenAI-compatible provider → no CLI reading; the one "Dato falso" flag that Claude Code gives for
    # the same answers (S20 A1, S22 A2), with its source
    assert not (tmp_path / "cli.log").exists(), (tmp_path / "cli.log").read_text()
    assert data["status"] == "done", data
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    kinds = [next(k for k in ANSWERS if k in r["body"]["text"]["format"]["schema"]["properties"]) for r in sent]
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE)], found
    assert found[0]["sources"] == [INE], found[0]["sources"]

    # Case 2 · every request → the address of base_url, the key of XAI_API_KEY, the rules as instructions, medium
    # effort and strict JSON by the schema; the model of its role
    assert sorted(kinds) == ["evidence", "flags", "flags", "rulings", "verdicts"], kinds
    assert {(r["path"], r["auth"]) for r in sent} == {("/v1/responses", f"Bearer {KEY}")}, {(r["path"], r["auth"]) for r in sent}
    for r, kind in zip(sent, kinds):
        body = r["body"]
        assert body["instructions"].startswith("You analyse Spanish conversations."), body["instructions"][:80]
        assert body["reasoning"] == {"effort": "medium"}, body["reasoning"]
        fmt = body["text"]["format"]
        assert (fmt["type"], fmt["strict"], bool(fmt.get("name"))) == ("json_schema", True, True), body["text"]
        assert body["model"] == ("grok-4.7-fast" if kind == "evidence" else "grok-4.7"), (kind, body["model"])

    # Case 3 · the search → the web_search tool; no other reading has a tool
    for r, kind in zip(sent, kinds):
        assert r["body"].get("tools", []) == ([{"type": "web_search"}] if kind == "evidence" else []), (kind, r["body"])

    # Case 4 · the second part → continues the first by its response id; the first starts a new conversation
    parts = [(r["body"], reply["id"]) for r, reply, k in zip(sent, api.replies, kinds) if k == "flags"]
    assert parts[0][0].get("previous_response_id") is None, parts[0][0]
    assert parts[1][0]["previous_response_id"] == parts[0][1], (parts[1][0].get("previous_response_id"), parts[0][1])
    assert parts[0][0]["store"] is True, parts[0][0].get("store")

    # Case 5 · the usage log → each line has its Grok model, its tokens (input without the cached part) and its cost: $0.0065 for grok-4.7, null for grok-4.7-fast
    assert sorted(u["step"] for u in usage) == ["analyze_chunk", "analyze_chunk", "fact_check", "judge", "search"], usage
    for u in usage:
        assert u["model"] == ("grok-4.7-fast" if u["step"] == "search" else "grok-4.7"), u
        assert (u["input_tokens"], u["cache_read_input_tokens"], u["output_tokens"]) == (1000, 3000, 500), u
        cost = u["cost_usd"] if u["step"] == "search" else round(u["cost_usd"], 6)
        assert cost == (None if u["step"] == "search" else 0.0065), u
    assert round(data["cost_usd"], 6) == 0.026, data["cost_usd"]
    api.httpd.shutdown()
    print("PASS S22 A3 · An OpenAI-compatible API set by its address reads a video")
