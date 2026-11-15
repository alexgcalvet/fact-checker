"""S8 A3 · The eval scores contradictions

Story: The person runs the eval. The golden dialogues now hold planted contradictions, and the printed
table has a contradiction row with its precision and recall next to the fallacy and inaccuracy rows.

Setup: the real golden dialogues of tests/golden. A fake Claude that, in each part call, lists every
planted contradiction and every contradiction decoy (a decoy with a "related" statement) whose second
statement is in that PART, each pinned on the speaker of its golden line; planted ones at confidence 0.9,
decoys at 0.6; it lists no fallacy, claim or question. No fact-check service.
"""
import json
import re

from fact_checker.cli import GOLDEN, run_eval


def norm(text):
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())


DIALOGUES = [json.loads(p.read_text()) for p in sorted(GOLDEN.glob("*.json"))]
PLANTED = [(d, e) for d in DIALOGUES for e in d["expected"] if e["type"] == "contradiction"]
DECOYS = [(d, e) for d in DIALOGUES for e in d["decoys"] if "related" in e]


def line_of(dialogue, quote):
    return next(line for line in dialogue["lines"] if norm(quote) in norm(line["text"]))


def same_speaker(dialogue, item):
    return line_of(dialogue, item["quote"])["speaker"] == line_of(dialogue, item["related"])["speaker"]


def contradiction(dialogue, item, confidence):
    return {"quote": item["quote"], "earlier": item["related"],
            "speaker": line_of(dialogue, item["quote"])["speaker"],
            "earlier_speaker": line_of(dialogue, item["related"])["speaker"],
            "reason": "Dice lo contrario de lo que dijo antes.", "confidence": confidence}


SCRIPTED = [contradiction(d, e, 0.9) for d, e in PLANTED] + [contradiction(d, e, 0.6) for d, e in DECOYS]


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        part = norm(prompt.split("PART:")[-1])
        return {"flags": [], "claims": [], "questions": [],
                "contradictions": [dict(c) for c in SCRIPTED if norm(c["quote"]) in part]}


def test_eval_scores_contradictions(capsys):
    # Case 1 · two or more dialogues hold planted contradictions → each has two statements of the same
    # speaker, the second one more than two and at most ten minutes after the first; some decoys are two
    # different speakers who disagree, and some are one speaker
    assert len({d["title"] for d, _ in PLANTED}) >= 2, "fewer than two dialogues with contradictions"
    for d, e in PLANTED:
        assert e["label"] == "self"
        first, second = line_of(d, e["related"]), line_of(d, e["quote"])
        assert first["speaker"] == second["speaker"], e
        assert 120 < second["t"] - first["t"] <= 600, e
    assert any(not same_speaker(d, e) for d, e in DECOYS)
    assert any(same_speaker(d, e) for d, e in DECOYS)

    report = run_eval(GOLDEN, llm=FakeClaude(), factcheck=None)
    out = capsys.readouterr().out
    row = report["contradiction"]
    flagged_decoys = sum(same_speaker(d, e) for d, e in DECOYS)
    precision = len(PLANTED) / (len(PLANTED) + flagged_decoys)

    # Case 2 · every planted contradiction is found → recall 100%
    assert row["expected"] == len(PLANTED)
    assert row["recall"] == 1.0, row

    # Case 3 · the decoys of one speaker count as wrong; decoys of two speakers make no flag → precision
    # is the planted ones over the planted ones and the one-speaker decoys
    assert abs(row["precision"] - precision) < 0.01, row

    # Case 4 · the printed table has a contradiction row with its precision and recall, next to the
    # fallacy and inaccuracy rows
    lines = out.splitlines()
    printed = next(line for line in lines if line.startswith("contradiction"))
    assert f"{precision:.0%}" in printed and "100%" in printed, printed
    assert any(line.startswith("fallacy") for line in lines)
    assert any(line.startswith("inaccuracy") for line in lines)
    print("PASS S8 A3 · The eval scores contradictions")
