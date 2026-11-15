"""S15 A3 · The shareable card takes the speaker from the judge

Story: A flag marked correct that the judge gave from "Luis" to "Ana Ruiz" appears on Ana Ruiz's card, and a flag the
judge dropped and the person never marked appears nowhere.
The person's mark wins: a flag the judge dropped and the person marked correct stays.

Setup: an invented flag file as GET /videos/<id> returns it (each flag with its latest mark and its `judge`
field), with two speakers and no `people`, so each speaker gets a card; passed to fact_checker.core.summary.card and
alt_text (S35).
"""
import json

from fact_checker.core.summary import alt_text, card

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
    guest, host = card(DATA, GUEST), card(DATA, HOST)

    # Case 1 · a flag marked correct that the judge gave from Luis to Ana Ruiz → on Ana Ruiz's card, not Luis's
    assert guest["devices"] == [("Ad hominem", 1)], f"FAIL S15 A3 · Ana Ruiz's devices {guest['devices']}"
    assert host["devices"] == [] and host["wrong"] == 0, f"FAIL S15 A3 · Luis's card {host}"

    # Case 2 · the alt text → the fallacy on Ana Ruiz's alt text only
    assert "Ad hominem ×1" in alt_text(guest), f"FAIL S15 A3 · {alt_text(guest)!r}"
    assert "Ad hominem" not in alt_text(host), f"FAIL S15 A3 · {alt_text(host)!r}"

    # Case 3 · a flag the judge dropped and the person never marked → nowhere on the card or the alt text
    assert "frase inventada false-120.0" not in json.dumps(guest, ensure_ascii=False) + alt_text(guest)

    # Case 4 · a flag the judge dropped and the person marked correct → still on its speaker's card
    assert guest["wrong"] == 1 and [g["quote"] for g in guest["gravest"]] == ["frase inventada false-180.0"], \
        f"FAIL S15 A3 · Ana Ruiz's false figures {guest['gravest']}"
    print("PASS S15 A3 · The shareable card takes the speaker from the judge")
