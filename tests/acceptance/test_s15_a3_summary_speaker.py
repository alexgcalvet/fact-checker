"""S15 A3 · The shareable summary takes the speaker from the judge

Story: A flag marked correct that the judge gave from "Luis" to "Ana Ruiz" appears in Ana Ruiz's column of the
summary image, and a flag the judge dropped and the person never marked appears nowhere.
The person's mark wins: a flag the judge dropped and the person marked correct stays.

Setup: an invented flag file as GET /videos/<id> returns it (each flag with its latest mark and its `judge`
field), with two speakers, passed to fact_checker.core.summary.summarize and alt_text.
"""
import json

from fact_checker.core.summary import alt_text, summarize

HOST = "Luis (presentador)"
GUEST = "Ana Ruiz (invitada)"


def flag(id, t, speaker, type, label, judge=None, mark=None):
    f = {"id": id, "t": t, "speaker": speaker, "quote": f"frase inventada {id}", "type": type, "label": label,
         "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "sources": [], "note": None,
         "on_player": True}
    if judge:
        f["judge"] = judge
    return f | {"mark": mark} if mark else f


DATA = {"video_id": "abcdefgh", "published_at": "2026-11-10", "status": "done", "stop_reason": None,
        "title": "Entrevista inventada", "channel": "Canal de prueba", "duration": 600.0,
        "speakers": {"SPEAKER_00": HOST, "SPEAKER_01": GUEST},
        "flags": [
            flag("ad_hominem-60.0", 60, HOST, "fallacy", "ad_hominem",
                 {"verdict": "keep", "reason": "Lo dice el invitado.", "speaker": GUEST}, "correct"),
            flag("false-120.0", 120, GUEST, "inaccuracy", "false", {"verdict": "drop", "reason": "Error menor."}),
            flag("false-180.0", 180, GUEST, "inaccuracy", "false", {"verdict": "drop", "reason": "Error menor."},
                 "correct"),
        ]}


def test_summary_speaker():
    s = summarize(DATA)
    columns = {c["name"]: c for c in s["speakers"]}

    # Case 1 · a flag marked correct that the judge gave from Luis to Ana Ruiz → in Ana Ruiz's column, not Luis's
    assert "ad_hominem-60.0" in [f["id"] for f in columns[GUEST]["flags"]]
    assert "ad_hominem-60.0" not in [f["id"] for f in columns[HOST]["flags"]]
    assert columns[GUEST]["counts"] == {"false": 1, "fallacy": 1}
    assert columns[HOST]["counts"] == {}

    # Case 2 · the alt text → the fallacy's quote under Ana Ruiz's line
    alt = alt_text(s)
    assert "frase inventada ad_hominem-60.0" in alt.split(GUEST, 1)[1]
    assert "frase inventada ad_hominem-60.0" not in alt.split(HOST, 1)[1].split(GUEST, 1)[0]

    # Case 3 · a flag the judge dropped and the person never marked → nowhere in the summary or the alt text
    assert "false-120.0" not in json.dumps(s, ensure_ascii=False)
    assert "frase inventada false-120.0" not in alt_text(s)

    # Case 4 · a flag the judge dropped and the person marked correct → still in its speaker's column
    assert "false-180.0" in [f["id"] for f in columns[GUEST]["flags"]]
    print("PASS S15 A3 · The shareable summary takes the speaker from the judge")
