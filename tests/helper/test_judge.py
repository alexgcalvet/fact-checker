"""The judge: one reading of the whole transcript that rules on every flag before the file says done."""
import json
import re
import sys
from pathlib import Path

from fact_checker import cli, server
from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import judged, run_analysis
from judge_fakes import DISPUTED_ID, FakeJudge, FALLACY_ID, FALSE_ID, FLAGS, REPROACH_ID, SELF_ID, transcript
from screen_fakes import fake_clis, fake_video, jsonl


# S15 A1 · The judge rules on every flag once the analysis ends
#
# Story: The helper analyses an invented 10-minute interview with a fallacy, a false figure, a disputed figure and
# a context card. Before the flag file says done, one more Claude reading gets the whole transcript with speakers
# and minutes and the three non-context flags. In the done file, the fallacy keeps its verdict, the false figure
# says "puntualización: 49,8 M frente a 49,4 M, el fondo se sostiene", the disputed figure is kept (S32), and the
# fallacy passes from "Luis" to "Ana Ruiz"; each original label, speaker and reason is still there.
# Edge case: WHEN the judge's Claude reading fails THEN the file still ends done, with the flags as found and no
# verdicts.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 10-minute interview, each line in the voice of
# SPEAKER_00 ("Luis") or SPEAKER_01 ("Ana Ruiz"); the fallacy sits in a line that the voices give to Luis. A fake
# Fact Check Tools API that finds nothing. A fake Claude that answers each part call with the flag, claim and
# context of that part, each fact-check call with a false verdict (one tier-1 measure against) and a disputed one
# (one measure for, one against), and the judge call (the call whose schema has `rulings`) with: keep the fallacy
# and give it to "Ana Ruiz", "nitpick" the false figure, answer "drop" for the disputed one. The judge call records its prompt,
# its tools and the file status at that moment. A second fake judge raises an error; a third run has a sparse
# 2.5-hour interview. A temporary helper home.

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALLACY = "ustedes no tienen ninguna autoridad moral para hablar de nada"
FALSE = "España recibió cuarenta y nueve coma ocho millones de turistas"
DISPUTED = "el paro juvenil es el más alto de toda Europa"
NAME = "Marta Gil"
NITPICK = "49,8 M frente a 49,4 M, el fondo se sostiene"
LINES = [
    (0, HOST, "Buenas noches hoy entrevistamos al líder de la oposición"),
    (60, GUEST, f"Gracias Luis el ministro {NAME} no ha resuelto nada"),
    (180, HOST, FALLACY),
    (300, GUEST, FALSE),
    (420, GUEST, DISPUTED),
    (590, HOST, "Muchas gracias por venir y buenas noches"),
]


# The same interview over 2.5 hours: the false and the disputed figures after the second hour.
LONG = LINES[:3] + [(7500, GUEST, FALSE), (8000, GUEST, DISPUTED), (9000, HOST, LINES[-1][2])]


def ids(lines):
    start = {text: t for t, _, text in lines}
    return {"fallacy": f"ad_hominem-{start[FALLACY]:.1f}", "false": f"false-{start[FALSE]:.1f}",
            "disputed": f"disputed-{start[DISPUTED]:.1f}"}


IDS = ids(LINES)


class FakeTranscript:
    def __init__(self, lines=LINES):
        self.lines = lines

    def fetch(self, video_id):
        segments = [Segment(t=t + i * 0.5, text=w, speaker=voice)
                    for t, voice, text in self.lines for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Luis", GUEST: "Ana Ruiz"})


class NoPublishedChecks:
    def search(self, query, language):
        return []


def measure(supports, tier=1):
    return {"name": "medida inventada", "value": "1", "source": "INE", "tier": tier, "supports": supports}


def verdict(quote, measures):
    return {"quote": quote, "verdict": "false", "reason": "Las fuentes dan otra cifra.", "confidence": 0.9,
            "sources": [{"publisher": "INE", "url": f"https://www.ine.es/{len(quote)}", "date": "2026-10-01"}],
            "note": None, "published": [], "measures": measures, "controversy": None}


class FakeClaude:
    def __init__(self, home, video_id, ids, judge_fails=False):
        self.home, self.video_id, self.ids, self.judge_fails = home, video_id, ids, judge_fails
        self.judge_calls = []

    def complete(self, prompt, schema, tools=()):
        if "rulings" in schema["properties"]:
            status = json.loads((self.home / "videos" / f"{self.video_id}.json").read_text())["status"]
            self.judge_calls.append({"prompt": prompt, "tools": tools, "status": status})
            if self.judge_fails:
                raise RuntimeError("claude -p error: overloaded")
            return {"rulings": [
                {"id": self.ids["fallacy"], "verdict": "keep", "reason": "El ataque es suyo y no argumenta.",
                 "speaker": "Ana Ruiz"},
                {"id": self.ids["false"], "verdict": "nitpick", "reason": NITPICK, "speaker": None},
                {"id": self.ids["disputed"], "verdict": "drop", "reason": "Una medida creíble lo respalda.",
                 "speaker": None},
            ]}
        if "verdicts" in schema["properties"]:
            return {"verdicts": [verdict(FALSE, [measure(False)]),
                                 verdict(DISPUTED, [measure(False), measure(True, tier=2)])]}
        part = prompt.split("PART:")[-1]
        return {
            "flags": [{"quote": FALLACY, "label": "ad_hominem", "closest": "ad_hominem", "speaker": "Luis",
                       "reason": "Ataca a la persona.", "confidence": 0.9}] if FALLACY in part else [],
            "claims": [{"quote": q, "speaker": "Ana Ruiz", "queries": [q], "question": None, "kind": "fact"}
                       for q in (FALSE, DISPUTED) if q in part],
            "questions": [], "contradictions": [],
            "context": [{"name": NAME, "kind": "person", "speaker": "Ana Ruiz",
                         "sentence": "Ministro de Transportes.", "confidence": 0.95}] if NAME in part else [],
        }


def analyse(home, judge_fails=False, lines=LINES):
    claude = FakeClaude(home, "entrevista", ids(lines), judge_fails)
    run_analysis("entrevista", 0, transcript=FakeTranscript(lines), llm=claude, judge=claude,
                 factcheck=NoPublishedChecks(), home=home)
    return json.loads((home / "videos" / "entrevista.json").read_text()), claude.judge_calls


def test_judge_verdicts(tmp_path):
    data, calls = analyse(tmp_path)
    flags = {f["id"]: f for f in data["flags"]}
    assert set(IDS.values()) <= set(flags), list(flags)

    # Case 1 · the analysis of every part ends → one Claude reading, without web tools, before the file says done
    assert len(calls) == 1, calls
    assert calls[0]["tools"] == ()
    assert calls[0]["status"] == "running"
    assert data["status"] == "done"

    # Case 2 · the judge's reading → the whole transcript with speakers and minutes, and the three non-context flags
    prompt = calls[0]["prompt"]
    for _, _, text in LINES:
        assert text in prompt, text
    # The judge reads blind (2026-11-16): each speaker as a label with no name, such as "Speaker 2".
    assert re.search(rf"5:00\W+Speaker \d+\W+{FALSE}", prompt), "no speaker and minute on the 5:00 line"
    assert "Ana Ruiz" not in prompt.split("CONVERSATION")[-1], "the judge reads the guest's name"
    assert re.search(rf"9:50\W+Speaker \d+\W+Muchas gracias", prompt), "no speaker and minute on the 9:50 line"
    for id in IDS.values():
        assert id in prompt, id
    context = [f for f in data["flags"] if f["type"] == "context"]
    assert context and context[0]["id"] not in prompt

    # Case 3 · the fallacy → keeps its verdict and passes from Luis to Ana Ruiz, the original speaker kept
    fallacy = flags[IDS["fallacy"]]
    assert fallacy["judge"]["verdict"] == "keep"
    assert fallacy["judge"]["speaker"] == "Ana Ruiz"
    assert (fallacy["speaker"], fallacy["label"], fallacy["reason"]) == ("Luis", "ad_hominem", "Ataca a la persona.")

    # Case 4 · the false figure → "puntualización" with the judge's reason; still labelled false
    false = flags[IDS["false"]]
    assert false["judge"]["verdict"] == "nitpick"
    assert false["judge"]["reason"] == NITPICK
    assert (false["label"], false["speaker"], false["reason"]) == ("false", "Ana Ruiz", "Las fuentes dan otra cifra.")

    # Case 5 · the judge answers "drop" for the disputed figure → kept (S32: the judge drops no flag)
    disputed = flags[IDS["disputed"]]
    assert disputed["judge"]["verdict"] == "keep"
    assert disputed["label"] == "disputed"

    # Case 6 · the context card → no verdict
    assert "judge" not in context[0]
    print("PASS S15 A1 · The judge rules on every flag once the analysis ends")


def test_judge_fails(tmp_path):
    data, calls = analyse(tmp_path, judge_fails=True)

    # Case 7 · the judge's Claude reading fails → the file still ends done, with the flags as found and no verdicts
    assert len(calls) == 1
    assert data["status"] == "done", data["stop_reason"]
    assert set(IDS.values()) <= {f["id"] for f in data["flags"]}
    assert not [f for f in data["flags"] if "judge" in f]
    print("PASS S15 A1 · a failed judge leaves the file done with the flags as found")


def test_one_reading_per_two_hours(tmp_path):
    data, calls = analyse(tmp_path, lines=LONG)

    # Case 8 · a 2.5-hour interview → one judge reading per started two hours, each flag judged in one of them
    assert len(calls) == 2, len(calls)
    judged = [f for f in data["flags"] if "judge" in f]
    assert {f["id"] for f in judged} == set(ids(LONG).values()), judged
    for f in judged:
        assert sum(f["id"] in c["prompt"] for c in calls) == 1, f["id"]
    print("PASS S15 A1 · one judge reading per started two video-hours")


# S32 A1 · The judge drops no flag
#
# Story: The helper judges an invented interview with a fallacy, a false figure and a disputed figure. The judge's
# reading is offered only "keep" and "nitpick" and is told that it never drops a flag. When it still answers "drop" for
# the disputed figure, as a provider that ignores the schema can, the flag file shows that figure as "keep" with the
# judge's reason, and no flag says dropped.
#
# Setup: the invented interview of judge_fakes and its flags. A fake judge LLM that keeps the fallacy, nitpicks the false
# figure and answers "drop" for the disputed figure and for the self-contradiction. The helper's judge step, the one that
# runs before the flag file says done.

DROP_REASON = "Una medida creíble lo respalda."


def test_judge_drops_nothing():
    llm = FakeJudge({FALLACY_ID: ("keep", "El ataque es suyo y no argumenta.", None),
                     FALSE_ID: ("nitpick", "49,8 M frente a 49,4 M, el fondo se sostiene", None),
                     DISPUTED_ID: ("drop", DROP_REASON, None),
                     SELF_ID: ("drop", "Habla de otro impuesto.", None)})
    flags = {f["id"]: f for f in judged(FLAGS, transcript(), llm)}
    assert len(llm.calls) == 1

    # Case 1 · the judge's reading → offered only "keep" and "nitpick", and told it never drops a flag
    verdicts = llm.calls[0]["schema"]["properties"]["rulings"]["items"]["properties"]["verdict"]["enum"]
    assert sorted(verdicts) == ["keep", "nitpick"], verdicts
    prompt = llm.calls[0]["prompt"]
    assert '"drop"' not in prompt and "drop it" not in prompt and "is dropped" not in prompt
    assert "never drop" in prompt.lower(), "the prompt does not say that the judge never drops a flag"

    # Case 2 · the judge still answers "drop" for the disputed figure → "keep", with the judge's reason
    assert flags[DISPUTED_ID]["judge"]["verdict"] == "keep", flags[DISPUTED_ID]["judge"]
    assert flags[DISPUTED_ID]["judge"]["reason"] == DROP_REASON
    assert flags[DISPUTED_ID]["label"] == "disputed"

    # Case 3 · the whole file → no flag says dropped; keep and nitpick stay as ruled
    assert not [f for f in flags.values() if f.get("judge", {}).get("verdict") == "drop"], json.dumps(flags)
    assert flags[FALLACY_ID]["judge"]["verdict"] == "keep"
    assert flags[FALSE_ID]["judge"]["verdict"] == "nitpick"
    print("PASS S32 A1 · The judge drops no flag")


# S32 A2 · A small slip of any kind becomes a "Puntualización"
#
# Story: In the same interview, the judge rules "nitpick" on the fallacy ("el ataque es leve, lo matiza en la frase
# siguiente") and on a self-contradiction. The flag file keeps both as "nitpick" with those reasons, so the player shows
# them as grey "Puntualización" cards; each original label and reason is still there.
#
# Setup: the invented interview of judge_fakes and its flags. A fake judge LLM that nitpicks the guest's fallacy and the
# self-contradiction and keeps the rest. The helper's judge step, the one that runs before the flag file says done.

SOFT = "el ataque es leve, lo matiza en la frase siguiente"
RECONCILED = "lo explica ella: la subida fue temporal"


def test_nitpick_any_type():
    llm = FakeJudge({FALLACY_ID: ("nitpick", SOFT, None), SELF_ID: ("nitpick", RECONCILED, None)})
    flags = {f["id"]: f for f in judged(FLAGS, transcript(), llm)}
    found = {f["id"]: f for f in FLAGS}

    # Case 1 · a nitpick on a fallacy → stays "nitpick" with the judge's reason; label and reason as found
    fallacy = flags[FALLACY_ID]
    assert fallacy["judge"] == {"verdict": "nitpick", "reason": SOFT}, fallacy["judge"]
    assert (fallacy["label"], fallacy["reason"]) == ("ad_hominem", found[FALLACY_ID]["reason"])

    # Case 2 · a nitpick on a self-contradiction → stays "nitpick" with the judge's reason; label and reason as found
    contradiction = flags[SELF_ID]
    assert contradiction["judge"] == {"verdict": "nitpick", "reason": RECONCILED}, contradiction["judge"]
    assert (contradiction["label"], contradiction["reason"]) == ("self", found[SELF_ID]["reason"])
    print('PASS S32 A2 · A small slip of any kind becomes a "Puntualización"')


# S32 A3 · A speaker fix rules out an unfair flag in the marks check
#
# Story: The person runs `fact-checker judge <video id> --against-marks` on an invented analysed interview. They marked
# unfair one flag that gives the host's words to the guest, and marked two flags correct. The judge gives the unfair one
# to the host and keeps the other two. The check prints "marked unfair, nitpicked or given to another speaker: 1 of 1"
# and "marked correct, touched: 0 of 2".
#
# Setup: a temporary helper home with the flag file of the invented interview of judge_fakes and three marks: the host's
# reproach given to the guest unfair, the guest's fallacy and the false figure correct. A fake YouTube that serves the
# interview, no speech engine, and a fake judge LLM in place of the provider: it gives the reproach to "Presentadora"
# and keeps the fallacy and the false figure.

VIDEO = "entrevista-inventada"


class FakeYouTube:
    def __init__(self, workdir, speech=None):
        pass

    def fetch(self, video_id):
        return transcript()


def test_marks_speaker_fix(tmp_path, monkeypatch, capsys):
    (tmp_path / "videos").mkdir()
    tr = transcript()
    (tmp_path / "videos" / f"{VIDEO}.json").write_text(json.dumps(
        {"video_id": VIDEO, "status": "done", "speakers": tr.speakers, "lang": "es", "flags": FLAGS}))
    (tmp_path / "marks.jsonl").write_text("".join(
        json.dumps({"video_id": VIDEO, "flag_id": i, "verdict": v}) + "\n"
        for i, v in ((REPROACH_ID, "unfair"), (FALLACY_ID, "correct"), (FALSE_ID, "correct"))))
    llm = FakeJudge({REPROACH_ID: ("keep", "Lo dice la presentadora.", "Presentadora"),
                     FALLACY_ID: ("keep", "El ataque es suyo.", None),
                     FALSE_ID: ("keep", "La cifra es otra.", None)})
    monkeypatch.setattr(cli, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "speech_cli", lambda: None)
    monkeypatch.setattr(server, "provider_llm", lambda home, name, **options: llm)

    cli.run_judge(VIDEO, tmp_path, against_marks=True)
    out = capsys.readouterr().out
    saved = {f["id"]: f for f in json.loads((tmp_path / "videos" / f"{VIDEO}.json").read_text())["flags"]}

    # Case 1 · the unfair flag given to the host → written to the file and counted as ruled out
    assert saved[REPROACH_ID]["judge"]["speaker"] == "Presentadora"
    assert "marked unfair, nitpicked or given to another speaker: 1 of 1" in out, out

    # Case 2 · the two flags marked correct and kept as found → not touched
    assert "marked correct, touched: 0 of 2" in out, out
    print("PASS S32 A3 · A speaker fix rules out an unfair flag in the marks check")


# S34 A1 · The judge rules a severity on each flag it keeps
#
# Story: The person runs the judge on an invented interview with three flags. The judge keeps a false figure as serious,
# keeps a weak generalisation as minor and turns a near date into a puntualización. The flag file holds `serious` and
# `minor` on the two kept flags and no severity on the puntualización.
# Edge case: when a provider answers a kept flag with no severity or an unknown one, the flag is kept with no severity.
#
# Setup: an invented 3-minute interview of one guest ("Ana Ruiz") with five flags as the parts found them: a false
# figure, a weak generalisation, a near date, and two more false figures for the edge case. A fake judge LLM that answers
# with the rulings it is given (it also sends a severity on the puntualización, as a careless provider can) and records
# each prompt and schema. The helper's judge step, the one that runs before the flag file says done.

GUEST_s34a1 = "SPEAKER_00"
LINES_s34a1 = [(0, "el paro bajó a la mitad en un solo año"), (40, "todos los jóvenes se van del país"),
         (80, "la ley se aprobó en marzo de 2019"), (120, "la deuda pública es del doscientos por ciento"),
         (160, "los precios subieron un cuarenta por ciento")]


def transcript_s34a1() -> Transcript:
    return Transcript(segments=[Segment(t=t, text=text, speaker=GUEST_s34a1) for t, text in LINES_s34a1],
                      published_at="2026-11-10", speakers={GUEST_s34a1: "Ana Ruiz"})


def flag(t, label, type="inaccuracy"):
    return {"id": f"{label}-{t:.1f}", "t": float(t), "speaker": "Ana Ruiz", "quote": dict(LINES_s34a1)[t], "type": type,
            "label": label, "reason": f"Motivo inventado del segundo {t}.", "confidence": 0.9}


FLAGS_s34a1 = [flag(0, "false"), flag(40, "hasty_generalization", "fallacy"), flag(80, "false"), flag(120, "false"),
         flag(160, "false")]
FALSE_ID_s34a1, WEAK_ID, DATE_ID, NONE_ID, ODD_ID = (f["id"] for f in FLAGS_s34a1)
RULINGS = {FALSE_ID_s34a1: ("keep", "Bajó del 12 % al 11 %, no a la mitad.", "serious"),
           WEAK_ID: ("keep", "Generaliza desde unos pocos casos.", "minor"),
           DATE_ID: ("nitpick", "Se aprobó en abril de 2019", "moderate"),
           NONE_ID: ("keep", "Es del 110 %.", None),
           ODD_ID: ("keep", "Subieron un 14 %.", "huge")}


class FakeJudge_s34a1:
    """Answers each judge reading with RULINGS: flag id → (verdict, reason, severity)."""

    def __init__(self):
        self.calls = []

    def complete(self, prompt, schema, tools=()):
        self.calls.append({"prompt": str(prompt), "schema": schema})
        return {"rulings": [{"id": i, "verdict": v, "reason": r, "speaker": None, "severity": s}
                            for i, (v, r, s) in RULINGS.items()]}


def test_severity_on_keep():
    llm = FakeJudge_s34a1()
    flags = {f["id"]: f for f in judged(FLAGS_s34a1, transcript_s34a1(), llm)}
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
    assert flags[FALSE_ID_s34a1]["judge"] == {"verdict": "keep", "reason": RULINGS[FALSE_ID_s34a1][1], "severity": "serious"}

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


# The judge reads even when the parts and fact checks spent the whole call budget, and a failed judge leaves a line.
#
# A 1 h 52 min interview with many checked figures once used every call before the judge, which then ruled on nothing
# and logged nothing.

VIDEO_judge_own_budget = "presupuesto1"


def run(tmp_path, monkeypatch) -> tuple[list[dict], dict]:
    fake_video(monkeypatch)
    home = tmp_path / "home"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    claude_log, _ = fake_clis(tmp_path / "run", monkeypatch)
    monkeypatch.setattr(sys, "argv", ["fact-checker", "analyze", f"https://www.youtube.com/watch?v={VIDEO_judge_own_budget}"])
    cli.main()
    return jsonl(home / "usage.log"), json.loads((home / "videos" / f"{VIDEO_judge_own_budget}.json").read_text())


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
