"""S24 A4 · The owner pulls the new rows with the admin token

Story: The owner sets `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env` and runs `fact-checker feedback pull`. It prints
"3 new marks" and writes them to a file in `~/.fact-checker/feedback/`. A second pull prints "0 new marks". The
collector answers 401 to a read without the token or with a wrong one, and the pull then names the token and exits 1.

Setup: a fake collector on a free local port that holds 3 rows from 2 testers and answers a read only with the admin
token. A temporary helper home whose `config.toml` sets `feedback_url` to it. Failing fake `claude` and `codex`
commands on PATH. The collector's own 401 is checked in s24-a4-collector-read.test.ts.
"""
import json
import sys

from fact_checker import cli
from s23_fakes import fail_clis
from s24_fakes import TOKEN, FakeCollector


def row(install, flag_id, at):
    return {"install_id": install, "helper_version": "0.1.0", "received_at": at, "video_id": "abcdefgh",
            "flag_id": flag_id, "t": 42.0, "type": "fallacy", "label": "ad_hominem", "quote": "frase inventada",
            "confidence": 0.85, "verdict": "unfair", "reason": "", "provider": "claude", "model": "opus"}


ROWS = [row("11111111-1111-4111-8111-111111111111", "a-1.0", "2026-11-15T10:00:00.000Z"),
        row("11111111-1111-4111-8111-111111111111", "a-2.0", "2026-11-15T10:00:00.000Z"),
        row("22222222-2222-4222-8222-222222222222", "a-1.0", "2026-11-15T11:30:00.000Z")]


def run(monkeypatch, capsys, *args) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out


def test_feedback_pull(tmp_path, monkeypatch, capsys):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    home.mkdir()
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.delenv("FEEDBACK_ADMIN_TOKEN", raising=False)
    collector = FakeCollector(rows=ROWS)
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    try:
        # Case 1 · no token → the collector answers 401; the pull names the token and exits 1
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 1 and "FEEDBACK_ADMIN_TOKEN" in out, (code, out)
        assert collector.reads[-1]["auth"] is None

        # Case 2 · a wrong token → 401; the pull names the token, never prints its value, and exits 1
        (home / ".env").write_text("FEEDBACK_ADMIN_TOKEN=wrong-token\n")
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 1 and "FEEDBACK_ADMIN_TOKEN" in out and "wrong-token" not in out, (code, out)
        assert not (home / "feedback").exists() or not list((home / "feedback").glob("*.jsonl"))

        # Case 3 · the token in .env → "3 new marks"; one file in feedback/ with the 3 rows
        (home / ".env").write_text(f"FEEDBACK_ADMIN_TOKEN={TOKEN}\n")
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 0 and "3 new marks" in out, (code, out)
        files = list((home / "feedback").glob("*.jsonl"))
        assert len(files) == 1
        assert [json.loads(line) for line in files[0].read_text().splitlines()] == ROWS
        assert collector.reads[-1]["path"] == "/marks"
        assert TOKEN not in out

        # Case 4 · a second pull → it asks only for rows after the last one; "0 new marks"; no new file
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 0 and "0 new marks" in out, (code, out)
        assert collector.reads[-1]["query"]["since"] == ["2026-11-15T11:30:00.000Z"]
        assert len(list((home / "feedback").glob("*.jsonl"))) == 1

        # Case 5 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        collector.stop()
    print("PASS S24 A4 · The owner pulls the new rows with the admin token")
