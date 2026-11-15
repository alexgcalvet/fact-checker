"""S31 A1 · The first part is read before the voices are known

Story: The helper analyses an invented 12-minute interview from second 0, with a speaker separation that takes 5
seconds and part readings that take 0.2 seconds. The flag of the first 30 seconds is in the flag file before the
speaker separation ends. When the person reaches minute 7, the part at minute 11 is read with the voice names
("[Invitado]") in its text.

Setup: invented word-by-word captions with no voices (one word every 0.5 s): the host's ad hominem at 0:00, the
guest's at 0:12, a line at 3:20 and the guest's last ad hominem at 11:00. A fake speaker separation that takes 5 s and
puts 0-10 s in the host's voice and the rest in the guest's. A fake model whose part readings take 0.2 s and that
names the voices "Presentadora" and "Invitado". The analysis runs as the helper runs it for the extension: in a thread,
following a viewer at second 0, so no part starts more than 10 minutes ahead of the playback second. A temporary
helper home.
"""
import threading
import time

from fact_checker.core import scheduler
from fact_checker.server import run_analysis
from s31_fakes import (HOST_QUOTE, LATE_QUOTE, FakeModel, FakeTranscript, SlowVoices, flag_file,
                       speaker_of, wait_for)


def test_first_part_first(tmp_path):
    voices, model, viewer = SlowVoices(5), FakeModel(), scheduler.Viewer(0)
    began = time.monotonic()
    run = threading.Thread(target=run_analysis, args=("primero1", 0), daemon=True,
                           kwargs={"transcript": FakeTranscript(), "llm": model, "home": tmp_path, "voices": voices,
                                   "viewer": viewer})
    run.start()

    # Case 1 · the speaker separation takes 5 s → the flag of the first 30 seconds is in the flag file before it ends
    shown = wait_for(lambda: speaker_of(flag_file(tmp_path, "primero1"), HOST_QUOTE), timeout=4.5)
    assert shown and not voices.done.is_set(), \
        f"FAIL S31 A1 · no first-part flag before the voices ({time.monotonic() - began:.1f} s)"
    assert time.monotonic() - began < 5

    # Case 2 · the voices end; the person reaches minute 7 → the part at minute 11 is read with the voice names
    assert wait_for(lambda: (flag_file(tmp_path, "primero1") or {}).get("speakers"), timeout=10), \
        "FAIL S31 A1 · the voices never reached the flag file"
    viewer.hear(420)
    run.join(timeout=20)
    assert not run.is_alive(), "FAIL S31 A1 · the analysis did not end"
    late = [p for p in model.parts if LATE_QUOTE in p]
    assert late and "[Invitado]" in late[0], f"FAIL S31 A1 · the part at minute 11 has no voice names: {late}"
    data = flag_file(tmp_path, "primero1")
    assert data["status"] == "done", data
    assert speaker_of(data, LATE_QUOTE) == "Invitado", data["flags"]

    # Case 3 · the first part was read once, without voice names
    first = [p for p in model.parts if HOST_QUOTE in p]
    assert len(first) == 1 and "[" not in first[0], f"FAIL S31 A1 · first part readings: {first}"
    print("PASS S31 A1 · The first part is read before the voices are known")
