"""S31 A2 · A flag shown before the voices are known gets the voice's name

Story: In the same interview, the reading of the first part pins the host's ad hominem at second 1 on "Invitado". Once
the voices are known, the flag file names "Presentadora" for that flag, with the same id; a flag whose name already
matches its voice keeps it.
Edge case: WHEN there is no Hugging Face token (no speaker separation) THEN the flags keep the names from the text and
no speakers reading runs.

Setup: the invented interview of S31 A1 (captions with no voices; the host's ad hominem at 0:00, the guest's at 0:12,
the guest's last at 11:00), read whole with no viewer. A fake speaker separation that takes 4 s and puts 0-10 s in the
host's voice and the rest in the guest's. A fake model whose part readings take 0.2 s, that pins the host's words on
"Invitado" and names the voices "Presentadora" and "Invitado". A second run has no speaker separation. A temporary
helper home per run.
"""
import threading

from fact_checker.server import run_analysis
from s31_fakes import (GUEST_QUOTE, HOST_QUOTE, FakeModel, FakeTranscript, SlowVoices, flag_file, speaker_of,
                       wait_for)


def test_names_corrected(tmp_path):
    voices, model = SlowVoices(4), FakeModel()
    run = threading.Thread(target=run_analysis, args=("nombres1", 0), daemon=True,
                           kwargs={"transcript": FakeTranscript(), "llm": model, "home": tmp_path / "voices",
                                   "voices": voices})
    run.start()

    # Case 1 · before the voices are known → the host's flag is shown with the name from the text, "Invitado"
    shown = wait_for(lambda: speaker_of(flag_file(tmp_path / "voices", "nombres1"), HOST_QUOTE), timeout=3.5)
    assert shown == "Invitado" and not voices.done.is_set(), f"FAIL S31 A2 · shown before the voices as {shown}"
    before = next(f for f in flag_file(tmp_path / "voices", "nombres1")["flags"] if f["quote"] == HOST_QUOTE)

    # Case 2 · the voices are known → the same flag (same id) names "Presentadora"; the guest's flag keeps "Invitado"
    run.join(timeout=15)
    data = flag_file(tmp_path / "voices", "nombres1")
    after = next(f for f in data["flags"] if f["quote"] == HOST_QUOTE)
    assert after["speaker"] == "Presentadora", f"FAIL S31 A2 · the shown flag still names {after['speaker']}"
    assert after["id"] == before["id"] and after["t"] == before["t"] and after["reason"] == before["reason"], after
    assert speaker_of(data, GUEST_QUOTE) == "Invitado", data["flags"]
    assert data["status"] == "done" and data["speakers"] == {"SPEAKER_00": "Presentadora", "SPEAKER_01": "Invitado"}

    # Case 3 · no speaker separation → the flags keep the names from the text; no speakers reading
    model = FakeModel()
    run_analysis("nombres1", 0, transcript=FakeTranscript(), llm=model, home=tmp_path / "text")
    data = flag_file(tmp_path / "text", "nombres1")
    assert speaker_of(data, HOST_QUOTE) == "Invitado" and model.speakers_readings == 0, \
        f"FAIL S31 A2 · without voices: {data['flags']}"
    print("PASS S31 A2 · A flag shown before the voices are known gets the voice's name")
