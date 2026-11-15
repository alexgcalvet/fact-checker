"""S13 A1 · The flag file says how far the analysis has reached

Story: The helper analyses an invented 10-minute video from the start. The part from 2:00 to 4:00 finishes
before the part from 0:30 to 2:00. While that happens the flag file says "analysed until 0:30"; once both
are done it says "analysed until 4:00". (The plan cuts the parts at 0:30, 2:30, 4:30, 6:30 and 8:30, so the
test uses those bounds: the part 2:30-4:30 finishes before the part 0:30-2:30.)

Setup: an invented 10-minute transcript with one short line every 5 seconds; a fake Claude that finds
nothing and holds the part 0:30-2:30 and the part 4:30-6:30 until the test lets them go; a temporary helper
home. The analysis runs in a thread and the test reads the flag file between the parts.
"""
import json
import re
import threading
import time

from fact_checker.adapters.youtube import Segment, Transcript
from fact_checker.server import run_analysis

TEN_MINUTES = [Segment(t=float(t), text=f"frase número {t}") for t in range(0, 600, 5)]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=TEN_MINUTES, published_at="2026-11-10")


class HeldClaude:
    """Finds nothing; the part whose last line is at `t` waits for `gates[t]`."""

    def __init__(self, gates):
        self.gates = gates

    def complete(self, prompt, schema):
        last = max(int(n) for n in re.findall(r"frase número (\d+)", prompt))
        if last in self.gates:
            assert self.gates[last].wait(10)
        return {"flags": []}


def wait_for_part(home, start):
    """Waits until the usage log shows the part that starts at `start` as done."""
    log = home / "usage.log"
    for _ in range(200):
        if log.exists() and any(json.loads(x)["chunk_start"] == start for x in log.read_text().splitlines()):
            return
        time.sleep(0.05)
    raise AssertionError(f"part {start} never finished")


def test_analysed_until(tmp_path):
    first, later = threading.Event(), threading.Event()
    claude = HeldClaude({145: first, 385: later})  # parts 30-150 and 270-390
    run = threading.Thread(target=run_analysis, args=("tenmin", 0),
                           kwargs={"transcript": FakeTranscript(), "llm": claude, "home": tmp_path})
    run.start()
    flag_file = tmp_path / "videos" / "tenmin.json"
    try:
        # Case 1 · the part 0:00-0:30 and the part 2:30-4:30 are done, 0:30-2:30 is not → analysed until 0:30
        wait_for_part(tmp_path, 0)
        wait_for_part(tmp_path, 150)
        data = json.loads(flag_file.read_text())
        assert data["status"] == "running"
        assert data["analysed_until"] == 30

        # Case 2 · the part 0:30-2:30 is done too, 4:30-6:30 is not → analysed until 4:30
        first.set()
        wait_for_part(tmp_path, 30)
        assert json.loads(flag_file.read_text())["analysed_until"] == 270
    finally:
        first.set()
        later.set()
        run.join(10)

    # Case 3 · every part is done → status done, analysed past the last line of the video
    data = json.loads(flag_file.read_text())
    assert data["status"] == "done"
    assert data["analysed_until"] >= TEN_MINUTES[-1].t
    print("PASS S13 A1 · The flag file says how far the analysis has reached")
