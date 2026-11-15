"""S27 A3 · With sharing off, nothing leaves the laptop (the helper side)

Story: The foot of the side panel says "Tus marcas se comparten con el autor para mejorar el detector · Desactivar en
⚙" and has no send button. In ⚙ the tester unticks "Compartir mis marcas con el autor". The foot of the panel now says
"Tus marcas no se comparten · Activar en ⚙", and `share_marks = false` is in `~/.fact-checker/config.toml` beside the
existing lines. The tester marks a card: after a second the collector has nothing. The tester ticks the box again and
marks another card: only that new mark goes; the one given while sharing was off never does.

Setup: a temporary helper home with a flag file of 3 flags and a `config.toml` that holds a comment, `feedback_url`
pointing to a fake collector on a free local port, and a `[models]` table. The helper HTTP server on another free
port. Failing fake `claude` and `codex` commands on PATH. The ⚙ box and the panel line are checked in
s27-a3-share-toggle.test.ts.
"""
import time
import tomllib

from s23_fakes import fail_clis
from s24_fakes import FALLACY, FIGURE, LATER, VIDEO, FakeCollector, home_with_flags, request, start_helper


def mark(port, flag, verdict):
    return request(port, f"/videos/{VIDEO}/marks", {"flag_id": flag["id"], "verdict": verdict, "reason": ""})


def test_sharing_off(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    home_with_flags(home)
    collector = FakeCollector()
    config = home / "config.toml"
    config.write_text(f'# my settings\nfeedback_url = "{collector.url}"\n\n[models]\nparts = "sonnet"\n')
    port, stop = start_helper(home)
    try:
        # Case 1 · no share_marks line → not asked yet (S30): null, and nothing is shared
        assert request(port, "/share") == (200, {"share": None})

        # Case 2 · the box unticked → share_marks = false in config.toml, the other lines kept, top level
        assert request(port, "/share", {"share": False}) == (200, {"share": False})
        settings = tomllib.loads(config.read_text())
        assert settings["share_marks"] is False
        assert settings["feedback_url"] == collector.url and settings["models"] == {"parts": "sonnet"}
        assert "# my settings" in config.read_text()
        assert request(port, "/share") == (200, {"share": False})

        # Case 3 · a mark with sharing off → after a second the collector has nothing
        assert mark(port, FALLACY, "correct") == (200, {"ok": True})
        time.sleep(1)
        assert collector.posts == []

        # Case 4 · the box ticked again → share_marks = true, one line; the next mark sends only itself
        assert request(port, "/share", {"share": True}) == (200, {"share": True})
        assert config.read_text().count("share_marks") == 1
        assert tomllib.loads(config.read_text())["share_marks"] is True
        mark(port, FIGURE, "unfair")
        end = time.monotonic() + 1
        while not collector.posts and time.monotonic() < end:
            time.sleep(0.02)
        time.sleep(0.3)
        assert [m["flag_id"] for p in collector.posts for m in p["marks"]] == [FIGURE["id"]]

        # Case 5 · share_marks = false written by hand → a mark sends nothing
        config.write_text(f'share_marks = false\nfeedback_url = "{collector.url}"\n')
        assert request(port, "/share") == (200, {"share": False})
        mark(port, LATER, "unfair")
        time.sleep(1)
        assert len(collector.posts) == 1

        # Case 6 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
        collector.stop()
    print("PASS S27 A3 · With sharing off, nothing leaves the laptop (the helper side)")
