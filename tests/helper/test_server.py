"""The helper server: it starts and follows an analysis, serves the flag file and keeps the person's marks."""
import http.client
import json
import plistlib
import re
import stat
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from fact_checker import cli, install, server
from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript
from fact_checker.core.scheduler import plan
from fact_checker.server import handler, Helper, run_analysis
from fact_checker.store import Store
from interview_fakes import fail_clis, FakeMessagesAPI, TWO_PARTS
from machine_fakes import Foreign, free_ports, guard, health, wait
from video_fakes import FakeTranscript, fake_video, JSON3Captions, NoPublishedChecks


# S1 A3 · The analysis starts where the person is watching and runs ahead
#
# Story: The person opens a 60-minute video at minute 50. The first part analysed is the 30 seconds from
# minute 50, then 2-minute parts forward to the end, then the first 50 minutes; never more than 3 parts at
# once. The usage log shows, for each part, how many seconds before playback it was ready.
#
# Setup: an invented 60-minute transcript with one short line every 5 seconds; a fake Claude that takes
# 50 ms per call, finds nothing, and counts how many calls run at the same time; a temporary helper home.

HOUR = [Segment(t=float(t), text=f"frase número {t}") for t in range(0, 3600, 5)]


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
    run_analysis("hour", 3000, transcript=FakeTranscript(HOUR), llm=claude, home=tmp_path)
    data = json.loads((tmp_path / "videos" / "hour.json").read_text())

    # Case 5 · all parts analysed → status done, one Claude call per part
    assert data["status"] == "done"
    assert claude.calls == len(plan(FakeTranscript(HOUR).fetch("hour"), 3000))

    # Case 6 · never more than 3 calls at once, and more than one when there is work
    assert 2 <= claude.peak <= 3

    # Case 7 · the usage log has one line per call, each with the lead in seconds
    lines = [json.loads(x) for x in (tmp_path / "usage.log").read_text().splitlines()]
    assert len(lines) == claude.calls
    assert all(isinstance(x["lead_s"], (int, float)) for x in lines)
    assert any(x["chunk_start"] == 3000 for x in lines)
    print("PASS S1 A3 · The analysis starts where the person is watching and runs ahead")


# S3 A4 (helper part) · Only flags above their type's bar reach the player
#
# Story: With bars fallacy 0.5 and inaccuracy 0.9, the helper marks a 0.55 fallacy for the player and a
# 0.85 inaccuracy not. The extension part is in tests/extension/card.test.ts (S3 A4).
#
# Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake Claude that returns one
# fallacy at 0.55 and one claim it judges false at 0.85 with a dated source; no published checks.

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-claims.json3"


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [{"quote": "el paro juvenil se duplicó el año pasado", "verdict": "false",
                                  "reason": "No.", "confidence": 0.85, "note": None,
                                  "sources": [{"publisher": "INE", "url": "https://www.ine.es/x", "date": "2025-10-28"}]}]}
        return {"flags": [{"quote": "eso es lo que dicen los datos", "label": "vague_authority", "speaker": "guest",
                           "reason": "Vago.", "confidence": 0.55}],
                "claims": [{"quote": "el paro juvenil se duplicó el año pasado", "speaker": "guest", "queries": ["paro"]}]}


def test_on_player_by_type(tmp_path):
    run_analysis("claims", 0, transcript=JSON3Captions(FAKE), llm=FakeClaude(), factcheck=NoPublishedChecks(),
                 home=tmp_path, thresholds={"fallacy": 0.5, "inaccuracy": 0.9})
    flags = {f["type"]: f for f in json.loads((tmp_path / "videos" / "claims.json").read_text())["flags"]}

    # Case 1 · a 0.55 fallacy with the fallacy bar at 0.5 → marked for the player
    assert flags["fallacy"]["on_player"] is True

    # Case 2 · a 0.85 inaccuracy with the inaccuracy bar at 0.9 → not marked
    assert flags["inaccuracy"]["on_player"] is False
    print("PASS S3 A4 (helper) · Only flags above their type's bar reach the player")


# S4 A1 (helper part) · Marking a card keeps the mark on the laptop
#
# Story: The person marks an ad hominem card "unfair" with the reason "es una pregunta, no un ataque". The
# helper's marks log gets one line with the video, the flag, its words, its name, "unfair" and that reason.
# Marking it again "correct" adds a second line; the latest mark is the one that counts. The extension part
# is in tests/extension/card.test.ts (S4 A1).
#
# Setup: a temporary helper home with the flag file of one video holding one ad hominem flag; the helper
# HTTP server on a free local port.

VIDEO = "abcdefgh"
FLAG = {"id": "ad_hominem-42.0", "t": 42.0, "speaker": "guest", "quote": "la oposición no tiene autoridad",
        "type": "fallacy", "label": "ad_hominem", "reason": "Ataca.", "confidence": 0.55, "related": None,
        "sources": [], "note": None, "on_player": True}


def post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status
    except urllib.error.HTTPError as e:
        return e.code


def test_mark_stored(tmp_path):
    Store(tmp_path).save({"video_id": VIDEO, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
                          "flags": [FLAG]})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    marks = tmp_path / "marks.jsonl"
    try:
        # Case 1 · an "unfair" mark with a reason → one line with video, flag, words, name, verdict, reason
        assert post(port, f"/videos/{VIDEO}/marks",
                    {"flag_id": FLAG["id"], "verdict": "unfair", "reason": "es una pregunta, no un ataque"}) == 200
        line = json.loads(marks.read_text().splitlines()[0])
        assert {k: line[k] for k in ("video_id", "flag_id", "quote", "label", "type", "verdict", "reason")} == {
            "video_id": VIDEO, "flag_id": FLAG["id"], "quote": FLAG["quote"], "label": "ad_hominem",
            "type": "fallacy", "verdict": "unfair", "reason": "es una pregunta, no un ataque"}
        assert line["confidence"] == 0.55

        # Case 2 · the same card marked "correct" → a second line; both are kept
        assert post(port, f"/videos/{VIDEO}/marks", {"flag_id": FLAG["id"], "verdict": "correct", "reason": ""}) == 200
        assert [json.loads(x)["verdict"] for x in marks.read_text().splitlines()] == ["unfair", "correct"]

        # Case 3 · a flag that the video does not have, or a verdict outside the two → rejected, no line
        assert post(port, f"/videos/{VIDEO}/marks", {"flag_id": "nope-1.0", "verdict": "unfair", "reason": ""}) == 404
        assert post(port, f"/videos/{VIDEO}/marks", {"flag_id": FLAG["id"], "verdict": "maybe", "reason": ""}) == 400
        assert len(marks.read_text().splitlines()) == 2
    finally:
        httpd.shutdown()
    print("PASS S4 A1 (helper) · Marking a card keeps the mark on the laptop")


# S13 A1 · The flag file says how far the analysis has reached
#
# Story: The helper analyses an invented 10-minute video from the start. The part from 2:00 to 4:00 finishes
# before the part from 0:30 to 2:00. While that happens the flag file says "analysed until 0:30"; once both
# are done it says "analysed until 4:00". (The plan cuts the parts at 0:30, 2:30, 4:30, 6:30 and 8:30, so the
# test uses those bounds: the part 2:30-4:30 finishes before the part 0:30-2:30.)
#
# Setup: an invented 10-minute transcript with one short line every 5 seconds; a fake Claude that finds
# nothing and holds the part 0:30-2:30 and the part 4:30-6:30 until the test lets them go; a temporary helper
# home. The analysis runs in a thread and the test reads the flag file between the parts.

TEN_MINUTES = [Segment(t=float(t), text=f"frase número {t}") for t in range(0, 600, 5)]


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
                           kwargs={"transcript": FakeTranscript(TEN_MINUTES), "llm": claude, "home": tmp_path})
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


# S13 A3 · The helper returns the person's latest mark on each flag
#
# Story: The person marked a card unfair and then correct. When the extension asks for the flag file, that flag
# comes with the mark "correct", and flags with no mark come without one.
#
# Setup: a temporary helper home with the flag file of one video holding two flags, and a marks log line of
# another video that shares the id of the second flag; the helper HTTP server on a free local port.

OTHER = "zyxwvuts"


def flag(id, t, label):
    return {"id": id, "t": t, "speaker": "guest", "quote": f"frase {t}", "type": "fallacy", "label": label,
            "reason": "Motivo.", "confidence": 0.85, "related": None, "sources": [], "note": None, "on_player": True}


MARKED = flag("ad_hominem-42.0", 42.0, "ad_hominem")
UNMARKED = flag("straw_man-90.0", 90.0, "straw_man")


def request(port, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read())


def test_marks_in_flag_file(tmp_path):
    store = Store(tmp_path)
    store.save({"video_id": VIDEO, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
                "flags": [MARKED, UNMARKED]})
    store.save({"video_id": OTHER, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
                "flags": [UNMARKED]})
    store.add_mark(OTHER, UNMARKED, "unfair", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler(Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        # Case 1 · a flag marked unfair, then correct → the flag file comes with the mark "correct"
        request(port, f"/videos/{VIDEO}/marks", {"flag_id": MARKED["id"], "verdict": "unfair", "reason": "no"})
        request(port, f"/videos/{VIDEO}/marks", {"flag_id": MARKED["id"], "verdict": "correct", "reason": ""})
        flags = {f["id"]: f for f in request(port, f"/videos/{VIDEO}")["flags"]}
        assert flags[MARKED["id"]]["mark"] == "correct"

        # Case 2 · a flag with no mark in this video (only in another video) → no mark
        assert "mark" not in flags[UNMARKED["id"]]

        # Case 3 · the flag file on disk → keeps no mark; the marks log stays the only record
        assert all("mark" not in f for f in store.load(VIDEO)["flags"])
    finally:
        httpd.shutdown()
    print("PASS S13 A3 · The helper returns the person's latest mark on each flag")


# S18 A3 · The analysis follows what the person watches
#
# Story: On an invented 60-minute video, the person starts at 10:00. The helper analyses from 10:00 up to 10 minutes ahead
# of the playback second it last heard from the extension, and goes further as playback moves. When the extension stops
# asking for a minute (the tab closed), the analysis pauses; when it asks again, it goes on. The parts behind the start
# second are analysed only if the person goes back to them.
# Edge case: WHEN the person jumps from 15:00 to 45:00 THEN the next parts start at 45:00, and 25:00–45:00 stays
# unanalysed until watched.
#
# Setup: an invented 60-minute transcript with one short numbered line every 5 seconds, served by a fake YouTube. The
# helper runs behind its real HTTP handler on a free port, as the extension reaches it: POST /videos/<id>?from=<second>
# starts the analysis, and GET /videos/<id>?at=<second> is the extension's poll with the playback second. A fake Claude
# records the second of the first line of each PART it reads and finds nothing; each reading takes a short while. No
# Fact Check Tools key and no voices. The silence before a pause is cut from 60 s to 1.5 s (scheduler.SILENCE), and the
# parts run one at a time (scheduler.PARALLEL = 1). A background poller plays the extension: every 0.3 s it sends the
# playback second, until the test closes the tab. A temporary helper home.

VIEWED = "sesenta1"


class FollowingModel:
    starts = []
    delay = 0.05

    def __init__(self, *args, **kwargs):
        pass

    def complete(self, prompt, schema, tools=()):
        if "flags" in schema["properties"]:
            part = str(prompt).rpartition("PART:")[2]
            FollowingModel.starts.append(min(int(n) for n in re.findall(r"frase número (\d+)", part)))
            time.sleep(FollowingModel.delay)
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
            urllib.request.urlopen(f"{self.base}/videos/{VIEWED}?at={self.at}").read()
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
    raise AssertionError(f"timed out; parts read: {sorted(FollowingModel.starts)}")


def read_in(lo, hi):
    return sorted(s for s in FollowingModel.starts if lo <= s < hi)


def test_follow_viewer(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "YouTube", lambda *args: FakeTranscript(HOUR))
    monkeypatch.setattr(server, "ClaudeCLI", FollowingModel)
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(scheduler, "SILENCE", 1.5)
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    FollowingModel.starts = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    tab = Extension(base)
    try:
        # Case 1 · the person starts at 10:00 and stays there → parts from 10:00 up to 20:00 (30 s, then 2 minutes),
        # none before 10:00 and none that starts after 20:00
        tab.at = 600
        urllib.request.urlopen(urllib.request.Request(f"{base}/videos/{VIEWED}?from=600", method="POST")).read()
        tab.open.set()
        wait_for(lambda: 1110 in FollowingModel.starts)
        time.sleep(0.5)
        assert sorted(FollowingModel.starts) == [600, 630, 750, 870, 990, 1110], sorted(FollowingModel.starts)

        # Case 2 · playback moves to 15:00 → the parts go on up to 25:00, and no further
        tab.at = 900
        wait_for(lambda: 1470 in FollowingModel.starts)
        time.sleep(0.5)
        assert read_in(1200, 3600) == [1230, 1350, 1470], read_in(1200, 3600)

        # Case 3 · the person jumps to 45:00 and the tab closes right after → the next parts start at 45:00; after
        # the silence the analysis pauses before the parts up to 55:00 are all read
        FollowingModel.delay = 0.5
        tab.open.clear()
        time.sleep(0.4)
        tab.at = 2700
        tab.poll()
        wait_for(lambda: 2700 in FollowingModel.starts)
        time.sleep(scheduler.SILENCE + 1)
        paused = read_in(2700, 3600)
        time.sleep(1.5)
        assert read_in(2700, 3600) == paused, (paused, read_in(2700, 3600))
        assert paused[0] == 2700 and len(paused) < 6, paused

        # Case 4 · the extension asks again → the analysis goes on up to 55:00
        tab.open.set()
        wait_for(lambda: 3210 in FollowingModel.starts)
        assert read_in(2700, 3600) == [2700, 2730, 2850, 2970, 3090, 3210], read_in(2700, 3600)

        # Case 5 · the stretch skipped by the jump → 25:00-45:00 stays unanalysed
        FollowingModel.delay = 0.05
        assert read_in(1500, 2700) == [], read_in(1500, 2700)

        # Case 6 · the person goes back to 2:00 → the parts from 2:00 are analysed, none before it, and no part
        # from 10:00 on is read again
        later = sorted(s for s in FollowingModel.starts if s >= 600)
        tab.at = 120
        wait_for(lambda: 510 in FollowingModel.starts)
        time.sleep(0.5)
        assert read_in(0, 600) == [120, 150, 270, 390, 510], read_in(0, 600)
        assert sorted(s for s in FollowingModel.starts if s >= 600) == later, read_in(600, 3600)
        assert read_in(1500, 2700) == [], read_in(1500, 2700)
    finally:
        tab.open.clear()
        httpd.shutdown()

    data = json.loads((tmp_path / "videos" / f"{VIEWED}.json").read_text())
    assert data["status"] == "running", data["status"]
    print("PASS S18 A3 · The analysis follows what the person watches")


# S20 A4 · Codex flags meet Codex bars
#
# Story: With Codex as the provider and no Codex bars yet, a fallacy at confidence 0.6 goes to the side panel, not on
# the player, though the Claude bar is 0.4. Once a Codex bars file sets the fallacy bar at 0.5, the same flag goes on
# the player. With Claude as the provider, the Claude bars apply as before.
#
# Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake LLM that returns one fallacy at 0.6
# and no claims. The Claude bars file is a temporary thresholds.json with fallacy 0.4 and inaccuracy 0.6; the Codex
# bars file, when it exists, is thresholds.codex.json beside it. run_analysis gets no thresholds, so it reads the bars
# of the provider in FACT_CHECK_PROVIDER. A temporary helper home per run.

class FakeLLM:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [{"quote": "eso es lo que dicen los datos", "label": "vague_authority", "speaker": "guest",
                           "reason": "Vago.", "confidence": 0.6}], "claims": []}


def on_player(home: Path) -> bool:
    server.run_analysis("claims", 0, transcript=JSON3Captions(FAKE), llm=FakeLLM(), home=home)
    flags = json.loads((home / "videos" / "claims.json").read_text())["flags"]
    [fallacy] = [f for f in flags if f["type"] == "fallacy"]
    assert fallacy["confidence"] == 0.6, fallacy
    return fallacy["on_player"]


def test_bars_per_provider(tmp_path, monkeypatch):
    bars = tmp_path / "bars"
    bars.mkdir()
    (bars / "thresholds.json").write_text(json.dumps({"fallacy": 0.4, "inaccuracy": 0.6}))
    monkeypatch.setattr(server, "THRESHOLDS", bars / "thresholds.json")

    # Case 1 · Codex, no Codex bars file → the 0.6 fallacy meets the 0.8 default bar, not the Claude bar of 0.4:
    # side panel only
    monkeypatch.setenv("FACT_CHECK_PROVIDER", "codex")
    assert on_player(tmp_path / "codex-default") is False

    # Case 2 · Codex, a Codex bars file with fallacy 0.5 → the same flag goes on the player
    (bars / "thresholds.codex.json").write_text(json.dumps({"fallacy": 0.5, "inaccuracy": None}))
    assert on_player(tmp_path / "codex-tuned") is True

    # Case 3 · Claude (no provider set), the Codex file now at fallacy 0.9 → the Claude bar of 0.4 applies: on the player
    (bars / "thresholds.codex.json").write_text(json.dumps({"fallacy": 0.9, "inaccuracy": None}))
    monkeypatch.delenv("FACT_CHECK_PROVIDER")
    assert on_player(tmp_path / "claude") is True
    print("PASS S20 A4 · Codex flags meet Codex bars")


# S38 A2 · A taken port moves the helper and the extension follows (the helper side)
#
# Story: Another program holds port 8765. The helper starts at login on 8766 instead, and on YouTube the "Analizar este
# vídeo" button starts an analysis whose flag file appears in the helper home. With all five ports 8765–8769 taken, the
# helper log says so in one line and the helper stops; it does not restart in a loop.
#
# Setup: a temporary helper home and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT), so "8765" below
# is the first of them. Another program is a small web server that answers every request with an HTML 404. The helper
# runs as `fact-checker serve` with no `--port`, as the login agent starts it, in this process: the invented interview
# stands in for YouTube, and failing `claude` and `codex` commands stand in for the readers. The extension side is
# checked in tests/extension/start.test.ts (S38 A2).

def test_port_fallback(tmp_path, monkeypatch, capsys):
    fail_clis(tmp_path, monkeypatch)
    fake_video(monkeypatch, TWO_PARTS)
    guard(monkeypatch)
    first = free_ports()
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.setenv("FACT_CHECKER_PORT", str(first))
    started = []

    class Recorded(server.ThreadingHTTPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            started.append(self)

    monkeypatch.setattr(server, "ThreadingHTTPServer", Recorded)
    foreigners = [Foreign(first)]
    try:
        # Case 1 · another program holds 8765, `serve` with no port → the helper answers /health on 8766
        monkeypatch.setattr(sys, "argv", ["fact-checker", "serve"])
        threading.Thread(target=cli.main, daemon=True).start()
        answer = wait(lambda: health(first + 1))
        assert answer and answer["app"] == "fact-checker" and answer["home"] == str(home), \
            f"FAIL S38 A2 · no helper on {first + 1}: {answer}"
        assert foreigners[0].answers(), "FAIL S38 A2 · the other program lost its port"

        # Case 2 · the analyse request on 8766 → 202, and the flag file of the video appears in the helper home
        req = urllib.request.Request(f"http://127.0.0.1:{first + 1}/videos/{VIDEO}?from=0&lang=es", method="POST")
        with urllib.request.urlopen(req, timeout=10) as res:
            assert res.status == 202, f"FAIL S38 A2 · analyse answered {res.status}"
        flag_file = home / "videos" / f"{VIDEO}.json"
        assert wait(flag_file.exists), f"FAIL S38 A2 · no flag file in {home / 'videos'}"
        assert json.loads(flag_file.read_text())["video_id"] == VIDEO, "FAIL S38 A2 · the flag file of another video"
        for httpd in started:
            httpd.shutdown()
            httpd.server_close()
        started.clear()
        capsys.readouterr()

        # Case 3 · all five ports taken → one log line that says so, and the helper stops with exit 0
        foreigners += [Foreign(port) for port in range(first + 1, first + 5)]
        ended = []

        def serve():
            try:
                cli.main()
            except SystemExit as end:
                ended.append(end.code or 0)
            else:
                ended.append(0)
        stopper = threading.Thread(target=serve, daemon=True)
        stopper.start()
        stopper.join(timeout=10)
        assert ended, "FAIL S38 A2 · the helper still runs with every port taken"
        code, out = ended[0], capsys.readouterr().out.splitlines()
        assert code == 0, f"FAIL S38 A2 · serve exit {code} with every port taken"
        assert len(out) == 1 and f"{first}–{first + 4}" in out[0] and "taken" in out[0], \
            f"FAIL S38 A2 · the log: {out}"

        # Case 4 · the login agent restarts the helper only after a failure, never after that clean stop
        plist = install.launchd_plist(["fact-checker", "serve"], "/usr/bin", tmp_path / "server.log")
        assert plistlib.loads(plist)["KeepAlive"] == {"SuccessfulExit": False}, \
            f"FAIL S38 A2 · launchd restarts a clean stop: {plistlib.loads(plist)['KeepAlive']}"
        assert "Restart=on-failure" in install.systemd_unit(["fact-checker", "serve"], "/usr/bin"), \
            "FAIL S38 A2 · systemd restarts a clean stop"
    finally:
        for foreign in foreigners:
            foreign.stop()
        for httpd in started:
            httpd.shutdown()
            httpd.server_close()
    print("PASS S38 A2 · A taken port moves the helper and the extension follows (helper side)")


# `fact-checker analyze <url>` reads the whole video as the helper does, with no tab open to follow.
#
# An analysis started over HTTP follows the extension's playback second and pauses about ten minutes ahead of it when
# nobody polls; the command must not stop there.

WHOLE = "entera1234"
LINES = [Segment(t=float(t), text=f"frase número {t} del programa") for t in range(0, 1500, 10)]  # 25 minutes


class NothingModel:
    def __init__(self, *args, **kwargs):
        pass

    def complete(self, prompt, schema, tools=()):
        if "flags" in schema["properties"]:
            return {"flags": [], "claims": [], "questions": [], "contradictions": [], "positions": [], "context": []}
        return {"rulings": []}


def test_analyze_reads_past_the_horizon(tmp_path, monkeypatch):
    monkeypatch.setenv("FACT_CHECKER_HOME", str(tmp_path))
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(server, "YouTube", lambda *args: FakeTranscript(LINES))
    monkeypatch.setattr(server, "ClaudeCLI", NothingModel)
    monkeypatch.setattr(sys, "argv", ["fact-checker", "analyze", f"https://www.youtube.com/watch?v={WHOLE}&t=60s"])

    cli.main()

    data = json.loads((tmp_path / "videos" / f"{WHOLE}.json").read_text())
    assert data["status"] == "done", data
    assert data["analysed_until"] >= LINES[-1].t


KEY = "sk-ant-invented-s40-key-0123456789"


# S40 A3 · A key saved from the extension (the helper side)
#
# Story: The provider is `anthropic` and no key is set. On YouTube, the person opens ⚙ and clicks "Claves". A helper page
# lists `ANTHROPIC_API_KEY` as "falta". The person pastes the key in a hidden field and saves. The page says "guardada",
# never shows the value, the key file is readable only by the person, and the next analysis reads with that key with no
# restart.
#
# Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME); the helper home's settings say `provider = "anthropic"`, `screen = false`, and send the Anthropic
# API to a fake Messages API on a free local port. The home's `.env` holds only a comment. The helper's HTTP handler
# runs in this process on a free local port, never 8765–8769, and the same helper later runs the analysis, as one
# running helper does. The video is the invented two-part interview of S23 (fake YouTube, published fact-checks that
# find nothing, no voices); failing `claude` and `codex` commands are first on PATH. The key is an invented string. The
# extension side is checked in s40-a3-settings-opens-keys.test.ts.

def test_key_page(tmp_path, monkeypatch, capsys):
    fake_video(monkeypatch, TWO_PARTS)
    fail_clis(tmp_path, monkeypatch)
    guard(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY")  # restored after the test: the helper sets the key it saves
    api = FakeMessagesAPI()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    (home / "config.toml").write_text(f'provider = "anthropic"\nscreen = false\n[anthropic]\nbase_url = "{api.url}"\n')
    (home / ".env").write_text("# ANTHROPIC_API_KEY=\n")
    port = free_ports()
    base = f"http://127.0.0.1:{port}"
    helper = server.Helper(home)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), server.handler(helper))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def page(method="GET", form=None) -> tuple[int, str]:
        data = urllib.parse.urlencode(form).encode() if form else None
        req = urllib.request.Request(f"{base}/keys", data=data, method=method, headers={"Origin": base} if form else {})
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, res.read().decode()

    def row(text: str, name: str) -> str:
        """The text of the page around the key name, with the tags removed."""
        plain = re.sub(r"<[^>]+>", " ", text)
        return plain[plain.index(name):][:200]

    try:
        # Case 1 · GET /keys → 200, an HTML page that lists ANTHROPIC_API_KEY as "falta", with a hidden field for it
        status, text = page()
        assert status == 200, f"FAIL S40 A3 · /keys answered {status}"
        assert "ANTHROPIC_API_KEY" in text and "falta" in row(text, "ANTHROPIC_API_KEY"), \
            f"FAIL S40 A3 · ANTHROPIC_API_KEY is not listed as falta: {text}"
        assert re.search(r'<input[^>]*type="password"', text), "FAIL S40 A3 · no hidden field for the key"

        # Case 2 · the person saves the key → the page says "guardada" and never holds the value
        status, text = page("POST", {"name": "ANTHROPIC_API_KEY", "value": f"  {KEY}  "})
        assert status == 200, f"FAIL S40 A3 · saving answered {status}"
        assert "guardada" in row(text, "ANTHROPIC_API_KEY"), f"FAIL S40 A3 · the page does not say guardada: {text}"
        assert KEY not in text, "FAIL S40 A3 · the page shows the key"
        assert KEY not in page()[1], "FAIL S40 A3 · the page shows the key on a later visit"

        # Case 3 · the key file holds the key in place of its commented line, and is readable only by the person
        assert (home / ".env").read_text() == f"ANTHROPIC_API_KEY={KEY}\n", "FAIL S40 A3 · the key file"
        assert stat.S_IMODE((home / ".env").stat().st_mode) == 0o600, \
            f"FAIL S40 A3 · the key file mode is {oct(stat.S_IMODE((home / '.env').stat().st_mode))}"

        # Case 4 · the next analysis of the same running helper → every reading sends that key
        helper._run("keys1", 0)
        assert api.requests, "FAIL S40 A3 · the analysis sent no reading"
        sent = {r["headers"].get("x-api-key") for r in api.requests}
        assert sent == {KEY}, f"FAIL S40 A3 · the readings sent other keys: {len(sent)} distinct"

        # Case 5 · a second key replaces the first in the running helper too
        page("POST", {"name": "ANTHROPIC_API_KEY", "value": KEY + "-2"})
        api.requests.clear()
        helper._run("keys2", 0)
        assert {r["headers"].get("x-api-key") for r in api.requests} == {KEY + "-2"}, \
            "FAIL S40 A3 · the running helper kept the old key"
        assert (home / ".env").read_text() == f"ANTHROPIC_API_KEY={KEY}-2\n", "FAIL S40 A3 · the key file after a change"

        # Case 6 · nothing the helper printed holds the key
        out = capsys.readouterr()
        assert KEY not in out.out + out.err, "FAIL S40 A3 · the helper printed the key"
    finally:
        httpd.shutdown()
        httpd.server_close()
        api.stop()
    print("PASS S40 A3 · A key saved from the extension (helper side)")


OLD = "ANTHROPIC_API_KEY=sk-ant-invented-old\n"
NEW = "sk-ant-invented-new"


# S40 A4 · The key page refuses other sites
#
# Story: A web page on another site posts a key to the helper's key page, or reaches it through a host name other than
# 127.0.0.1. The helper answers 403 and the key file does not change.
#
# Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME); the helper home's settings say `provider = "anthropic"`, with a `.env` that holds one invented
# ANTHROPIC_API_KEY. The helper's HTTP handler runs in this process on a free local port, never 8765–8769. Each request
# is sent by hand with the Host and Origin headers that a browser would send for another site, or for a host name that
# points at 127.0.0.1 (DNS rebinding). The keys are invented strings.

def test_key_page_origin(tmp_path, monkeypatch):
    guard(monkeypatch)
    for name in ("FACT_CHECK_PROVIDER", "ANTHROPIC_API_KEY", "HF_TOKEN", "FACT_CHECK_API_KEY"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)  # restored after the test: the helper sets each key it saves
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    (home / "config.toml").write_text('provider = "anthropic"\n')
    keys = home / ".env"
    keys.write_text(OLD)
    keys.chmod(0o600)
    port = free_ports()
    own = f"127.0.0.1:{port}"
    httpd = ThreadingHTTPServer(("127.0.0.1", port), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def send(method: str, host: str, origin: str | None = None, form: dict | None = None) -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        body = urllib.parse.urlencode(form or {"name": "ANTHROPIC_API_KEY", "value": NEW}) if method == "POST" else None
        headers = {"Host": host} | ({"Origin": origin} if origin is not None else {}) | \
            ({"Content-Type": "application/x-www-form-urlencoded"} if body else {})
        conn.request(method, "/keys", body=body, headers=headers)
        res = conn.getresponse()
        answer = (res.status, res.read().decode(errors="replace"))
        conn.close()
        return answer

    def unchanged(case: str) -> None:
        assert keys.read_text() == OLD, f"FAIL S40 A4 · {case}: the key file changed"
        assert stat.S_IMODE(keys.stat().st_mode) == 0o600, f"FAIL S40 A4 · {case}: the key file mode changed"

    try:
        # Case 1 · another site posts a key (Origin https://evil.example) → 403, the key file does not change
        status, text = send("POST", own, "https://evil.example")
        assert status == 403, f"FAIL S40 A4 · a post from another site answered {status}"
        unchanged("another site")
        assert NEW not in text, "FAIL S40 A4 · the refusal echoes the key"

        # Case 2 · a post with Origin null, or with no Origin → 403, the key file does not change
        for origin in ("null", None):
            assert send("POST", own, origin)[0] == 403, f"FAIL S40 A4 · a post with Origin {origin} was not refused"
            unchanged(f"Origin {origin}")

        # Case 3 · a post through another host name (DNS rebinding), even with a matching Origin → 403, no change
        for host in (f"localhost:{port}", f"evil.example:{port}", "127.0.0.1", f"127.0.0.1:{port + 1}"):
            assert send("POST", host, f"http://{host}")[0] == 403, f"FAIL S40 A4 · a post through {host} was not refused"
            unchanged(f"Host {host}")

        # Case 4 · the page itself read through another host name → 403, no key name listed
        for host in (f"localhost:{port}", f"evil.example:{port}"):
            status, text = send("GET", host)
            assert status == 403 and "ANTHROPIC_API_KEY" not in text, f"FAIL S40 A4 · GET through {host}: {status}"

        # Case 5 · a key name the settings do not need, or a value with a line break → refused, no change
        for form in ({"name": "PATH", "value": "/tmp/evil"}, {"name": "OPENAI_API_KEY", "value": NEW},
                     {"name": "ANTHROPIC_API_KEY", "value": f"{NEW}\nPATH=/tmp/evil"}):
            status, _ = send("POST", own, f"http://{own}", form)
            assert status in (400, 403), f"FAIL S40 A4 · {form['name']} answered {status}"
            unchanged(f"form {form['name']}")

        # Case 6 · the two optional keys, from the helper's own page → saved
        added = OLD
        for name in ("HF_TOKEN", "FACT_CHECK_API_KEY"):
            status, _ = send("POST", own, f"http://{own}", {"name": name, "value": f"{name.lower()}-invented"})
            added += f"{name}={name.lower()}-invented\n"
            assert status == 200 and keys.read_text() == added, f"FAIL S40 A4 · {name} from the helper's own page: {status}"
    finally:
        httpd.shutdown()
        httpd.server_close()
    print("PASS S40 A4 · The key page refuses other sites")
