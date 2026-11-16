"""The eval: precision and recall on the golden dataset and on the person's marks."""
import json
import re

from fact_checker.cli import GOLDEN, report_marks, run_eval
from video_fakes import NoPublishedChecks


# S3 A2 · The eval scores flags against the expected ones
#
# Story: Two invented dialogues hold 4 expected fallacies. The model returns 3 fallacies: 2 on the expected
# words with the expected name, 1 elsewhere. The eval reports fallacy precision 67% and recall 50%. A flag
# with the expected name that quotes only part of the expected words counts as right if it shares at least
# half of their words.
#
# Setup: a temporary golden folder with two short dialogues; a fake Claude that answers every part with the
# same three fallacies (one exact, one with 4 of the 6 expected words, one on a fair argument) and no claims.

DIALOGUES = {
    "one.json": {
        "title": "one", "published_at": "2026-01-15",
        "lines": [
            {"t": 0, "speaker": "host", "text": "qué opina de la propuesta de la oposición"},
            {"t": 4, "speaker": "guest", "text": "la oposición no tiene autoridad para hablar"},
            {"t": 9, "speaker": "guest", "text": "o aprobamos la ley o llega el caos"},
            {"t": 14, "speaker": "guest", "text": "la ley reduce los plazos de los permisos de obra"},
        ],
        "expected": [
            {"type": "fallacy", "label": "ad_hominem", "quote": "la oposición no tiene autoridad para hablar"},
            {"type": "fallacy", "label": "false_dilemma", "quote": "o aprobamos la ley o llega el caos"},
        ],
    },
    "two.json": {
        "title": "two", "published_at": "2026-01-15",
        "lines": [
            {"t": 0, "speaker": "host", "text": "por qué subió el precio del alquiler"},
            {"t": 4, "speaker": "guest", "text": "desde que gobierna mi partido todo ha mejorado en el país"},
            {"t": 10, "speaker": "guest", "text": "todos los expertos dicen que vamos bien"},
        ],
        "expected": [
            {"type": "fallacy", "label": "false_cause", "quote": "desde que gobierna mi partido todo ha mejorado"},
            {"type": "fallacy", "label": "vague_authority", "quote": "todos los expertos dicen que vamos bien"},
        ],
    },
}

SCRIPTED = [
    {"quote": "La oposición no tiene autoridad para hablar", "label": "ad_hominem", "speaker": "guest",
     "reason": "Ataca a la persona.", "confidence": 0.9},
    {"quote": "todos los expertos dicen", "label": "vague_authority", "speaker": "guest",
     "reason": "Autoridad sin nombre.", "confidence": 0.8},
    {"quote": "la ley reduce los plazos de los permisos de obra", "label": "hasty_generalization",
     "speaker": "guest", "reason": "Generaliza.", "confidence": 0.7},
]


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [dict(f) for f in SCRIPTED], "claims": []}


def test_eval_scores(tmp_path, capsys):
    for name, dialogue in DIALOGUES.items():
        (tmp_path / name).write_text(json.dumps(dialogue, ensure_ascii=False))

    report = run_eval(tmp_path, llm=FakeClaude(), factcheck=None)
    out = capsys.readouterr().out

    # Case 1 · 2 of the 3 fallacy flags match an expected one → precision 2/3
    assert abs(report["fallacy"]["precision"] - 2 / 3) < 0.01

    # Case 2 · 2 of the 4 expected fallacies are found → recall 1/2
    assert abs(report["fallacy"]["recall"] - 0.5) < 0.01

    # Case 3 · a flag that shares 4 of the 6 expected words, with the expected name → counts as right
    assert report["fallacy"]["matched"] == 2

    # Case 4 · the printed table shows the fallacy row with 67% and 50%
    row = next(line for line in out.splitlines() if line.startswith("fallacy"))
    assert "67%" in row and "50%" in row
    print("PASS S3 A2 · The eval scores flags against the expected ones")


# S3 A3 · The eval picks the bar per type and saves it
#
# Story: The fallacy flags of a run have confidences 0.9 right, 0.85 right, 0.7 wrong, 0.6 right, 0.5 wrong;
# the inaccuracy flags are all wrong. With "save", the eval writes fallacy 0.85 and inaccuracy "never" to the
# thresholds file.
#
# Setup: a temporary golden folder with one dialogue that expects three fallacies and no inaccuracy; a fake
# Claude that returns five fallacies (three on the expected words at 0.9, 0.85 and 0.6, two on fair lines at
# 0.7 and 0.5) and five claims that it then judges false with dated sources; a fake Fact Check Tools API that
# finds nothing; a temporary thresholds file.

LINES = [
    "la oposición no tiene autoridad para hablar",
    "o aprobamos la ley o llega el caos",
    "todos los expertos dicen que vamos bien",
    "la ley reduce los plazos de los permisos de obra",
    "el plan prevé cuatro mil viviendas nuevas",
    "el paro en enero fue del once por ciento",
    "la deuda pública bajó el año pasado",
    "el salario mínimo subió en febrero",
]
DIALOGUE = {
    "title": "bars", "published_at": "2026-01-15",
    "lines": [{"t": i * 3, "speaker": "guest", "text": text} for i, text in enumerate(LINES)],
    "expected": [
        {"type": "fallacy", "label": "ad_hominem", "quote": LINES[0]},
        {"type": "fallacy", "label": "false_dilemma", "quote": LINES[1]},
        {"type": "fallacy", "label": "vague_authority", "quote": LINES[2]},
    ],
}
FLAGS = [
    (LINES[0], "ad_hominem", 0.9), (LINES[1], "false_dilemma", 0.85), (LINES[3], "false_cause", 0.7),
    (LINES[2], "vague_authority", 0.6), (LINES[4], "hasty_generalization", 0.5),
]
CLAIMS = [LINES[4], LINES[5], LINES[6], LINES[7], LINES[3]]


class BarsModel:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                {"quote": q, "verdict": "false", "reason": "No.", "confidence": 0.95,
                 "sources": [{"publisher": "INE", "url": f"https://www.ine.es/{i}", "date": "2025-12-01"}],
                 "note": None} for i, q in enumerate(CLAIMS)]}
        return {"flags": [{"quote": q, "label": l, "speaker": "guest", "reason": "r", "confidence": c}
                          for q, l, c in FLAGS],
                "claims": [{"quote": q, "speaker": "guest", "queries": [q]} for q in CLAIMS]}


def test_pick_threshold(tmp_path):
    golden = tmp_path / "golden"
    golden.mkdir()
    (golden / "bars.json").write_text(json.dumps(DIALOGUE, ensure_ascii=False))
    saved = tmp_path / "thresholds.json"

    report = run_eval(golden, llm=BarsModel(), factcheck=NoPublishedChecks(), save_to=saved)

    # Case 1 · fallacies right at 0.9 and 0.85, wrong at 0.7 → the lowest bar with precision ≥ 0.80 is 0.85
    assert report["fallacy"]["bar"] == 0.85

    # Case 2 · five inaccuracy flags, all wrong → no bar: "never"
    assert report["inaccuracy"]["bar"] is None

    # Case 3 · with save → the thresholds file holds fallacy 0.85 and inaccuracy null
    assert json.loads(saved.read_text()) == {"fallacy": 0.85, "inaccuracy": None}
    print("PASS S3 A3 · The eval picks the bar per type and saves it")


# S4 A3 · The eval prints the real precision from the marks
#
# Story: The marks log holds 3 evasion marks (1 correct, 2 unfair) and 4 inaccuracy marks (3 correct,
# 1 unfair). The person runs the eval of marks and reads: fallacy 33% (1 of 3), with evasion 33% (1 of 3)
# under it; inaccuracy 75% (3 of 4).
#
# Setup: a temporary helper home with a marks log; one inaccuracy flag was first marked unfair and then
# correct, so only its latest mark counts.

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


# S8 A3 · The eval scores contradictions
#
# Story: The person runs the eval. The golden dialogues now hold planted contradictions, and the printed
# table has a contradiction row with its precision and recall next to the fallacy and inaccuracy rows.
#
# Setup: the real golden dialogues of tests/golden. A fake Claude that, in each part call, lists every
# planted contradiction and every contradiction decoy (a decoy with a "related" statement) whose second
# statement is in that PART, each pinned on the speaker of its golden line; planted ones at confidence 0.9,
# decoys at 0.6; it lists no fallacy, claim or question. No fact-check service.

def norm(text):
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())


GOLDEN_DIALOGUES = [json.loads(p.read_text()) for p in sorted(GOLDEN.glob("*.json"))]
PLANTED = [(d, e) for d in GOLDEN_DIALOGUES for e in d["expected"] if e["type"] == "contradiction"]
DECOYS = [(d, e) for d in GOLDEN_DIALOGUES for e in d["decoys"] if "related" in e]


def line_of(dialogue, quote):
    return next(line for line in dialogue["lines"] if norm(quote) in norm(line["text"]))


def same_speaker(dialogue, item):
    return line_of(dialogue, item["quote"])["speaker"] == line_of(dialogue, item["related"])["speaker"]


def contradiction(dialogue, item, confidence):
    return {"quote": item["quote"], "earlier": item["related"],
            "speaker": line_of(dialogue, item["quote"])["speaker"],
            "earlier_speaker": line_of(dialogue, item["related"])["speaker"],
            "reason": "Dice lo contrario de lo que dijo antes.", "confidence": confidence}


CONTRADICTIONS = [contradiction(d, e, 0.9) for d, e in PLANTED] + [contradiction(d, e, 0.6) for d, e in DECOYS]


class ContradictionModel:
    def complete(self, prompt, schema, tools=()):
        part = norm(prompt.split("PART:")[-1])
        return {"flags": [], "claims": [], "questions": [],
                "contradictions": [dict(c) for c in CONTRADICTIONS if norm(c["quote"]) in part]}


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

    report = run_eval(GOLDEN, llm=ContradictionModel(), factcheck=None)
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
