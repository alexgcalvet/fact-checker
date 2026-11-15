"""S27 A2 · With the collector down, the mark waits and goes with the next one

Story: The collector answers 503, then nothing listens on its port. The tester marks 2 cards: the helper takes each
mark as always and reports no error, and no file appears in `~/.fact-checker/`. The collector comes back; the tester
marks a third card and one request holds all 3 marks. Edge case: a tester with no connection runs
`fact-checker feedback send`: the pending marks go to `~/.fact-checker/feedback-<date>.json`, the command prints that
path, and they stay pending.

Setup: a temporary helper home with a flag file of 3 flags. A fake collector on a free local port that answers 503
until the test lets it store again, and a local port where nothing listens. The helper HTTP server on another free
port. Failing fake `claude` and `codex` commands on PATH.
"""
import json
import socket
import sys
import time
from datetime import date

from fact_checker import cli
from s23_fakes import fail_clis
from s24_fakes import FALLACY, FIGURE, LATER, VIDEO, FakeCollector, home_with_flags, request, start_helper


DATED = "feedback-[0-9]*.json"  # the dated file; feedback-sent.json is the record of what was sent


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def mark(port, flag, verdict, reason=""):
    return request(port, f"/videos/{VIDEO}/marks", {"flag_id": flag["id"], "verdict": verdict, "reason": reason})


def run(monkeypatch, capsys, *args) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out


def test_down_collector_waits(tmp_path, monkeypatch, capsys):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    home_with_flags(home)
    saved = home / f"feedback-{date.today().isoformat()}.json"
    collector = FakeCollector(fail=503)
    (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
    port, stop = start_helper(home)
    try:
        # Case 1 · the collector answers 503 → the mark is taken as always; nothing stored, no file
        assert mark(port, FALLACY, "correct", "sí") == (200, {"ok": True})
        time.sleep(1)
        assert collector.posts == []
        assert list(home.glob(DATED)) == []

        # Case 2 · nothing listens on the collector's port → the same: taken, no file, the helper keeps answering
        (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "http://127.0.0.1:{closed_port()}"\n')
        assert mark(port, FIGURE, "unfair", "es 11 %") == (200, {"ok": True})
        time.sleep(1)
        assert list(home.glob(DATED)) == []
        assert request(port, f"/videos/{VIDEO}")[0] == 200

        # Case 3 · no connection, `fact-checker feedback send` → the dated file with both marks; its path printed
        code, out = run(monkeypatch, capsys, "feedback", "send")
        assert code == 0 and str(saved) in out, (code, out)
        body = json.loads(saved.read_text())
        assert sorted(m["flag_id"] for m in body["marks"]) == sorted([FALLACY["id"], FIGURE["id"]])
        saved.unlink()

        # Case 4 · the collector is back, a third mark → one request holds all 3 marks; still no file
        collector.fail = None
        (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
        mark(port, LATER, "unfair")
        end = time.monotonic() + 1
        while not collector.posts and time.monotonic() < end:
            time.sleep(0.02)
        time.sleep(0.3)
        assert len(collector.posts) == 1, collector.posts
        assert sorted(m["flag_id"] for m in collector.posts[0]["marks"]) == sorted(
            [FALLACY["id"], FIGURE["id"], LATER["id"]])
        assert list(home.glob(DATED)) == []

        # Case 5 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
        collector.stop()
    print("PASS S27 A2 · With the collector down, the mark waits and goes with the next one")
