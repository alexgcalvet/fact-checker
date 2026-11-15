"""S23 A2 · A server without JSON schema still works, and a broken answer fails cleanly

Story: The person points `provider = "chat"` at a local server that rejects the JSON schema format with HTTP 400. The
same interview still gives the "Dato falso" flag: each reading asks for a plain JSON object and puts the schema in the
rules. When that server then answers text that is not JSON by the schema, the video stops with a reason that says so,
and the helper keeps running.
Edge case: WHEN the base URL is `http://localhost:…` and no key is set THEN the readings run with no key.

Setup: the invented two-part interview of S23 A1 (one false figure in the first part), a fake YouTube, a fake Fact
Check Tools API that finds nothing and no voices. `config.toml` says `provider = "chat"`, the model `llama-local` and
`[chat] base_url = "http://localhost:<port>/v1"`: a fake Chat Completions API that answers a `json_schema` request
with HTTP 400 ("response_format json_schema is not supported by this model") and a `json_object` request by the schema
that its system message holds, with no cached-token details in its usage. No chat key is set anywhere; the Tavily key
is in the home's `.env` and `[tavily] base_url` points at a fake Tavily API. Runs 2 and 3 use a fake that answers
every part reading with broken text: words that are not JSON, then JSON that lacks the required fields. The `claude`
and `codex` commands are fakes on PATH that log every call and fail. A temporary helper home per run.
"""
import json

from fact_checker import server
from s23_fakes import FALSE, INE, SCHEMAS, SECOND, FakeChatAPI, FakeTavily, fail_clis, fake_video, kind_of


def configure(home, api, tavily):
    home.mkdir()
    (home / "config.toml").write_text(
        'provider = "chat"\nscreen = false\n'
        '[models]\nparts = "llama-local"\nverdict = "llama-local"\njudge = "llama-local"\nsearch = "llama-local"\n'
        f'[chat]\nbase_url = "http://localhost:{api.port}/v1"\n'
        f'[tavily]\nbase_url = "{tavily.base_url}"\n')
    (home / ".env").write_text("TAVILY_API_KEY=tvly-invented-key\n")


def test_json_object_fallback(tmp_path, monkeypatch):
    fake_video(monkeypatch)
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
