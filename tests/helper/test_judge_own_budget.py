"""The judge reads even when the parts and fact checks spent the whole call budget, and a failed judge leaves a line.

A 1 h 52 min interview with many checked figures once used every call before the judge, which then ruled on nothing
and logged nothing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "acceptance"))
from s29_fakes import fake_clis, fake_video, jsonl  # noqa: E402

from fact_checker import cli  # noqa: E402
from fact_checker.core import scheduler  # noqa: E402

VIDEO = "presupuesto1"


def run(tmp_path, monkeypatch) -> tuple[list[dict], dict]:
    fake_video(monkeypatch)
    home = tmp_path / "home"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    claude_log, _ = fake_clis(tmp_path / "run", monkeypatch)
    monkeypatch.setattr(sys, "argv", ["fact-checker", "analyze", f"https://www.youtube.com/watch?v={VIDEO}"])
    cli.main()
    return jsonl(home / "usage.log"), json.loads((home / "videos" / f"{VIDEO}.json").read_text())


def test_judge_reads_after_the_budget_is_spent(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "CALLS_PER_HOUR", 3)  # the two parts read and the verdict use them all
    usage, data = run(tmp_path, monkeypatch)
    judge = [u for u in usage if u["step"] == "judge"]
    assert judge and not any(u.get("stop_reason") for u in judge), judge
    assert data["status"] == "done"


def test_failed_judge_is_logged(tmp_path, monkeypatch):
    monkeypatch.setattr("fact_checker.core.judge.judge", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("caído")))
    usage, _ = run(tmp_path, monkeypatch)
    assert any(u["step"] == "judge" and "caído" in str(u.get("stop_reason")) for u in usage), usage
