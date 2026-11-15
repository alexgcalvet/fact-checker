"""S23 A3 · Mixed providers per step, and a search service for a model with no web search

Story: The person keeps `provider = "anthropic"` and adds a `[roles.parts]` and a `[roles.search]` table on a chat
API. The parts are read on the chat API, the verdicts and the judge on Anthropic. The search sends the claim's queries
to the search service, the chat model reads its results, and the card says "Dato falso" with the result's source and
date. Without the search service key, the video finishes with no fact-check, and the usage log names the missing key.

Setup: the invented two-part interview of S23 A1 (one false figure in the first part), a fake YouTube, a fake Fact
Check Tools API that finds nothing and no voices. `config.toml` says `provider = "anthropic"` with `[anthropic]
base_url` on a fake Messages API, `[roles.parts]` with `provider = "chat"`, the model `open/parts-model`, a fake Chat
Completions API and `key_env = "HF_TOKEN"`, `[roles.search]` the same with the model `open/search-model`, and
`[tavily] base_url` on a fake Tavily API that returns one dated INE result. ANTHROPIC_API_KEY, HF_TOKEN and
TAVILY_API_KEY are in the home's `.env`. Run 2 has the same settings without TAVILY_API_KEY. The `claude` and `codex`
commands are fakes on PATH that log every call and fail. A temporary helper home per run.
"""
import json

from fact_checker import server
from s23_fakes import (FALSE, RESULT, SECOND, FakeChatAPI, FakeMessagesAPI, FakeTavily, fail_clis, fake_video,
                       kind_of)

KEYS = {"ANTHROPIC_API_KEY": "sk-ant-invented", "HF_TOKEN": "hf_invented", "TAVILY_API_KEY": "tvly-invented"}


def configure(home, anthropic, chat, tavily, keys):
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
    fake_video(monkeypatch)
    cli_log = fail_clis(tmp_path, monkeypatch)
    anthropic, chat, tavily = FakeMessagesAPI(), FakeChatAPI(), FakeTavily()
    home = tmp_path / "home"
    configure(home, anthropic, chat, tavily, KEYS)

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
    configure(home, anthropic, chat, tavily, {k: v for k, v in KEYS.items() if k != "TAVILY_API_KEY"})
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
