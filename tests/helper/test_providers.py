"""The providers: Claude Code, Codex, the Anthropic, OpenAI-compatible and chat APIs, and a provider per role."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

from fact_checker import server
from fact_checker.adapters import llm_claude_cli
from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fake_servers import FakeServer
from interview_fakes import (
    ANSWERS,
    fail_clis,
    fake_clis,
    FakeChatAPI,
    FakeMessagesAPI,
    FakeTavily,
    FALSE,
    INE,
    jsonl,
    kind as schema_kind,
    kind_of,
    NOTHING,
    ONE_PART,
    RESULT,
    SCHEMAS,
    SECOND,
    THREE_PARTS,
    TWO_PARTS,
)
from video_fakes import fake_video


# S18 A1 · Every reading uses the five-minute cache and medium effort
#
# Story: The helper analyses an invented video with a fake Claude Code that records how it is called. Every reading (part,
# search, verdict, judge) asks for medium effort and the five-minute cache, and the search reading may use web search but
# not open pages.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
# gives one false figure that carries his argument. The helper runs as it does for the person (Helper._run), with a fake
# YouTube that returns these captions, a fake Fact Check Tools API that finds nothing and no voices. The `claude` command
# is a fake on PATH: it writes the arguments and the FORCE_PROMPT_CACHING_5M variable (the documented Claude Code setting
# of the five-minute cache) of each reading to a log, and answers by the JSON schema it gets. A temporary helper home.

LEAN_ANSWERS = {
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
    fake_video(monkeypatch, ONE_PART)
    monkeypatch.delenv("FORCE_PROMPT_CACHING_5M", raising=False)
    log, _ = fake_clis(tmp_path, monkeypatch, answers=LEAN_ANSWERS)
    home = tmp_path / "home"
    home.mkdir()

    server.Helper(home)._run("ligera", 0)
    data = json.loads((home / "videos" / "ligera.json").read_text())
    readings = [json.loads(x) for x in log.read_text().splitlines()]
    assert data["status"] == "done", data

    # Case 1 · the part, search, verdict and judge readings → each one runs
    assert sorted(r["answer"] for r in readings) == sorted(LEAN_ANSWERS), [r["answer"] for r in readings]

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


# S20 A1 · One setting routes every reading through Codex
#
# Story: The person starts the helper with FACT_CHECK_PROVIDER=codex and analyses an invented 30-second interview with
# one false figure. Every reading (part, search, verdict, judge) runs Codex, never Claude Code: the search with live
# web search, the others with no web search, all by the account's default model (no -m: S22). The false figure shows
# as "Dato falso", and the usage log names the model of each reading, "codex-default", with its tokens.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01
# ("Invitado") gives one false figure. The helper runs as it does for the person (Helper._run), with a fake YouTube that
# returns these captions, a fake Fact Check Tools API that finds nothing and no voices. FACT_CHECK_PROVIDER is codex and
# CODEX_BIN is unset. The `codex` command is a fake on PATH: it writes the model, the config overrides and the stdin
# prompt of each reading to a log, and answers by the JSON schema file it gets, as the event stream of
# tests/fakes/codex-cli/exec.jsonl with that answer as the agent message. The `claude` command is a fake on PATH that
# logs every call and fails. A temporary helper home.

EVENTS = Path(__file__).parents[1] / "fakes" / "codex-cli" / "exec.jsonl"

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

def script(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n{body}")
    path.chmod(0o755)


def test_codex_provider(tmp_path, monkeypatch):
    fake_video(monkeypatch, ONE_PART)
    claude_log = fail_clis(tmp_path, monkeypatch)
    script(tmp_path / "bin" / "codex", FAKE_CODEX)
    (tmp_path / "answers.json").write_text(json.dumps(ANSWERS))
    log = tmp_path / "readings.jsonl"
    monkeypatch.setenv("FAKE_CODEX_ANSWERS", str(tmp_path / "answers.json"))
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log))
    monkeypatch.setenv("FAKE_CODEX_EVENTS", str(EVENTS))
    monkeypatch.setenv("FACT_CHECK_PROVIDER", "codex")
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


# S22 A1 · The settings file picks the provider and a model per step
#
# Story: The person writes `parts = "sonnet"` and `verdict = "opus"` under `[models]` in the settings file and analyses
# an invented interview with one false figure. The usage log shows each part read by `sonnet`, each verdict by `opus`,
# the search by `haiku` and the judge by `opus`. With no settings file, the same video shows today's models: `opus` for
# parts, verdicts and judge, `haiku` for the search and the screen (S29).
# Edge case: WHEN the file says `provider = "codex"` and `FACT_CHECK_PROVIDER=claude` is set THEN every reading runs
# Claude Code.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
# ("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
# does for the person (Helper._run), with a fake YouTube that returns these captions, a fake Fact Check Tools API that
# finds nothing and no voices. The `claude` command is a fake on PATH: it writes the --model of each reading to a log and
# answers by the JSON schema it gets; only the first part reading finds the claim. The `codex` command is a fake on PATH
# that logs every call and fails. A temporary helper home per run, with `config.toml` written by the case.

READ = {"read": True, "reason": "Hay un dato."}


def analyse(tmp_path, monkeypatch, name: str, config: str | None):
    """Runs the helper on the invented interview in a new home; returns the flag file, the usage log and the fake
    Claude's log."""
    run = tmp_path / name
    home = run / "home"
    home.mkdir(parents=True)
    claude_log, codex_log = fake_clis(run, monkeypatch, answers=ANSWERS | {"read": READ, "nothing": NOTHING})
    if config is not None:
        (home / "config.toml").write_text(config)
    server.Helper(home)._run("roles1", 0)
    data = json.loads((home / "videos" / "roles1.json").read_text())
    usage = jsonl(home / "usage.log")
    return data, usage, jsonl(claude_log), codex_log


def models_by_step(usage) -> dict:
    return {step: sorted({u["model"] for u in usage if u["step"] == step}) for step in sorted({u["step"] for u in usage})}


def test_models_per_role(tmp_path, monkeypatch):
    fake_video(monkeypatch, TWO_PARTS)

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


# S22 A2 · The Anthropic API reads a video like Claude Code does
#
# Story: The person sets `provider = "anthropic"` and puts `ANTHROPIC_API_KEY` in the helper's `.env`. An invented
# two-part interview with one false figure gives the same flags as with Claude Code. The search reading carries the web
# search tool and no other reading does. The second part continues the first part's conversation. Each usage line has
# its dollar cost, such as 0.0246 for an Opus reading with 1,000 new, 2,000 cache-written, 3,000 cached and 500 output
# tokens, and the flag file sums them.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
# ("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
# does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices.
# Run 1 uses Claude Code: a fake `claude` on PATH that answers by the JSON schema it gets. Run 2 uses the Anthropic API:
# `config.toml` says `provider = "anthropic"` and points `[anthropic] base_url` at a fake Messages API on a free local
# port. The fake answers by the schema in `output_config.format`, in the shape of tests/fakes/anthropic-api/messages.json
# (1,000 / 2,000 / 3,000 / 500 tokens); it rejects a schema with `minimum`, `maximum` or `maxItems` with HTTP 400, as the
# docs say the API does; it pauses the first search request with `pause_turn` after one search. Only the first part
# reading finds the claim. The key is in the home's `.env`, not in the environment. A temporary helper home per run.

TEMPLATE = Path(__file__).parents[1] / "fakes" / "anthropic-api" / "messages.json"
KEY = "sk-ant-invented-key"
OPUS_READING = (1000 * 4 + 2000 * 5 + 3000 * 0.20 + 500 * 20) / 1e6  # 0.0246
SONNET_REQUEST = (1000 * 2 + 2000 * 2.50 + 3000 * 0.10 + 500 * 10) / 1e6  # 0.0123
SEARCH = 0.01  # one web search

def comparable(flags):
    return [{k: v for k, v in f.items() if k != "id"} for f in flags]


def test_anthropic_api(tmp_path, monkeypatch):
    fake_video(monkeypatch, TWO_PARTS)
    claude_log, _ = fake_clis(tmp_path, monkeypatch, answers=ANSWERS | {"nothing": NOTHING})

    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    server.Helper(claude_home)._run("anthro1", 0)
    with_claude = json.loads((claude_home / "videos" / "anthro1.json").read_text())

    api = FakeMessagesAPI(pause_search=True)
    home = tmp_path / "api-home"
    home.mkdir()
    (home / "config.toml").write_text(f'provider = "anthropic"\nscreen = false\n[models]\n'
                                      f'search = "claude-sonnet-5-5"\n[anthropic]\nbase_url = "{api.url}"\n')
    (home / ".env").write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    claude_log.unlink()
    server.Helper(home)._run("anthro1", 0)
    data = json.loads((home / "videos" / "anthro1.json").read_text())
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    sent = api.requests
    kinds = [schema_kind(r["body"]["output_config"]["format"]["schema"]) for r in sent]

    # Case 1 · the Anthropic provider → no Claude Code reading, and the same flags as with Claude Code
    assert not claude_log.exists(), claude_log.read_text()
    assert data["status"] == "done", data
    assert with_claude["status"] == "done", with_claude
    assert [f["label"] for f in data["flags"] if f["type"] == "inaccuracy"] == ["false"], data["flags"]
    assert comparable(data["flags"]) == comparable(with_claude["flags"]), (data["flags"], with_claude["flags"])

    # Case 2 · every request → the key from .env, the API version, medium effort, the rules as a cached system prompt;
    # only a part reading (a conversation) caches its messages too
    assert {r["path"] for r in sent} == {"/v1/messages"}, sent
    sent_keys = {(r["headers"].get("x-api-key"), r["headers"].get("anthropic-version")) for r in sent}
    assert sent_keys == {(KEY, "2026-10-21")}, sent_keys
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
    api.stop()
    print("PASS S22 A2 · The Anthropic API reads a video like Claude Code does")


# S22 A3 · An OpenAI-compatible API set by its address reads a video
#
# Story: The person sets `provider = "openai"`, `base_url = "https://api.x.ai/v1"`, `key_env = "XAI_API_KEY"` and the
# Grok models in the settings file. The same invented interview gives the same flags. Each reading sends the key of
# `XAI_API_KEY` to that address, asks for JSON by the schema, the search adds web search, and the second part continues
# the first by its response id. A Grok model in the price table shows its cost; one that is not there shows a null cost.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
# ("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
# does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices.
# `config.toml` says `provider = "openai"`, the models `grok-4.7` (parts, verdict, judge) and `grok-4.7-fast` (search),
# and `[openai] base_url` points at a fake Responses API on a free local port (`http://127.0.0.1:<port>/v1`) with
# `key_env = "XAI_API_KEY"`. XAI_API_KEY is set in the environment and OPENAI_API_KEY is not. The fake answers by the
# schema in `text.format`, in the shape of tests/fakes/openai-api/responses.json (4,000 input tokens of which 3,000
# cached, 500 output), with a new response id each time and a `web_search_call` item before a search answer. Only the
# first part reading finds the claim. The `claude` and `codex` commands are fakes on PATH that log every call and fail.
# A temporary helper home.

RESPONSES = Path(__file__).parents[1] / "fakes" / "openai-api" / "responses.json"
XAI_KEY = "xai-invented-key"


class FakeResponsesAPI(FakeServer):
    """A local Responses API that answers by its schema: the claim for the first part reading only."""

    def __init__(self):
        super().__init__()
        self.replies, self.base_url = [], f"http://127.0.0.1:{self.port}/v1"

    def answer(self, body):
        name = schema_kind(body["text"]["format"]["schema"])
        first_part = name == "flags" and not any(
            "flags" in r["body"]["text"]["format"]["schema"]["properties"] for r in self.requests[:-1])
        reply = json.loads(RESPONSES.read_text()) | {"id": f"resp_{len(self.requests)}", "model": body["model"]}
        reply["output"][-1]["content"][0]["text"] = json.dumps(
            ANSWERS[name] if name != "flags" or first_part else NOTHING, ensure_ascii=False)
        if name == "evidence":
            reply["output"].insert(0, {"type": "web_search_call", "id": "ws_1", "status": "completed",
                                       "action": {"type": "search", "query": FALSE}})
        self.replies.append(reply)
        return 200, reply


def test_openai_compatible(tmp_path, monkeypatch):
    fake_video(monkeypatch, TWO_PARTS)
    monkeypatch.setenv("XAI_API_KEY", XAI_KEY)
    cli_log = fail_clis(tmp_path, monkeypatch)
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
    assert not cli_log.exists(), cli_log.read_text()
    assert data["status"] == "done", data
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    kinds = [schema_kind(r["body"]["text"]["format"]["schema"]) for r in sent]
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE)], found
    assert found[0]["sources"] == [INE], found[0]["sources"]

    # Case 2 · every request → the address of base_url, the key of XAI_API_KEY, the rules as instructions, medium
    # effort and strict JSON by the schema; the model of its role
    assert sorted(kinds) == ["evidence", "flags", "flags", "rulings", "verdicts"], kinds
    sent_to = {(r["path"], r["headers"].get("Authorization")) for r in sent}
    assert sent_to == {("/v1/responses", f"Bearer {XAI_KEY}")}, sent_to
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
    api.stop()
    print("PASS S22 A3 · An OpenAI-compatible API set by its address reads a video")


# S23 A1 · A chat API reads a video like Claude Code does
#
# Story: The person sets `provider = "chat"`, a `base_url`, `key_env = "HF_TOKEN"` and a model in the settings file, and
# puts the search service key in the helper's `.env`. An invented two-part interview with one false figure gives the one
# "Dato falso" flag that Claude Code gives. Each reading sends the key of `HF_TOKEN` to `<base_url>/chat/completions`
# and asks for JSON by the schema. Each part sends only its own window, never the first part's messages (S29). A model with no price shows a
# null cost.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
# ("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
# does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices.
# `config.toml` says `provider = "chat"`, `[chat] base_url` points at a fake Chat Completions API on a free local port
# with `key_env = "HF_TOKEN"`, every step uses the model `open/model-x`, and `[tavily] base_url` points at a fake Tavily
# API. HF_TOKEN and TAVILY_API_KEY are in the home's `.env`, not in the environment. The chat fake answers by the schema
# in `response_format`, in the shape of tests/fakes/chat-api/completion.json (4,000 prompt tokens of which 3,000 cached,
# 500 completion tokens). Only the first part reading finds the claim. The Tavily fake returns one INE result. The
# `claude` and `codex` commands are fakes on PATH that log every call and fail. A temporary helper home.

HF_KEY, SEARCH_KEY = "hf_invented_key", "tvly-invented-key"
MODEL = "open/model-x"


def test_chat_api(tmp_path, monkeypatch):
    fake_video(monkeypatch, TWO_PARTS)
    cli_log = fail_clis(tmp_path, monkeypatch)
    api, tavily = FakeChatAPI(), FakeTavily()
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text(
        'provider = "chat"\nscreen = false\n'
        f'[models]\nparts = "{MODEL}"\nverdict = "{MODEL}"\njudge = "{MODEL}"\nsearch = "{MODEL}"\n'
        f'[chat]\nbase_url = "{api.base_url}"\nkey_env = "HF_TOKEN"\n'
        f'[tavily]\nbase_url = "{tavily.base_url}"\n')
    (home / ".env").write_text(f"HF_TOKEN={HF_KEY}\nTAVILY_API_KEY={SEARCH_KEY}\n")

    server.Helper(home)._run("chat1", 0)
    data = json.loads((home / "videos" / "chat1.json").read_text())
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    readings = api.readings()
    kinds = [reply["kind"] for _, reply in readings]

    # Case 1 · the chat provider → no CLI reading; the one "Dato falso" flag that Claude Code gives for the same
    # answers (S22 A2), with its dated INE source
    assert not cli_log.exists(), cli_log.read_text()
    assert data["status"] == "done", data
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE)], found
    assert found[0]["sources"] == [INE], found[0]["sources"]

    # Case 2 · every reading → POST <base_url>/chat/completions with the key of HF_TOKEN, the rules as the system
    # message, strict JSON by the schema, the model of the settings and no tool
    assert sorted(kinds) == ["evidence", "flags", "flags", "rulings", "verdicts"], kinds
    assert len(api.requests) == 5, [r["body"].get("response_format", {}).get("type") for r in api.requests]
    for request, kind in zip(api.requests, kinds):
        body = request["body"]
        assert request["path"] == "/v1/chat/completions", request["path"]
        assert request["headers"].get("Authorization") == f"Bearer {HF_KEY}", request["headers"].get("Authorization")
        assert body["model"] == MODEL, body["model"]
        assert body["messages"][0]["role"] == "system", body["messages"][0]
        assert body["messages"][0]["content"].startswith("You analyse Spanish conversations."), body["messages"][0]
        fmt = body["response_format"]
        assert (fmt["type"], fmt["json_schema"]["strict"], bool(fmt["json_schema"].get("name"))) == \
            ("json_schema", True, True), fmt
        assert kind in fmt["json_schema"]["schema"]["properties"], (kind, fmt)
        assert "tools" not in body, (kind, body["tools"])

    # Case 3 · the figure search → the claim's query to Tavily with its key; the search reading gets the result's
    # title, URL, date and snippet
    assert [r["body"]["query"] for r in tavily.requests] == [FALSE], [r["body"] for r in tavily.requests]
    assert tavily.requests[0]["path"] == "/search", tavily.requests[0]["path"]
    assert tavily.requests[0]["headers"].get("Authorization") == f"Bearer {SEARCH_KEY}", tavily.requests[0]["headers"]
    search = next(r["body"] for r, reply in readings if reply["kind"] == "evidence")
    said = search["messages"][-1]["content"]
    for part in (RESULT["title"], RESULT["url"], RESULT["published_date"], RESULT["content"]):
        assert part in said, (part, said)

    # Case 4 · each part → its own system and user message only, never an earlier part's answer (S29)
    parts = [r["body"] for r, reply in readings if reply["kind"] == "flags"]
    assert [[m["role"] for m in p["messages"]] for p in parts] == [["system", "user"]] * 2, parts
    assert any(json.loads(reply["content"]) == ANSWERS["flags"] for _, reply in readings if reply["kind"] == "flags")

    # Case 5 · the usage log → each line has the model, the tokens (prompt without the cached part) and a null cost
    assert sorted(u["step"] for u in usage) == ["analyze_chunk", "analyze_chunk", "fact_check", "judge", "search"], usage
    for u in usage:
        assert u["model"] == MODEL, u
        assert (u["input_tokens"], u["cache_read_input_tokens"], u["output_tokens"]) == (1000, 3000, 500), u
        assert u["cost_usd"] is None, u
    assert data["cost_usd"] == 0, data["cost_usd"]
    api.stop()
    tavily.stop()
    print("PASS S23 A1 · A chat API reads a video like Claude Code does")


# S23 A2 · A server without JSON schema still works, and a broken answer fails cleanly
#
# Story: The person points `provider = "chat"` at a local server that rejects the JSON schema format with HTTP 400. The
# same interview still gives the "Dato falso" flag: each reading asks for a plain JSON object and puts the schema in the
# rules. When that server then answers text that is not JSON by the schema, the video stops with a reason that says so,
# and the helper keeps running.
# Edge case: WHEN the base URL is `http://localhost:…` and no key is set THEN the readings run with no key.
#
# Setup: the invented two-part interview of S23 A1 (one false figure in the first part), a fake YouTube, a fake Fact
# Check Tools API that finds nothing and no voices. `config.toml` says `provider = "chat"`, the model `llama-local` and
# `[chat] base_url = "http://localhost:<port>/v1"`: a fake Chat Completions API that answers a `json_schema` request
# with HTTP 400 ("response_format json_schema is not supported by this model") and a `json_object` request by the schema
# that its system message holds, with no cached-token details in its usage. No chat key is set anywhere; the Tavily key
# is in the home's `.env` and `[tavily] base_url` points at a fake Tavily API. Runs 2 and 3 use a fake that answers
# every part reading with broken text: words that are not JSON, then JSON that lacks the required fields. The `claude`
# and `codex` commands are fakes on PATH that log every call and fail. A temporary helper home per run.

def configure(home, api, tavily):
    home.mkdir()
    (home / "config.toml").write_text(
        'provider = "chat"\nscreen = false\n'
        '[models]\nparts = "llama-local"\nverdict = "llama-local"\njudge = "llama-local"\nsearch = "llama-local"\n'
        f'[chat]\nbase_url = "http://localhost:{api.port}/v1"\n'
        f'[tavily]\nbase_url = "{tavily.base_url}"\n')
    (home / ".env").write_text("TAVILY_API_KEY=tvly-invented-key\n")


def test_json_object_fallback(tmp_path, monkeypatch):
    fake_video(monkeypatch, TWO_PARTS)
    cli_log = fail_clis(tmp_path, monkeypatch)
    tavily = FakeTavily()
    api = FakeChatAPI(reject_schema=True)
    home = tmp_path / "home"
    configure(home, api, tavily)

    server.Helper(home)._run("local1", 0)
    data = json.loads((home / "videos" / "local1.json").read_text())
    readings = api.readings()
    rejected = [r for r in api.requests if r["body"]["response_format"]["type"] == "json_schema"]

    # Case 1 · a server that rejects json_schema → the same "Dato falso" flag through json_object readings
    assert not cli_log.exists(), cli_log.read_text()
    assert data["status"] == "done", data
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE)], found
    assert found[0]["sources"] == [INE], found[0]["sources"]

    # Case 2 · every answered reading → json_object with its schema in the system message; json_schema is tried at
    # most once per step, never again after a rejection (S29: parts read at once may each try it before the first
    # rejection)
    assert sorted(reply["kind"] for _, reply in readings) == ["evidence", "flags", "flags", "rulings", "verdicts"], \
        readings
    for request, reply in readings:
        body = request["body"]
        assert body["response_format"] == {"type": "json_object"}, body["response_format"]
        assert json.dumps(SCHEMAS[reply["kind"]]) in body["messages"][0]["content"], reply["kind"]
    tried = [kind_of(r["body"]) for r in rejected]
    assert tried and all(tried.count(k) == 1 for k in tried if k != "flags"), tried

    # Case 3 · localhost and no key → no Authorization header
    assert {r["headers"].get("Authorization") for r in api.requests} == {None}, api.requests[0]["headers"]
    api.stop()

    # Case 4 · a part answered with words that are not JSON → the video stops with a reason that names the JSON; the
    # helper returns normally
    broken = FakeChatAPI(reject_schema=True, broken="Claro, aquí tienes el análisis de la parte.")
    home = tmp_path / "broken"
    configure(home, broken, tavily)
    server.Helper(home)._run("local2", 0)
    data = json.loads((home / "videos" / "local2.json").read_text())
    assert data["status"] == "stopped", data
    assert data["stop_reason"].startswith("error:") and "JSON" in data["stop_reason"], data["stop_reason"]
    broken.stop()

    # Case 5 · a part answered with JSON that lacks the required fields → the same clean stop
    partial = FakeChatAPI(reject_schema=True, broken=json.dumps({"flags": []}))
    home = tmp_path / "partial"
    configure(home, partial, tavily)
    server.Helper(home)._run("local3", 0)
    data = json.loads((home / "videos" / "local3.json").read_text())
    assert data["status"] == "stopped", data
    assert data["stop_reason"].startswith("error:") and "JSON" in data["stop_reason"], data["stop_reason"]
    assert not cli_log.exists(), cli_log.read_text()
    partial.stop()
    tavily.stop()
    print("PASS S23 A2 · A server without JSON schema still works, and a broken answer fails cleanly")


# S23 A3 · Mixed providers per step, and a search service for a model with no web search
#
# Story: The person keeps `provider = "anthropic"` and adds a `[roles.parts]` and a `[roles.search]` table on a chat
# API. The parts are read on the chat API, the verdicts and the judge on Anthropic. The search sends the claim's queries
# to the search service, the chat model reads its results, and the card says "Dato falso" with the result's source and
# date. Without the search service key, the video finishes with no fact-check, and the usage log names the missing key.
#
# Setup: the invented two-part interview of S23 A1 (one false figure in the first part), a fake YouTube, a fake Fact
# Check Tools API that finds nothing and no voices. `config.toml` says `provider = "anthropic"` with `[anthropic]
# base_url` on a fake Messages API, `[roles.parts]` with `provider = "chat"`, the model `open/parts-model`, a fake Chat
# Completions API and `key_env = "HF_TOKEN"`, `[roles.search]` the same with the model `open/search-model`, and
# `[tavily] base_url` on a fake Tavily API that returns one dated INE result. ANTHROPIC_API_KEY, HF_TOKEN and
# TAVILY_API_KEY are in the home's `.env`. Run 2 has the same settings without TAVILY_API_KEY. The `claude` and `codex`
# commands are fakes on PATH that log every call and fail. A temporary helper home per run.

KEYS = {"ANTHROPIC_API_KEY": "sk-ant-invented", "HF_TOKEN": "hf_invented", "TAVILY_API_KEY": "tvly-invented"}


def configure_roles(home, anthropic, chat, tavily, keys):
    home.mkdir()
    (home / "config.toml").write_text(
        'provider = "anthropic"\nscreen = false\n'
        f'[anthropic]\nbase_url = "{anthropic.url}"\n'
        f'[roles.parts]\nprovider = "chat"\nbase_url = "{chat.base_url}"\nkey_env = "HF_TOKEN"\n'
        'model = "open/parts-model"\n'
        f'[roles.search]\nprovider = "chat"\nbase_url = "{chat.base_url}"\nkey_env = "HF_TOKEN"\n'
        'model = "open/search-model"\n'
        f'[tavily]\nbase_url = "{tavily.base_url}"\n')
    (home / ".env").write_text("".join(f"{k}={v}\n" for k, v in keys.items()))


def test_roles_and_search_api(tmp_path, monkeypatch):
    fake_video(monkeypatch, TWO_PARTS)
    cli_log = fail_clis(tmp_path, monkeypatch)
    anthropic, chat, tavily = FakeMessagesAPI(), FakeChatAPI(), FakeTavily()
    home = tmp_path / "home"
    configure_roles(home, anthropic, chat, tavily, KEYS)

    server.Helper(home)._run("mixed1", 0)
    data = json.loads((home / "videos" / "mixed1.json").read_text())
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    on_chat = [(kind_of(r["body"]), r["body"]["model"]) for r in chat.requests]
    on_anthropic = [(next(k for k in ("verdicts", "rulings", "flags", "evidence")
                          if k in r["body"]["output_config"]["format"]["schema"]["properties"]), r["body"]["model"])
                    for r in anthropic.requests]

    # Case 1 · parts and search on the chat API with their own models; verdict and judge on Anthropic's defaults
    assert not cli_log.exists(), cli_log.read_text()
    assert data["status"] == "done", data
    assert sorted(on_chat) == [("evidence", "open/search-model"), ("flags", "open/parts-model"),
                               ("flags", "open/parts-model")], on_chat
    assert sorted(on_anthropic) == [("rulings", "claude-opus-5-5"), ("verdicts", "claude-opus-5-5")], on_anthropic
    assert {r["headers"].get("Authorization") for r in chat.requests} == {f"Bearer {KEYS['HF_TOKEN']}"}
    assert {r["headers"].get("x-api-key") for r in anthropic.requests} == {KEYS["ANTHROPIC_API_KEY"]}
    assert not [r for r in anthropic.requests if r["body"].get("tools")], "a verdict or judge reading had a tool"

    # Case 2 · the figure search → the claim's query to Tavily; the chat search reading gets the result and no tool
    assert [r["body"]["query"] for r in tavily.requests] == [FALSE], [r["body"] for r in tavily.requests]
    assert {r["headers"].get("Authorization") for r in tavily.requests} == {f"Bearer {KEYS['TAVILY_API_KEY']}"}
    search = next(r["body"] for r in chat.requests if kind_of(r["body"]) == "evidence")
    assert "tools" not in search, search["tools"]
    assert RESULT["url"] in search["messages"][-1]["content"], search["messages"][-1]["content"]

    # Case 3 · the card → "Dato falso" (label false) with the result's source and date
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE)], found
    assert [(s["url"], s["date"]) for s in found[0]["sources"]] == [(RESULT["url"], RESULT["published_date"])], found

    # Case 4 · the usage log → each step with the model of its provider
    models = sorted((u["step"], u["model"]) for u in usage)
    assert models == [("analyze_chunk", "open/parts-model"), ("analyze_chunk", "open/parts-model"),
                      ("fact_check", "claude-opus-5-5"), ("judge", "claude-opus-5-5"),
                      ("search", "open/search-model")], models

    # Case 5 · no search key → the video finishes with no fact-check, no search request, and a usage line that names
    # the missing key
    for fake in (anthropic, chat, tavily):
        fake.requests.clear()
    chat.replies.clear()
    home = tmp_path / "no-search-key"
    configure_roles(home, anthropic, chat, tavily, {k: v for k, v in KEYS.items() if k != "TAVILY_API_KEY"})
    server.Helper(home)._run("mixed2", 0)
    data = json.loads((home / "videos" / "mixed2.json").read_text())
    usage = [json.loads(x) for x in (home / "usage.log").read_text().splitlines()]
    assert data["status"] == "done", data
    assert not [f for f in data["flags"] if f["type"] == "inaccuracy"], data["flags"]
    assert not tavily.requests, tavily.requests
    assert not [r for r in chat.requests if kind_of(r["body"]) == "evidence"], "a search reading ran"
    assert not [r for r in anthropic.requests if "verdicts" in r["body"]["output_config"]["format"]["schema"]["properties"]]
    stops = [u for u in usage if u.get("stop_reason")]
    assert [(u["step"], u["stop_reason"]) for u in stops] == [("fact_check", "TAVILY_API_KEY is not set")], usage
    assert not cli_log.exists(), cli_log.read_text()
    for fake in (anthropic, chat, tavily):
        fake.stop()
    print("PASS S23 A3 · Mixed providers per step, and a search service for a model with no web search")


# S29 A3 · A chat API reads each part with its window
#
# Story: The person sets `provider = "chat"` with one model. On an invented three-part interview, each part reading sends
# one system message and one user message that holds the minutes before the part, the positions list and the part; a
# later part never resends an earlier part's messages.
#
# Setup: the invented three-part interview of interview_fakes (THREE_PARTS: a greeting, a false figure, a stated position), with the
# screen off (`screen = false`) so that every part gets the full reading. The helper runs as it does for the person
# (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices. `config.toml` says
# `provider = "chat"`, `[chat] base_url` on a fake Chat Completions API on a free local port that records each request,
# `key_env = "HF_TOKEN"`, and `open/model-x` for every step under `[models]`. HF_TOKEN is in the home's `.env`; no search
# service key, so no figure is searched. The `claude` and `codex` commands fail. A temporary helper home.

def test_chat_reads_window(tmp_path, monkeypatch):
    fake_video(monkeypatch, THREE_PARTS)
    _, cli_log = fake_clis(tmp_path, monkeypatch, claude=False)
    api = FakeChatAPI()
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text(
        'provider = "chat"\nscreen = false\n'
        f'[models]\nparts = "{MODEL}"\nverdict = "{MODEL}"\njudge = "{MODEL}"\nsearch = "{MODEL}"\n'
        f'[chat]\nbase_url = "{api.base_url}"\nkey_env = "HF_TOKEN"\n')
    (home / ".env").write_text("HF_TOKEN=hf_invented\n")
    server.Helper(home)._run("window1", 0)
    api.stop()
    data = json.loads((home / "videos" / "window1.json").read_text())
    assert data["status"] == "done", data
    assert not cli_log.exists(), cli_log.read_text()
    parts = [b for k, b in api.kinds() if k == "flags"]

    # Case 1 · three parts → three part readings, each one system message and one user message, never an earlier
    # part's answer
    assert len(parts) == 3, f"FAIL S29 A3 · {len(parts)} part readings"
    for body in parts:
        assert [m["role"] for m in body["messages"]] == ["system", "user"], \
            f"FAIL S29 A3 · a part reading sends {[m['role'] for m in body['messages']]}"

    # Case 2 · the stance part → its user message holds the positions list, then the minutes before it (the false
    # figure) as CONTEXT, then its PART
    stance = next(b["messages"][1]["content"] for b in parts if "impuestos" in b["messages"][1]["content"].split("PART:")[-1])
    before, _, part = stance.partition("PART:")
    assert "POSITIONS" in before and "CONTEXT" in before and FALSE in before, \
        f"FAIL S29 A3 · the stance part's window: {stance}"
    assert "impuestos" in part, stance
    print("PASS S29 A3 · A chat API reads each part with its window")


# A `claude -p` call carries only our prompt: no Claude Code coding prompt, no tools it was not given, and no
# CLAUDE.md of a folder above it (each costs thousands of input tokens per call).

USAGE = {"input_tokens": 3, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 1}

def run(tmp_path, monkeypatch, tools=()):
    seen = tmp_path / "seen"
    fake = tmp_path / "claude"
    ok = json.dumps({"is_error": False, "total_cost_usd": 0.01, "usage": USAGE, "structured_output": {}})
    fake.write_text(f'#!/bin/sh\npwd > {seen}\nfor a in "$@"; do echo "[$a]" >> {seen}; done\necho \'{ok}\'\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    ClaudeCLI(tmp_path, model="opus").complete("hola", {"type": "object"}, tools=tools)
    cwd, *args = seen.read_text().splitlines()
    return Path(cwd).resolve(), args


def test_no_coding_prompt_no_tools_no_claude_md(tmp_path, monkeypatch):
    _, args = run(tmp_path, monkeypatch)
    assert "[--setting-sources=]" in args
    assert "[--system-prompt]" in args
    assert args[args.index("[--tools]") + 1] == "[]"


def test_web_search_is_the_only_tool_when_asked(tmp_path, monkeypatch):
    _, args = run(tmp_path, monkeypatch, tools=("WebSearch",))
    assert args[args.index("[--tools]") + 1] == "[WebSearch]"


# A 429 from `claude -p` is retried after a wait instead of stopping the analysis.

def test_429_is_retried(tmp_path, monkeypatch):
    calls = tmp_path / "calls"
    fake = tmp_path / "claude"
    busy = json.dumps({"is_error": True, "api_error_status": 429})
    ok = json.dumps({"is_error": False, "total_cost_usd": 0.01, "usage": USAGE, "structured_output": {"flags": []}})
    fake.write_text(f"#!/bin/sh\necho x >> {calls}\n"
                    f"if [ $(wc -l < {calls}) -lt 3 ]; then echo '{busy}'; exit 1; fi\necho '{ok}'\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    waits = []
    monkeypatch.setattr(llm_claude_cli.time, "sleep", waits.append)
    assert ClaudeCLI(tmp_path).complete("hola", {"type": "object"}) == {"flags": []}
    assert len(calls.read_text().splitlines()) == 3
    assert len(waits) == 2


def test_answer_without_structured_output_is_retried(tmp_path, monkeypatch):
    """A reading that ends with text instead of the JSON (seen on a 2-hour interview) is read again, not a crash."""
    calls = tmp_path / "calls"
    fake = tmp_path / "claude"
    text = json.dumps({"is_error": False, "total_cost_usd": 0.01, "usage": USAGE, "result": "Aquí tienes el análisis"})
    ok = json.dumps({"is_error": False, "total_cost_usd": 0.01, "usage": USAGE, "structured_output": {"flags": []}})
    fake.write_text(f"#!/bin/sh\necho x >> {calls}\n"
                    f"if [ $(wc -l < {calls}) -lt 2 ]; then echo '{text}'; exit 0; fi\necho '{ok}'\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(llm_claude_cli.time, "sleep", lambda s: None)
    assert ClaudeCLI(tmp_path).complete("hola", {"type": "object"}) == {"flags": []}
    assert len(calls.read_text().splitlines()) == 2


# A `claude -p` that hangs is cut at the timeout, also when a child process it started holds its output open.

def test_hung_claude_is_cut(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\nsleep 30 &\nsleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        ClaudeCLI(tmp_path, timeout=1).complete("hola", {"type": "object"})
    assert time.monotonic() - t0 < 10


# Inline 2026-11-22 · A CLI reading never gets the helper's keys
#
# Story: The person keeps ANTHROPIC_API_KEY and HF_TOKEN in the helper's `.env`, and the helper puts them in its
# environment. A `claude -p` reading with that key in its environment would bill the API in place of the
# subscription, and a reading led by a prompt injection could print it. Each `claude` and `codex` reading starts
# without the keys of `.env`; the rest of the environment (PATH, the cache setting) stays.
#
# Setup: a temporary helper home whose `.env` holds two invented keys, also set in the environment as `serve` does;
# fake `claude` and `codex` commands that write their environment to a file and answer `{}`.

def test_cli_readings_get_no_keys(tmp_path, monkeypatch):
    keys = {"ANTHROPIC_API_KEY": "sk-invented-1", "HF_TOKEN": "hf-invented-2"}
    (tmp_path / ".env").write_text("".join(f"{k}={v}\n" for k, v in keys.items()))
    for k, v in keys.items():
        monkeypatch.setenv(k, v)
    seen = tmp_path / "env"
    ok = json.dumps({"is_error": False, "total_cost_usd": 0.01, "usage": USAGE, "structured_output": {}})
    events = "\n".join(json.dumps(e) for e in (
        {"type": "thread.started", "thread_id": "t"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
        {"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}}))
    for name, answer in (("claude", ok), ("codex", events)):
        (tmp_path / name).write_text(f"#!/bin/sh\ncat > /dev/null\nenv > {seen}.{name}\ncat <<'EOF'\n{answer}\nEOF\n")
        (tmp_path / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("CODEX_BIN", raising=False)

    for provider in ("claude", "codex"):
        (tmp_path / "config.toml").write_text(f'provider = "{provider}"\n')
        server.provider_llm(tmp_path, "parts").complete("hola", {"type": "object"})
        env = (tmp_path / f"env.{provider}").read_text()
        for value in keys.values():
            assert value not in env, f"FAIL · the {provider} reading got a key of .env"
        assert f"PATH={tmp_path}" in env, f"FAIL · the {provider} reading lost PATH"
    assert "FORCE_PROMPT_CACHING_5M=1" in (tmp_path / "env.claude").read_text()
