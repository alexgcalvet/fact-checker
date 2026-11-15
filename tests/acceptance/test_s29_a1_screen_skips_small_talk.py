"""S29 A1 · A cheap screen skips the parts with nothing to check

Story: The helper analyses an invented interview of three parts: a greeting, a false figure and a stated position. The
usage log shows one `screen` reading per part, by `haiku`; the greeting is logged as skipped and gets no full reading;
the two others get it. The part after the greeting still sees the greeting's words before its own.
Edge case: WHEN the screen reading fails or does not say "no" THEN the part gets the full reading.

Setup: invented word-by-word captions (one word every 0.5 s) of a 2.5-minute interview in three parts: the host's
greeting (0:00), the guest's false figure (0:30) and the guest's stance on taxes (2:30). The helper runs as it does for
the person (Helper._run, conversation mode, no settings file), with a fake YouTube, a fake Fact Check Tools API that
finds nothing and no voices. The `claude` command is a fake on PATH that logs the kind, model, tools and message of
each reading and answers by the JSON schema it gets; its screen says "no" only to the part that holds the greeting.
The `codex` command fails. A temporary helper home per run.
"""
import json

from fact_checker import server
from s29_fakes import FALSE, GREETING, fake_clis, fake_video, jsonl


def analyse(tmp_path, monkeypatch, name: str, config: str | None = None):
    run = tmp_path / name
    home = run / "home"
    home.mkdir(parents=True)
    claude_log, _ = fake_clis(run, monkeypatch)
    if config is not None:
        (home / "config.toml").write_text(config)
    server.Helper(home)._run("screen1", 0)
    data = json.loads((home / "videos" / "screen1.json").read_text())
    return data, jsonl(home / "usage.log"), jsonl(claude_log)


def test_screen_skips_small_talk(tmp_path, monkeypatch):
    fake_video(monkeypatch)

    # Case 1 · no settings → one screen reading per part by haiku, with no tool; the greeting part is logged as
    # skipped (read false, with the screen's reason) and the two others as read
    data, usage, readings = analyse(tmp_path, monkeypatch, "default")
    assert data["status"] == "done", data
    screens = sorted((u["chunk_start"], u["model"], u["read"]) for u in usage if u["step"] == "screen")
    assert screens == [(0, "haiku", False), (30, "haiku", True), (150, "haiku", True)], \
        f"FAIL S29 A1 · screen lines {[u for u in usage if u['step'] == 'screen']}"
    assert all(u["reason"] for u in usage if u["step"] == "screen"), usage
    assert [r["tools"] for r in readings if r["kind"] == "screen"] == ["", "", ""], readings

    # Case 2 · the greeting gets no full reading; the figure and the stance do, and the figure still gives its
    # "Dato falso" flag
    parts = sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk")
    assert parts == [30, 150], f"FAIL S29 A1 · full readings of the parts at {parts}"
    assert [(f["label"], f["quote"]) for f in data["flags"] if f["type"] == "inaccuracy"] == [("false", FALSE)], data

    # Case 3 · the full reading of the part after the greeting → the greeting's words come before its own PART
    first = next(r["text"] for r in readings if r["kind"] == "flags" and FALSE in r["text"].split("PART:")[-1])
    before, _, part = first.partition("PART:")
    assert GREETING in before and FALSE in part, f"FAIL S29 A1 · the next part does not see the greeting: {first}"

    # Case 4 · the screen reading fails → every part gets the full reading
    monkeypatch.setenv("FAKE_SCREEN_FAILS", "1")
    data, usage, _ = analyse(tmp_path, monkeypatch, "failing")
    monkeypatch.delenv("FAKE_SCREEN_FAILS")
    assert data["status"] == "done", data
    assert sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk") == [0, 30, 150], usage

    # Case 5 · the screen answers with no `read` at all → every part gets the full reading
    monkeypatch.setenv("FAKE_SCREEN_ODD", "1")
    data, usage, _ = analyse(tmp_path, monkeypatch, "odd")
    monkeypatch.delenv("FAKE_SCREEN_ODD")
    assert data["status"] == "done", data
    assert sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk") == [0, 30, 150], usage

    # Case 6 · `screen = false` in the settings (for a measurement) → no screen reading, every part read in full
    data, usage, readings = analyse(tmp_path, monkeypatch, "off", "screen = false\n")
    assert data["status"] == "done", data
    assert not [r for r in readings if r["kind"] == "screen"], readings
    assert sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk") == [0, 30, 150], usage
    print("PASS S29 A1 · A cheap screen skips the parts with nothing to check")
