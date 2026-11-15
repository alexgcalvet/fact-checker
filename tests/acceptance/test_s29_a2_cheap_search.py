"""S29 A2 · The figure search runs on the cheap model

Story: With no settings file, the same interview's false figure is searched by `haiku` with web search, and its verdict
is given by `opus`. With `provider = "anthropic"`, the search reading goes to `claude-haiku-5-5` with the web search
tool and the verdict to `claude-opus-5-5`.

Setup: the invented three-part interview of the S29 fakes (a greeting, a false figure, a stated position). The helper
runs as it does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and
no voices. Case 1: the `claude` command is a fake on PATH that logs the kind, model and tools of each reading. Case 2:
`config.toml` says `provider = "anthropic"` with `[anthropic] base_url` on a fake Messages API on a free local port that
records each request; ANTHROPIC_API_KEY is in the home's `.env`; the `claude` and `codex` commands fail. A temporary
helper home per run.
"""
import json

from fact_checker import server
from s29_fakes import FALSE, FakeMessagesAPI, fake_clis, fake_video, jsonl


def test_cheap_search(tmp_path, monkeypatch):
    fake_video(monkeypatch)

    # Case 1 · no settings → the search reading by haiku with WebSearch, the verdict by opus with no tool
    run = tmp_path / "default"
    home = run / "home"
    home.mkdir(parents=True)
    claude_log, _ = fake_clis(run, monkeypatch)
    server.Helper(home)._run("search1", 0)
    data = json.loads((home / "videos" / "search1.json").read_text())
    readings = jsonl(claude_log)
    assert data["status"] == "done", data
    search = [(r["model"], r["tools"]) for r in readings if r["kind"] == "evidence"]
    verdict = [(r["model"], r["tools"]) for r in readings if r["kind"] == "verdicts"]
    assert len(search) == 1 and search[0][0] == "haiku" and "WebSearch" in search[0][1], \
        f"FAIL S29 A2 · search readings {search}"
    assert verdict == [("opus", "")], f"FAIL S29 A2 · verdict readings {verdict}"
    assert [(f["label"], f["quote"]) for f in data["flags"] if f["type"] == "inaccuracy"] == [("false", FALSE)], data

    # Case 2 · provider anthropic → the search request to claude-haiku-5-5 with the web search tool, the verdict
    # request to claude-opus-5-5 with no tool
    run = tmp_path / "anthropic"
    home = run / "home"
    home.mkdir(parents=True)
    _, cli_log = fake_clis(run, monkeypatch, claude=False)
    api = FakeMessagesAPI()
    (home / "config.toml").write_text(f'provider = "anthropic"\n[anthropic]\nbase_url = "{api.url}"\n')
    (home / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-invented\n")
    server.Helper(home)._run("search2", 0)
    api.stop()
    data = json.loads((home / "videos" / "search2.json").read_text())
    assert data["status"] == "done", data
    assert not cli_log.exists(), cli_log.read_text()
    kinds = api.kinds()
    search = [(b["model"], [t["type"] for t in b.get("tools", [])]) for k, b in kinds if k == "evidence"]
    verdict = [(b["model"], b.get("tools")) for k, b in kinds if k == "verdicts"]
    assert len(search) == 1 and search[0][0] == "claude-haiku-5-5" and search[0][1][0].startswith("web_search"), \
        f"FAIL S29 A2 · search requests {search}"
    assert verdict == [("claude-opus-5-5", None)], f"FAIL S29 A2 · verdict requests {verdict}"
    print("PASS S29 A2 · The figure search runs on the cheap model")
