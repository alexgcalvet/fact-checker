"""S34 A1 · The judge rules a severity on each flag it keeps

Story: The person runs the judge on an invented interview with three flags. The judge keeps a false figure as serious,
keeps a weak generalisation as minor and turns a near date into a puntualización. The flag file holds `serious` and
`minor` on the two kept flags and no severity on the puntualización.
Edge case: when a provider answers a kept flag with no severity or an unknown one, the flag is kept with no severity.

Setup: an invented 3-minute interview of one guest ("Ana Ruiz") with five flags as the parts found them: a false
figure, a weak generalisation, a near date, and two more false figures for the edge case. A fake judge LLM that answers
with the rulings it is given (it also sends a severity on the puntualización, as a careless provider can) and records
each prompt and schema. The helper's judge step, the one that runs before the flag file says done.
"""
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import judged

GUEST = "SPEAKER_00"
LINES = [(0, "el paro bajó a la mitad en un solo año"), (40, "todos los jóvenes se van del país"),
         (80, "la ley se aprobó en marzo de 2019"), (120, "la deuda pública es del doscientos por ciento"),
         (160, "los precios subieron un cuarenta por ciento")]


def transcript() -> Transcript:
    return Transcript(segments=[Segment(t=t, text=text, speaker=GUEST) for t, text in LINES],
                      published_at="2026-11-10", speakers={GUEST: "Ana Ruiz"})


def flag(t, label, type="inaccuracy"):
    return {"id": f"{label}-{t:.1f}", "t": float(t), "speaker": "Ana Ruiz", "quote": dict(LINES)[t], "type": type,
            "label": label, "reason": f"Motivo inventado del segundo {t}.", "confidence": 0.9}


FLAGS = [flag(0, "false"), flag(40, "hasty_generalization", "fallacy"), flag(80, "false"), flag(120, "false"),
         flag(160, "false")]
FALSE_ID, WEAK_ID, DATE_ID, NONE_ID, ODD_ID = (f["id"] for f in FLAGS)
RULINGS = {FALSE_ID: ("keep", "Bajó del 12 % al 11 %, no a la mitad.", "serious"),
           WEAK_ID: ("keep", "Generaliza desde unos pocos casos.", "minor"),
           DATE_ID: ("nitpick", "Se aprobó en abril de 2019", "moderate"),
           NONE_ID: ("keep", "Es del 110 %.", None),
           ODD_ID: ("keep", "Subieron un 14 %.", "huge")}


class FakeJudge:
    """Answers each judge reading with RULINGS: flag id → (verdict, reason, severity)."""

    def __init__(self):
        self.calls = []

    def complete(self, prompt, schema, tools=()):
        self.calls.append({"prompt": str(prompt), "schema": schema})
        return {"rulings": [{"id": i, "verdict": v, "reason": r, "speaker": None, "severity": s}
                            for i, (v, r, s) in RULINGS.items()]}


def test_severity_on_keep():
    llm = FakeJudge()
    flags = {f["id"]: f for f in judged(FLAGS, transcript(), llm)}
    assert len(llm.calls) == 1

    # Case 1 · the judge's reading → offered the three levels and told the rubric: by the point, never by intent
    item = llm.calls[0]["schema"]["properties"]["rulings"]["items"]
    assert "severity" in item["properties"] and "severity" in item["required"], item
    levels = [v for v in item["properties"]["severity"].get("enum", []) if v is not None]
    assert sorted(levels) == ["minor", "moderate", "serious"], levels
    prompt = llm.calls[0]["prompt"].lower()
    for word in ("moderate", "serious", "central", "intent"):
        assert word in prompt, f"the prompt does not name {word!r}"

    # Case 2 · the false figure kept as serious → `serious` in its verdict
    assert flags[FALSE_ID]["judge"] == {"verdict": "keep", "reason": RULINGS[FALSE_ID][1], "severity": "serious"}

    # Case 3 · the weak generalisation kept as minor → `minor` in its verdict
    assert flags[WEAK_ID]["judge"]["verdict"] == "keep"
    assert flags[WEAK_ID]["judge"]["severity"] == "minor"

    # Case 4 · the near date turned into a puntualización → no severity, even though the provider sent one
    assert flags[DATE_ID]["judge"]["verdict"] == "nitpick"
    assert "severity" not in flags[DATE_ID]["judge"], flags[DATE_ID]["judge"]

    # Case 5 · a kept flag with no severity or an unknown one → kept, with no severity
    for i in (NONE_ID, ODD_ID):
        assert flags[i]["judge"]["verdict"] == "keep"
        assert "severity" not in flags[i]["judge"], flags[i]["judge"]
    print("PASS S34 A1 · The judge rules a severity on each flag it keeps")
