"""S29 A3 · A chat API reads each part with its window

Story: The person sets `provider = "chat"` with one model. On an invented three-part interview, each part reading sends
one system message and one user message that holds the minutes before the part, the positions list and the part; a
later part never resends an earlier part's messages.

Setup: the invented three-part interview of the S29 fakes (a greeting, a false figure, a stated position), with the
screen off (`screen = false`) so that every part gets the full reading. The helper runs as it does for the person
(Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and no voices. `config.toml` says
`provider = "chat"`, `[chat] base_url` on a fake Chat Completions API on a free local port that records each request,
`key_env = "HF_TOKEN"`, and `open/model-x` for every step under `[models]`. HF_TOKEN is in the home's `.env`; no search
service key, so no figure is searched. The `claude` and `codex` commands fail. A temporary helper home.
"""
import json

from fact_checker import server
from s29_fakes import FALSE, FakeChatAPI, fake_clis, fake_video

MODEL = "open/model-x"


def test_chat_reads_window(tmp_path, monkeypatch):
    fake_video(monkeypatch)
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
