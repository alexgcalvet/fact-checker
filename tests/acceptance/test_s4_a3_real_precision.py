"""S4 A3 · The eval prints the real precision from the marks

Story: The marks log holds 3 evasion marks (1 correct, 2 unfair) and 4 inaccuracy marks (3 correct,
1 unfair). The person runs the eval of marks and reads: fallacy 33% (1 of 3), with evasion 33% (1 of 3)
under it; inaccuracy 75% (3 of 4).

Setup: a temporary helper home with a marks log; one inaccuracy flag was first marked unfair and then
correct, so only its latest mark counts.
"""
import json

from fact_checker.cli import report_marks


def mark(flag_id, kind, label, verdict, confidence=0.7):
    return {"video_id": "abcdefgh", "flag_id": flag_id, "quote": "palabras", "type": kind, "label": label,
            "confidence": confidence, "verdict": verdict, "reason": ""}


MARKS = [
    mark("evasion-10.0", "fallacy", "evasion", "correct"),
    mark("evasion-20.0", "fallacy", "evasion", "unfair"),
    mark("evasion-30.0", "fallacy", "evasion", "unfair"),
    mark("false-40.0", "inaccuracy", "false", "unfair"),
    mark("false-40.0", "inaccuracy", "false", "correct"),
    mark("false-50.0", "inaccuracy", "false", "correct"),
    mark("misleading-60.0", "inaccuracy", "misleading", "correct"),
    mark("misleading-70.0", "inaccuracy", "misleading", "unfair"),
]


def test_real_precision(tmp_path, capsys):
    (tmp_path / "marks.jsonl").write_text("".join(json.dumps(m) + "\n" for m in MARKS))
    report = report_marks(tmp_path)
    out = capsys.readouterr().out.splitlines()

    # Case 1 · 3 evasion marks, 1 correct → fallacy precision 1/3
    assert (report["fallacy"]["correct"], report["fallacy"]["marked"]) == (1, 3)

    # Case 2 · a flag marked twice → only the latest mark counts: inaccuracy 3 of 4
    assert (report["inaccuracy"]["correct"], report["inaccuracy"]["marked"]) == (3, 4)

    # Case 3 · the printed table → fallacy 33% (1/3), evasion 33% (1/3) under it, inaccuracy 75% (3/4)
    row = lambda name: next(line for line in out if line.strip().startswith(name))
    assert "33%" in row("fallacy") and "1/3" in row("fallacy")
    assert "33%" in row("evasion") and "1/3" in row("evasion")
    assert "75%" in row("inaccuracy") and "3/4" in row("inaccuracy")
    print("PASS S4 A3 · The eval prints the real precision from the marks")
