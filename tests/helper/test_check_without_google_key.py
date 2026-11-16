"""Without the Google Fact Check key, figures are still checked by web search: only published fact-checks are missing.

A helper restarted without that key once read three whole interviews and checked no figure at all.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "acceptance"))
from s29_fakes import FALSE, fake_clis, fake_video, jsonl  # noqa: E402

from fact_checker import cli  # noqa: E402

VIDEO = "sinclave123"


def test_figures_checked_without_google_key(tmp_path, monkeypatch):
    fake_video(monkeypatch)
    monkeypatch.delenv("FACT_CHECK_API_KEY")
    home = tmp_path / "home"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    claude_log, _ = fake_clis(tmp_path / "run", monkeypatch)
    monkeypatch.setattr(sys, "argv", ["fact-checker", "analyze", f"https://www.youtube.com/watch?v={VIDEO}"])

    cli.main()

    data = json.loads((home / "videos" / f"{VIDEO}.json").read_text())
    assert [f["quote"] for f in data["flags"] if f["type"] == "inaccuracy"] == [FALSE]
    assert "verdicts" in {r["kind"] for r in jsonl(claude_log)}
    assert [c["outcome"] for c in jsonl(home / "claims.jsonl")] == ["flagged"]
