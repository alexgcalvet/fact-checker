"""S31 A4 · The time to the first part is logged

Story: After an analysis with part readings of 0.2 seconds, the flag file holds `first_flags_s`, the seconds from the
start of the analysis to the first part written, such as 0.4; later parts do not change it, and a shared copy of the
analysis leaves it out.

Setup: the invented interview of S31 A1 (captions with no voices, four parts), read whole with no viewer and no speaker
separation, by a fake model whose part readings take 0.2 s, in a thread so the test can read the flag file while the
analysis runs. A second run whose captions cannot be fetched. A temporary helper home per run.
"""
import threading

from fact_checker import analyses
from fact_checker.server import run_analysis
from s31_fakes import PART_S, FakeModel, FakeTranscript, flag_file, wait_for


class NoCaptions:
    def fetch(self, video_id):
        raise RuntimeError("yt-dlp failed")


def test_first_flags_logged(tmp_path):
    run = threading.Thread(target=run_analysis, args=("tiempo01", 0), daemon=True,
                           kwargs={"transcript": FakeTranscript(), "llm": FakeModel(), "home": tmp_path / "one"})
    run.start()

    # Case 1 · the first part is written → the flag file holds first_flags_s, at least one part reading and under 2 s
    first = wait_for(lambda: (flag_file(tmp_path / "one", "tiempo01") or {}).get("first_flags_s"), timeout=5)
    assert first is not None, "FAIL S31 A4 · no first_flags_s after the first part"
    assert PART_S <= first < 2, f"FAIL S31 A4 · first_flags_s is {first}"

    # Case 2 · every part is done → first_flags_s keeps its value, and the shared copy leaves it out
    run.join(timeout=15)
    data = flag_file(tmp_path / "one", "tiempo01")
    assert data["status"] == "done" and data["first_flags_s"] == first, data
    assert "first_flags_s" not in analyses.strip(data), "FAIL S31 A4 · the shared copy carries first_flags_s"

    # Case 3 · the captions cannot be fetched → the analysis stops with no first_flags_s
    run_analysis("tiempo01", 0, transcript=NoCaptions(), llm=FakeModel(), home=tmp_path / "none")
    data = flag_file(tmp_path / "none", "tiempo01")
    assert data["status"] == "stopped" and "first_flags_s" not in data, data
    print("PASS S31 A4 · The time to the first part is logged")
