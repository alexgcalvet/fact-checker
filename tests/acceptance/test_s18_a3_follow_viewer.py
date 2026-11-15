"""S18 A3 · The analysis follows what the person watches

Story: On an invented 60-minute video, the person starts at 10:00. The helper analyses from 10:00 up to 10 minutes ahead
of the playback second it last heard from the extension, and goes further as playback moves. When the extension stops
asking for a minute (the tab closed), the analysis pauses; when it asks again, it goes on. The parts behind the start
second are analysed only if the person goes back to them.
Edge case: WHEN the person jumps from 15:00 to 45:00 THEN the next parts start at 45:00, and 25:00–45:00 stays
unanalysed until watched.

Setup: an invented 60-minute transcript with one short numbered line every 5 seconds, served by a fake YouTube. The
helper runs behind its real HTTP handler on a free port, as the extension reaches it: POST /videos/<id>?from=<second>
starts the analysis, and GET /videos/<id>?at=<second> is the extension's poll with the playback second. A fake Claude
records the second of the first line of each PART it reads and finds nothing; each reading takes a short while. No
Fact Check Tools key and no voices. The silence before a pause is cut from 60 s to 1.5 s (scheduler.SILENCE), and the
parts run one at a time (scheduler.PARALLEL = 1). A background poller plays the extension: every 0.3 s it sends the
playback second, until the test closes the tab. A temporary helper home.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from fact_checker import server
from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript

HOUR = [Segment(t=float(t), text=f"frase número {t}") for t in range(0, 3600, 5)]
VIDEO = "sesenta1"


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        return Transcript(segments=HOUR, published_at="2026-11-10")


class FakeClaude:
    starts = []
    delay = 0.05

    def __init__(self, *args, **kwargs):
        pass

    def complete(self, prompt, schema, tools=()):
        if "flags" in schema["properties"]:
            part = str(prompt).rpartition("PART:")[2]
            FakeClaude.starts.append(min(int(n) for n in re.findall(r"frase número (\d+)", part)))
            time.sleep(FakeClaude.delay)
            return {"flags": [], "claims": [], "questions": [], "contradictions": [], "positions": [], "context": []}
        return {"rulings": []}


class Extension:
    """Polls the flag file with the playback second while the tab is open."""

    def __init__(self, base):
        self.base, self.at, self.open = base, 0, threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def poll(self):
        """A 404 before the flag file exists still tells the helper the playback second, as the extension's poll does."""
        try:
            urllib.request.urlopen(f"{self.base}/videos/{VIDEO}?at={self.at}").read()
        except urllib.error.HTTPError:
            pass

    def _loop(self):
        while True:
            self.open.wait()
            self.poll()
            time.sleep(0.3)


def wait_for(cond, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out; parts read: {sorted(FakeClaude.starts)}")


def read_in(lo, hi):
    return sorted(s for s in FakeClaude.starts if lo <= s < hi)


def test_follow_viewer(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "ClaudeCLI", FakeClaude)
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(scheduler, "SILENCE", 1.5)
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    FakeClaude.starts = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    tab = Extension(base)
    try:
        # Case 1 · the person starts at 10:00 and stays there → parts from 10:00 up to 20:00 (30 s, then 2 minutes),
        # none before 10:00 and none that starts after 20:00
        tab.at = 600
        urllib.request.urlopen(urllib.request.Request(f"{base}/videos/{VIDEO}?from=600", method="POST")).read()
        tab.open.set()
        wait_for(lambda: 1110 in FakeClaude.starts)
        time.sleep(0.5)
        assert sorted(FakeClaude.starts) == [600, 630, 750, 870, 990, 1110], sorted(FakeClaude.starts)

        # Case 2 · playback moves to 15:00 → the parts go on up to 25:00, and no further
        tab.at = 900
        wait_for(lambda: 1470 in FakeClaude.starts)
        time.sleep(0.5)
        assert read_in(1200, 3600) == [1230, 1350, 1470], read_in(1200, 3600)

        # Case 3 · the person jumps to 45:00 and the tab closes right after → the next parts start at 45:00; after
        # the silence the analysis pauses before the parts up to 55:00 are all read
        FakeClaude.delay = 0.5
        tab.open.clear()
        time.sleep(0.4)
        tab.at = 2700
        tab.poll()
        wait_for(lambda: 2700 in FakeClaude.starts)
        time.sleep(scheduler.SILENCE + 1)
        paused = read_in(2700, 3600)
        time.sleep(1.5)
        assert read_in(2700, 3600) == paused, (paused, read_in(2700, 3600))
        assert paused[0] == 2700 and len(paused) < 6, paused

        # Case 4 · the extension asks again → the analysis goes on up to 55:00
        tab.open.set()
        wait_for(lambda: 3210 in FakeClaude.starts)
        assert read_in(2700, 3600) == [2700, 2730, 2850, 2970, 3090, 3210], read_in(2700, 3600)

        # Case 5 · the stretch skipped by the jump → 25:00-45:00 stays unanalysed
        FakeClaude.delay = 0.05
        assert read_in(1500, 2700) == [], read_in(1500, 2700)

        # Case 6 · the person goes back to 2:00 → the parts from 2:00 are analysed, none before it, and no part
        # from 10:00 on is read again
        later = sorted(s for s in FakeClaude.starts if s >= 600)
        tab.at = 120
        wait_for(lambda: 510 in FakeClaude.starts)
        time.sleep(0.5)
        assert read_in(0, 600) == [120, 150, 270, 390, 510], read_in(0, 600)
        assert sorted(s for s in FakeClaude.starts if s >= 600) == later, read_in(600, 3600)
        assert read_in(1500, 2700) == [], read_in(1500, 2700)
    finally:
        tab.open.clear()
        httpd.shutdown()

    data = json.loads((tmp_path / "videos" / f"{VIDEO}.json").read_text())
    assert data["status"] == "running", data["status"]
    print("PASS S18 A3 · The analysis follows what the person watches")
