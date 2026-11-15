"""S33 A1 · Each voice gets a role, a person and its seconds of speech

Story: The person analyses an invented interview where the host opens with "Buenos días, hoy está con nosotros Ana
Ruiz". The flag file lists the host as `host` and Ana Ruiz as `guest` with the person "Ana Ruiz", and the seconds each
one speaks, for example 1260 and 2460.
Edge case: WHEN the voices cannot be separated THEN the file has no people, and the export gives a card for every speaker
(S35).

Setup: the invented interview of s33_fakes, with the title "Entrevista inventada a Ana Ruiz"; voice turns that give the
host 1260 s, Ana Ruiz 2460 s and a third voice 30 s; a fake model that names the host "Presentador" (role host, person
"Presentador") and the guest "Ana Ruiz (invitada)" (role guest, person "Ana Ruiz"); a temporary helper home. The edge
case runs the same interview with no voice separation, then adds one flag marked correct for each of two speakers.
"""
import json

from fact_checker.core import summary
from fact_checker.server import run_analysis
from s33_fakes import GUEST, HOST, NOISE, TITLE, FakeModel, FakeTranscript, FakeVoices

NAMED = {HOST: ("Presentador", "host", "Presentador"), GUEST: ("Ana Ruiz (invitada)", "guest", "Ana Ruiz"),
         NOISE: ("Técnico", "guest", "Técnico")}


def flag(id, t, speaker):
    return {"id": id, "t": t, "speaker": speaker, "quote": f"frase inventada {id}", "type": "fallacy",
            "label": "ad_hominem", "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "sources": [],
            "note": None, "on_player": True, "mark": "correct"}


def test_people_in_flag_file(tmp_path):
    model = FakeModel(NAMED)
    run_analysis("entrevista", 0, transcript=FakeTranscript(), llm=model, home=tmp_path, voices=FakeVoices())
    data = json.loads((tmp_path / "videos" / "entrevista.json").read_text())
    people = data.get("people")
    assert people, f"FAIL S33 A1 · the flag file has no people: {sorted(data)}"

    # Case 1 · the host's voice → role host, the person is the label, 1260 s of speech, set by the reading
    assert people.get("Presentador") == {"role": "host", "person": "Presentador", "spoken_s": 1260,
                                         "set_by": "llm"}, f"FAIL S33 A1 · host entry {people.get('Presentador')}"

    # Case 2 · the guest's voice → role guest, person "Ana Ruiz", 2460 s of speech
    assert people.get("Ana Ruiz (invitada)") == {"role": "guest", "person": "Ana Ruiz", "spoken_s": 2460,
                                                 "set_by": "llm"}, f"FAIL S33 A1 · guest entry {people}"

    # Case 3 · a voice under 5 % of the talk → no entry
    assert set(people) == {"Presentador", "Ana Ruiz (invitada)"}, f"FAIL S33 A1 · entries {sorted(people)}"

    # Case 4 · the speaker reading → asks a role (host or guest) and a person, and sees the video title
    assert len(model.readings) == 1, f"FAIL S33 A1 · {len(model.readings)} speakers readings"
    item = model.readings[0]["schema"]["properties"]["speakers"]["items"]
    assert item["properties"]["role"]["enum"] == ["host", "guest"], f"FAIL S33 A1 · role schema {item['properties']}"
    assert {"role", "person"} <= set(item["required"]), f"FAIL S33 A1 · required {item['required']}"
    assert TITLE in model.readings[0]["prompt"], "FAIL S33 A1 · the speakers reading does not see the video title"

    # Case 5 · no voice separation → no people in the file, and a card for every speaker
    run_analysis("sinvoces", 0, transcript=FakeTranscript(), llm=FakeModel(NAMED), home=tmp_path)
    plain = json.loads((tmp_path / "videos" / "sinvoces.json").read_text())
    assert "people" not in plain, f"FAIL S33 A1 · a file with no voices has people: {plain['people']}"
    shown = summary.guests(plain | {"flags": [flag("a-10.0", 10.0, "Presentador"), flag("b-20.0", 20.0, "Ana Ruiz")]})
    assert shown == ["Presentador", "Ana Ruiz"], f"FAIL S33 A1 · the export gives cards for {shown}"
    print("PASS S33 A1 · Each voice gets a role, a person and its seconds of speech")
