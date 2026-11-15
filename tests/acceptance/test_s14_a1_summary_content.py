"""S14 A1 · The summary keeps each speaker's most serious reviewed flags

Story: A flag file with two speakers holds, for the guest, a false figure, a dodged question, a contradiction,
a disputed figure and a fallacy marked correct, plus a false figure marked unfair; the host has one fallacy
marked correct. The summary has two columns: the guest's lists the false figure, the contradiction and the
dodged question, in that order, with counts of every reviewed type; the host's lists the fallacy. The unfair
flag appears nowhere.
Edge case: WHEN the video has five speakers THEN the four who speak most get a box with up to two flags each,
and the footer says "y 1 más".

Setup: invented flag files as GET /videos/<id> returns them (each flag with its latest mark), passed to
fact_checker.core.summary.summarize. "Who speaks most" is the number of flags of each speaker in the file,
any type and any mark.
"""
import json

from fact_checker.core.summary import alt_text, summarize

GUEST = "Ana Ruiz (invitada)"
HOST = "Luis Gil (presentador)"


def flag(id, t, speaker, type, label, mark=None, confidence=0.9):
    f = {"id": id, "t": t, "speaker": speaker, "quote": f"frase inventada {id}", "type": type, "label": label,
         "reason": "Motivo inventado.", "confidence": confidence, "related": None, "sources": [], "note": None,
         "on_player": True}
    return f | {"mark": mark} if mark else f


def flag_file(flags, speakers):
    return {"video_id": "abcdefgh", "published_at": "2026-11-10", "status": "done", "stop_reason": None,
            "title": "Entrevista inventada", "channel": "Canal de prueba", "duration": 3600.0,
            "speakers": speakers, "flags": flags}


TWO = flag_file([
    flag("fallacy-60.0", 60, GUEST, "fallacy", "ad_hominem", "correct"),
    flag("disputed-120.0", 120, GUEST, "inaccuracy", "disputed", "correct"),
    flag("question-180.0", 180, GUEST, "question", "dodged", "correct"),
    flag("contradiction-240.0", 240, GUEST, "contradiction", "self", "correct"),
    flag("false-300.0", 300, GUEST, "inaccuracy", "false", "correct"),
    flag("false-360.0", 360, GUEST, "inaccuracy", "false", "unfair", confidence=0.99),
    flag("false-420.0", 420, GUEST, "inaccuracy", "false"),
    flag("context-30.0", 30, GUEST, "context", "person", "correct"),
    flag("fallacy-500.0", 500, HOST, "fallacy", "straw_man", "correct"),
], {"SPEAKER_00": HOST, "SPEAKER_01": GUEST})


def test_two_speakers():
    s = summarize(TWO)
    columns = {c["name"]: c for c in s["speakers"]}

    # Case 1 · two speakers with reviewed flags → two columns, one per speaker
    assert set(columns) == {GUEST, HOST}

    # Case 2 · the guest's column → false figure, contradiction, dodged question, in that order
    assert [f["id"] for f in columns[GUEST]["flags"]] == ["false-300.0", "contradiction-240.0", "question-180.0"]

    # Case 3 · the guest's counts → one of every reviewed type, context left out
    assert columns[GUEST]["counts"] == {"false": 1, "contradiction": 1, "question": 1, "disputed": 1, "fallacy": 1}

    # Case 4 · the host's column → the fallacy only
    assert [f["id"] for f in columns[HOST]["flags"]] == ["fallacy-500.0"]
    assert columns[HOST]["counts"] == {"fallacy": 1}

    # Case 5 · the flag marked unfair and the unmarked one → nowhere in the summary or the alt text
    for id in ("false-360.0", "false-420.0", "context-30.0"):
        assert id not in json.dumps(s, ensure_ascii=False)
    assert "false-360.0" not in alt_text(s) and "frase inventada false-360.0" not in alt_text(s)
    assert "frase inventada false-300.0" in alt_text(s)
    assert s["more"] == 0 and "más" not in s["footer"]
    print("PASS S14 A1 · The summary keeps each speaker's most serious reviewed flags")


def test_five_speakers():
    names = [f"Persona {n}" for n in "ABCDE"]
    flags = []
    # A to D each have three reviewed fallacies; E has one flag, so E speaks least.
    for n, name in enumerate(names[:4]):
        flags += [flag(f"fallacy-{n}{k}", n * 100 + k, name, "fallacy", "ad_hominem", "correct") for k in range(3)]
    flags.append(flag("false-999.0", 999, names[4], "inaccuracy", "false", "correct"))
    s = summarize(flag_file(flags, {f"SPEAKER_0{n}": name for n, name in enumerate(names)}))

    # Case 6 · five speakers → the four who speak most get a box with up to two flags each
    assert {c["name"] for c in s["speakers"]} == set(names[:4])
    assert all(len(c["flags"]) == 2 for c in s["speakers"])

    # Case 7 · the fifth speaker → left out, and the footer says "y 1 más"
    assert s["more"] == 1 and "y 1 más" in s["footer"]
    print("PASS S14 A1 · five speakers: four boxes and y 1 más")
