"""S22 A2 · The Anthropic API reads a video like Claude Code does

Story: The person sets `provider = "anthropic"` and puts `ANTHROPIC_API_KEY` in the helper's `.env`. An invented
two-part interview with one false figure gives the same flags as with Claude Code. The search reading carries the web
search tool and no other reading does. The second part continues the first part's conversation. Each usage line has
its dollar cost, such as 0.0246 for an Opus reading with 1,000 new, 2,000 cache-written, 3,000 cached and 500 output
tokens, and the flag file sums them.

Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices.
Run 1 uses Claude Code: a fake `claude` on PATH that answers by the JSON schema it gets. Run 2 uses the Anthropic API:
`config.toml` says `provider = "anthropic"` and points `[anthropic] base_url` at a fake Messages API on a free local
port. The fake answers by the schema in `output_config.format`, in the shape of tests/fakes/anthropic-api/messages.json
(1,000 / 2,000 / 3,000 / 500 tokens); it rejects a schema with `minimum`, `maximum` or `maxItems` with HTTP 400, as the
docs say the API does; it pauses the first search request with `pause_turn` after one search. Only the first part
reading finds the claim. The key is in the home's `.env`, not in the environment. A temporary helper home per run.
"""
import json
import os
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from fact_checker import server
from fact_checker.core.flags import Segment, Transcript

TEMPLATE = Path(__file__).parents[1] / "fakes" / "anthropic-api" / "messages.json"
HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE = "el paro bajó a la mitad en un año"
LINES = [
    (0, GUEST, f"Mire {FALSE} y eso lo cambia todo"),
    (40, HOST, "Muchas gracias por venir y buenas noches"),
]
KEY = "sk-ant-invented-key"
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
OPUS_READING = (1000 * 4 + 2000 * 5 + 3000 * 0.20 + 500 * 20) / 1e6  # 0.0246
SONNET_REQUEST = (1000 * 2 + 2000 * 2.50 + 3000 * 0.10 + 500 * 10) / 1e6  # 0.0123
SEARCH = 0.01  # one web search

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
schema = json.loads(opt("--json-schema"))
answers = json.load(open(os.environ["FAKE_ANSWERS"]))
key = next(k for k in answers if k in schema["properties"])
log = os.environ["FAKE_CLAUDE_LOG"]
earlier = [x.strip() for x in open(log)] if os.path.exists(log) else []
answer = answers[key] if key != "flags" or "flags" not in earlier else answers["nothing"]
open(log, "a").write(key + "\\n")
usage = {"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 5}
print(json.dumps({"type": "result", "is_error": False, "api_error_status": None, "result": "",
                  "structured_output": answer, "total_cost_usd": 0.01, "usage": usage}))
"""


def has_limits(schema) -> bool:
    if isinstance(schema, dict):
        return any(k in schema for k in ("minimum", "maximum", "maxItems")) or any(
            has_limits(v) for k, v in schema.items() if k != "properties") or any(
            has_limits(v) for v in schema.get("properties", {}).values())
    return isinstance(schema, list) and any(has_limits(v) for v in schema)


class FakeMessagesAPI:
    """A local Messages API that records each request and answers by its schema."""

    def __init__(self):
        self.requests, self.lock, self.paused = [], threading.Lock(), False
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with api.lock:
                    api.requests.append({"path": self.path, "key": self.headers.get("x-api-key"),
                                         "version": self.headers.get("anthropic-version"), "body": body})
                    code, reply = api.answer(body)
                raw = json.dumps(reply).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def answer(self, body):
        schema = body["output_config"]["format"]["schema"]
        if has_limits(schema):
            return 400, {"type": "error", "error": {"type": "invalid_request_error", "message": "unsupported schema"}}
        key = next(k for k in ANSWERS if k in schema["properties"])
        reply = json.loads(TEMPLATE.read_text()) | {"id": f"msg_{len(self.requests)}", "model": body["model"]}
        if key == "evidence" and not self.paused:
            self.paused = True
            reply["content"] = [
                {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": FALSE}},
                {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1",
                 "content": [{"type": "web_search_result", "url": INE["url"], "title": "Paro",
                              "encrypted_content": "(secret removed)", "page_age": None}]}]
            reply["stop_reason"] = "pause_turn"
            reply["usage"]["server_tool_use"]["web_search_requests"] = 1
            return 200, reply
        first_part = key == "flags" and not any(
            "flags" in r["body"]["output_config"]["format"]["schema"]["properties"] for r in self.requests[:-1])
        answer = ANSWERS[key] if key != "flags" or first_part else NOTHING
        reply["content"][-1]["text"] = json.dumps(answer, ensure_ascii=False)
        return 200, reply


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


def comparable(flags):
    return [{k: v for k, v in f.items() if k != "id"} for f in flags]


def test_anthropic_api(tmp_path, monkeypatch):
    for name in ("FACT_CHECK_PROVIDER", "ANTHROPIC_API_KEY", "HF_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}")
    (bin_dir / "claude").chmod((bin_dir / "claude").stat().st_mode | stat.S_IEXEC)
    (tmp_path / "answers.json").write_text(json.dumps(ANSWERS | {"nothing": NOTHING}))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_ANSWERS", str(tmp_path / "answers.json"))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(tmp_path / "claude.log"))

    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    server.Helper(claude_home)._run("anthro1", 0)
    with_claude = json.loads((claude_home / "videos" / "anthro1.json").read_text())

    api = FakeMessagesAPI()
    home = tmp_path / "api-home"
    home.mkdir()
    (home / "config.toml").write_text(f'provider = "anthropic"\nscreen = false\n[models]\n'
                                      f'search = "claude-sonnet-5-5"\n[anthropic]\nbase_url = "{api.url}"\n')
    (home / ".env").write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    (tmp_path / "claude.log").unlink()
    server.Helper(home)._run("anthro1", 0)
    data = json.loads((home / "videos" / "anthro1.json").read_text())
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    sent = api.requests
    kinds = [next(k for k in ANSWERS if k in r["body"]["output_config"]["format"]["schema"]["properties"]) for r in sent]

    # Case 1 · the Anthropic provider → no Claude Code reading, and the same flags as with Claude Code
    assert not (tmp_path / "claude.log").exists(), (tmp_path / "claude.log").read_text()
    assert data["status"] == "done", data
    assert with_claude["status"] == "done", with_claude
    assert [f["label"] for f in data["flags"] if f["type"] == "inaccuracy"] == ["false"], data["flags"]
    assert comparable(data["flags"]) == comparable(with_claude["flags"]), (data["flags"], with_claude["flags"])

    # Case 2 · every request → the key from .env, the API version, medium effort, the rules as a cached system prompt;
    # only a part reading (a conversation) caches its messages too
    assert {r["path"] for r in sent} == {"/v1/messages"}, sent
    assert {(r["key"], r["version"]) for r in sent} == {(KEY, "2026-10-21")}, {(r["key"], r["version"]) for r in sent}
    for r, kind in zip(sent, kinds):
        body = r["body"]
        assert body["output_config"]["effort"] == "medium", body["output_config"]
        assert body["system"][-1]["cache_control"] == {"type": "ephemeral"}, body["system"]
        assert body.get("cache_control") == ({"type": "ephemeral"} if kind == "flags" else None), (kind, body.get("cache_control"))
        assert body["model"] == ("claude-sonnet-5-5" if kinds[sent.index(r)] == "evidence" else "claude-opus-5-5"), body

    # Case 3 · the search → the web search tool, continued after pause_turn; no other reading has a tool
    searches = [r["body"] for r, k in zip(sent, kinds) if k == "evidence"]
    assert len(searches) == 2, kinds
    for body in searches:
        assert [(t["type"], t["name"], t["max_uses"]) for t in body["tools"]] == [
            ("web_search_20260209", "web_search", 5)], body["tools"]
    assert searches[1]["messages"][-1]["role"] == "assistant", searches[1]["messages"]
    assert searches[1]["messages"][-1]["content"][0]["type"] == "server_tool_use", searches[1]["messages"][-1]
    assert all("tools" not in r["body"] for r, k in zip(sent, kinds) if k != "evidence"), kinds

    # Case 4 · the second part → continues the first part's conversation, with the first answer sent back unchanged
    parts = [r["body"] for r, k in zip(sent, kinds) if k == "flags"]
    assert len(parts) == 2, kinds
    assert [m["role"] for m in parts[0]["messages"]] == ["user"], parts[0]["messages"]
    assert [m["role"] for m in parts[1]["messages"]] == ["user", "assistant", "user"], parts[1]["messages"]
    assert parts[1]["messages"][1]["content"][0] == json.loads(TEMPLATE.read_text())["content"][0], parts[1]["messages"][1]
    sessions = {u.get("session") for u in usage if u["step"] == "analyze_chunk"}
    assert len(sessions) == 1 and None not in sessions, usage

    # Case 5 · the usage log → each line has its model and its dollar cost; the flag file sums them
    assert sorted(u["step"] for u in usage) == ["analyze_chunk", "analyze_chunk", "fact_check", "judge", "search"], usage
    for u in usage:
        if u["step"] == "search":
            assert u["model"] == "claude-sonnet-5-5", u
            assert u["cost_usd"] == pytest.approx(2 * SONNET_REQUEST + SEARCH), u
        else:
            assert u["model"] == "claude-opus-5-5", u
            assert u["cost_usd"] == pytest.approx(OPUS_READING), u
            assert (u["input_tokens"], u["cache_creation_input_tokens"], u["cache_read_input_tokens"],
                    u["output_tokens"]) == (1000, 2000, 3000, 500), u
    assert data["cost_usd"] == pytest.approx(4 * OPUS_READING + 2 * SONNET_REQUEST + SEARCH), data["cost_usd"]
    api.httpd.shutdown()
    print("PASS S22 A2 · The Anthropic API reads a video like Claude Code does")
