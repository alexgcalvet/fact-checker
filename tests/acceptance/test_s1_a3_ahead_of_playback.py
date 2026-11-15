"""S1 A3 · The analysis starts where the person is watching and runs ahead

Story: The person opens a 60-minute video at minute 50. The first part analysed is the 30 seconds from
minute 50, then 2-minute parts forward to the end, then the first 50 minutes; never more than 3 parts at
once. The usage log shows, for each part, how many seconds before playback it was ready.

Setup: an invented 60-minute transcript with one short line every 5 seconds; a fake Claude that takes
50 ms per call, finds nothing, and counts how many calls run at the same time; a temporary helper home.
"""
import json
import threading
import time

from fact_checker.adapters.youtube import Transcript, Segment
from fact_checker.core.scheduler import plan
from fact_checker.server import run_analysis

HOUR = [Segment(t=float(t), text=f"frase número {t}") for t in range(0, 3600, 5)]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=HOUR, published_at="2026-11-10")


class CountingClaude:
    def __init__(self):
        self.lock = threading.Lock()
        self.now = 0
        self.peak = 0
        self.calls = 0

    def complete(self, prompt, schema):
        with self.lock:
            self.now += 1
            self.calls += 1
            self.peak = max(self.peak, self.now)
        time.sleep(0.05)
        with self.lock:
            self.now -= 1
        return {"flags": []}


def test_plan_starts_at_playback_second():
    chunks = plan(Transcript(segments=HOUR, published_at="2026-11-10"), 3000)
    starts = [c.start for c in chunks]

    # Case 1 · opened at minute 50 → first part is the 30 seconds from second 3000
    assert (chunks[0].start, chunks[0].end) == (3000, 3030)

    # Case 2 · then 2-minute parts forward to the end of the video
    forward = [c for c in chunks if c.start >= 3000]
    assert [c.start for c in forward[1:]] == list(range(3030, 3600, 120))
    assert starts[: len(forward)] == [c.start for c in forward]

    # Case 3 · then the first 50 minutes, from second 0, in 2-minute parts
    earlier = chunks[len(forward):]
    assert [c.start for c in earlier] == list(range(0, 3000, 120))

    # Case 4 · every line of the transcript is in exactly one part
    covered = [s.t for c in chunks for s in c.segments]
    assert sorted(covered) == [s.t for s in HOUR]


def test_runs_ahead_with_three_at_once(tmp_path):
    claude = CountingClaude()
    run_analysis("hour", 3000, transcript=FakeTranscript(), llm=claude, home=tmp_path)
    data = json.loads((tmp_path / "videos" / "hour.json").read_text())

    # Case 5 · all parts analysed → status done, one Claude call per part
    assert data["status"] == "done"
    assert claude.calls == len(plan(FakeTranscript().fetch("hour"), 3000))

    # Case 6 · never more than 3 calls at once, and more than one when there is work
    assert 2 <= claude.peak <= 3

    # Case 7 · the usage log has one line per call, each with the lead in seconds
    lines = [json.loads(x) for x in (tmp_path / "usage.log").read_text().splitlines()]
    assert len(lines) == claude.calls
    assert all(isinstance(x["lead_s"], (int, float)) for x in lines)
    assert any(x["chunk_start"] == 3000 for x in lines)
    print("PASS S1 A3 · The analysis starts where the person is watching and runs ahead")
