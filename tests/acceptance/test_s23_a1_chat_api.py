"""S23 A1 · A chat API reads a video like Claude Code does

Story: The person sets `provider = "chat"`, a `base_url`, `key_env = "HF_TOKEN"` and a model in the settings file, and
puts the search service key in the helper's `.env`. An invented two-part interview with one false figure gives the one
"Dato falso" flag that Claude Code gives. Each reading sends the key of `HF_TOKEN` to `<base_url>/chat/completions`
and asks for JSON by the schema. Each part sends only its own window, never the first part's messages (S29). A model with no price shows a
null cost.

Setup: invented word-by-word captions (one word every 0.5 s) of a 50-second interview in two parts: SPEAKER_01
("Invitado") gives one false figure in the first 30 seconds, SPEAKER_00 thanks him at second 40. The helper runs as it
does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices.
`config.toml` says `provider = "chat"`, `[chat] base_url` points at a fake Chat Completions API on a free local port
with `key_env = "HF_TOKEN"`, every step uses the model `open/model-x`, and `[tavily] base_url` points at a fake Tavily
API. HF_TOKEN and TAVILY_API_KEY are in the home's `.env`, not in the environment. The chat fake answers by the schema
in `response_format`, in the shape of tests/fakes/chat-api/completion.json (4,000 prompt tokens of which 3,000 cached,
500 completion tokens). Only the first part reading finds the claim. The Tavily fake returns one INE result. The
`claude` and `codex` commands are fakes on PATH that log every call and fail. A temporary helper home.
"""
import json

from fact_checker import server
from s23_fakes import ANSWERS, FALSE, INE, RESULT, SECOND, FakeChatAPI, FakeTavily, fail_clis, fake_video

KEY, SEARCH_KEY = "hf_invented_key", "tvly-invented-key"
MODEL = "open/model-x"


def test_chat_api(tmp_path, monkeypatch):
    fake_video(monkeypatch)
    cli_log = fail_clis(tmp_path, monkeypatch)
    api, tavily = FakeChatAPI(), FakeTavily()
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text(
        'provider = "chat"\nscreen = false\n'
        f'[models]\nparts = "{MODEL}"\nverdict = "{MODEL}"\njudge = "{MODEL}"\nsearch = "{MODEL}"\n'
        f'[chat]\nbase_url = "{api.base_url}"\nkey_env = "HF_TOKEN"\n'
        f'[tavily]\nbase_url = "{tavily.base_url}"\n')
    (home / ".env").write_text(f"HF_TOKEN={KEY}\nTAVILY_API_KEY={SEARCH_KEY}\n")

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
        assert request["headers"].get("Authorization") == f"Bearer {KEY}", request["headers"].get("Authorization")
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
