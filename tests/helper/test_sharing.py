"""Sharing: marks and whole analyses sent to the collector after consent, and the owner's review."""
import json
import re
import socket
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

from fact_checker import analyses, cli, server
from fake_servers import FakeCollector, TOKEN
from interview_fakes import fail_clis
from language_fakes import readings, setup
from marks_fakes import (
    FALLACY,
    FIGURE,
    home_with_flags,
    LATER,
    OLD,
    OLD_VIDEO,
    request,
    start_helper,
    VIDEO,
)
from shared_analysis_fakes import ANALYSIS, SHARED_VIDEO


# S24 A4 · The owner pulls the new rows with the admin token
#
# Story: The owner sets `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env` and runs `fact-checker feedback pull`. It prints
# "3 new marks" and writes them to a file in `~/.fact-checker/feedback/`. A second pull prints "0 new marks". The
# collector answers 401 to a read without the token or with a wrong one, and the pull then names the token and exits 1.
#
# Setup: a fake collector on a free local port that holds 3 rows from 2 testers and answers a read only with the admin
# token. A temporary helper home whose `config.toml` sets `feedback_url` to it. Failing fake `claude` and `codex`
# commands on PATH. The collector's own 401 is checked in tests/collector/marks.test.ts (S24 A4).

def row(install, flag_id, at):
    return {"install_id": install, "helper_version": "0.1.0", "received_at": at, "video_id": "abcdefgh",
            "flag_id": flag_id, "t": 42.0, "type": "fallacy", "label": "ad_hominem", "quote": "frase inventada",
            "confidence": 0.85, "verdict": "unfair", "reason": "", "provider": "claude", "model": "opus"}


ROWS = [row("11111111-1111-4111-8111-111111111111", "a-1.0", "2026-11-15T10:00:00.000Z"),
        row("11111111-1111-4111-8111-111111111111", "a-2.0", "2026-11-15T10:00:00.000Z"),
        row("22222222-2222-4222-8222-222222222222", "a-1.0", "2026-11-15T11:30:00.000Z")]


def run(monkeypatch, capsys, *args) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out


def test_feedback_pull(tmp_path, monkeypatch, capsys):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    home.mkdir()
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.delenv("FEEDBACK_ADMIN_TOKEN", raising=False)
    collector = FakeCollector(rows=ROWS)
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    try:
        # Case 1 · no token → the collector answers 401; the pull names the token and exits 1
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 1 and "FEEDBACK_ADMIN_TOKEN" in out, (code, out)
        assert collector.requests[-1]["auth"] is None

        # Case 2 · a wrong token → 401; the pull names the token, never prints its value, and exits 1
        (home / ".env").write_text("FEEDBACK_ADMIN_TOKEN=wrong-token\n")
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 1 and "FEEDBACK_ADMIN_TOKEN" in out and "wrong-token" not in out, (code, out)
        assert not (home / "feedback").exists() or not list((home / "feedback").glob("*.jsonl"))

        # Case 3 · the token in .env → "3 new marks"; one file in feedback/ with the 3 rows
        (home / ".env").write_text(f"FEEDBACK_ADMIN_TOKEN={TOKEN}\n")
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 0 and "3 new marks" in out, (code, out)
        files = list((home / "feedback").glob("*.jsonl"))
        assert len(files) == 1
        assert [json.loads(line) for line in files[0].read_text().splitlines()] == ROWS
        assert collector.requests[-1]["path"] == "/marks"
        assert TOKEN not in out

        # Case 4 · a second pull → it asks only for rows after the last one; "0 new marks"; no new file
        code, out = run(monkeypatch, capsys, "feedback", "pull")
        assert code == 0 and "0 new marks" in out, (code, out)
        assert collector.requests[-1]["query"]["since"] == ["2026-11-15T11:30:00.000Z"]
        assert len(list((home / "feedback").glob("*.jsonl"))) == 1

        # Case 5 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        collector.stop()
    print("PASS S24 A4 · The owner pulls the new rows with the admin token")


# S27 A1 · A mark reaches the collector by itself
#
# Story: A tester marks an ad hominem card as fair. Within a second the author's collector gets one request with that
# mark only (video, second, type, label, quote, confidence, verdict, reason, provider, model, helper version, install id),
# and the card answers at once even when the collector is slow. The tester marks a false-figure card: the next request
# holds only that mark. Two marks given at the same instant are each sent once. Edge case: a changed verdict of a sent
# mark goes out again with the new verdict.
#
# Setup: a temporary helper home with a flag file of 3 flags that names its readers (claude, opus), and an older flag
# file of 1 flag with no readers whose usage log names the part model "sonnet". `config.toml` sets `feedback_url` to a
# fake collector on a free local port; a second fake collector holds each request 2 seconds before it answers. The
# helper HTTP server on another free port. Failing fake `claude` and `codex` commands on PATH. No `/feedback` request
# is made: every send comes from the marks.

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
MARK_FIELDS = {"video_id", "flag_id", "t", "type", "label", "quote", "confidence", "verdict", "reason", "provider",
               "model"}


def wait_for(check, seconds=1.0):
    """True as soon as `check()` holds, False after `seconds`."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return check()


def mark(port, video, flag, verdict, reason=""):
    return request(port, f"/videos/{video}/marks", {"flag_id": flag["id"], "verdict": verdict, "reason": reason})


def test_mark_sends_itself(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    home_with_flags(home)
    collector, slow = FakeCollector(), FakeCollector(delay=2)
    (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
    port, stop = start_helper(home)
    try:
        # Case 1 · one mark → within a second one request holds that mark only, with every field
        assert mark(port, VIDEO, FALLACY, "correct", "sí") == (200, {"ok": True})
        assert wait_for(lambda: len(collector.posts) == 1), collector.posts
        body = collector.posts[0]
        assert set(body) == {"install_id", "helper_version", "marks"}
        assert UUID.fullmatch(body["install_id"]), body["install_id"]
        assert isinstance(body["helper_version"], str) and body["helper_version"]
        assert body["marks"] == [{
            "video_id": VIDEO, "flag_id": FALLACY["id"], "t": 42.0, "type": "fallacy", "label": "ad_hominem",
            "quote": FALLACY["quote"], "confidence": 0.85, "verdict": "correct", "reason": "sí",
            "provider": "claude", "model": "opus"}]
        assert str(tmp_path) not in json.dumps(body)

        # Case 2 · a second mark → the next request holds only that mark, with the same install id
        mark(port, VIDEO, FIGURE, "unfair", "es 11 %")
        assert wait_for(lambda: len(collector.posts) == 2), collector.posts
        assert [(m["flag_id"], m["verdict"], m["reason"]) for m in collector.posts[1]["marks"]] == [
            (FIGURE["id"], "unfair", "es 11 %")]
        assert collector.posts[1]["install_id"] == body["install_id"]

        # Case 3 · a sent mark changes its verdict → it goes out again with the new verdict
        mark(port, VIDEO, FIGURE, "correct")
        assert wait_for(lambda: len(collector.posts) == 3), collector.posts
        assert [(m["flag_id"], m["verdict"]) for m in collector.posts[2]["marks"]] == [(FIGURE["id"], "correct")]

        # Case 4 · two marks at the same instant → each one is sent exactly once
        both = [threading.Thread(target=mark, args=(port, VIDEO, LATER, "unfair")),
                threading.Thread(target=mark, args=(port, OLD_VIDEO, OLD, "correct"))]
        for t in both:
            t.start()
        for t in both:
            t.join()
        sent = lambda: [m["flag_id"] for p in collector.posts[3:] for m in p["marks"]]
        assert wait_for(lambda: len(sent()) >= 2), collector.posts
        time.sleep(0.5)
        assert sorted(sent()) == sorted([LATER["id"], OLD["id"]]), sent()
        old = next(m for p in collector.posts[3:] for m in p["marks"] if m["flag_id"] == OLD["id"])
        assert (old["provider"], old["model"], old["t"]) == (None, "sonnet", 10.0)

        # Case 5 · a collector that takes 2 seconds → the mark is answered at once, and still reaches it
        (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{slow.url}"\n')
        began = time.monotonic()
        assert mark(port, VIDEO, FALLACY, "unfair", "no") == (200, {"ok": True})
        assert time.monotonic() - began < 0.5
        assert wait_for(lambda: len(slow.posts) == 1, 4), slow.posts
        assert [m["flag_id"] for m in slow.posts[0]["marks"]] == [FALLACY["id"]]

        # Case 6 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
        collector.stop()
        slow.stop()
    print("PASS S27 A1 · A mark reaches the collector by itself")


# S27 A2 · With the collector down, the mark waits and goes with the next one
#
# Story: The collector answers 503, then nothing listens on its port. The tester marks 2 cards: the helper takes each
# mark as always and reports no error, and no file appears in `~/.fact-checker/`. The collector comes back; the tester
# marks a third card and one request holds all 3 marks. Edge case: a tester with no connection runs
# `fact-checker feedback send`: the pending marks go to `~/.fact-checker/feedback-<date>.json`, the command prints that
# path, and they stay pending.
#
# Setup: a temporary helper home with a flag file of 3 flags. A fake collector on a free local port that answers 503
# until the test lets it store again, and a local port where nothing listens. The helper HTTP server on another free
# port. Failing fake `claude` and `codex` commands on PATH.

DATED = "feedback-[0-9]*.json"  # the dated file; feedback-sent.json is the record of what was sent


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_down_collector_waits(tmp_path, monkeypatch, capsys):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    home_with_flags(home)
    saved = home / f"feedback-{date.today().isoformat()}.json"
    collector = FakeCollector(fail=503)
    (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
    port, stop = start_helper(home)
    try:
        # Case 1 · the collector answers 503 → the mark is taken as always; nothing stored, no file
        assert mark(port, VIDEO, FALLACY, "correct", "sí") == (200, {"ok": True})
        time.sleep(1)
        assert collector.posts == []
        assert list(home.glob(DATED)) == []

        # Case 2 · nothing listens on the collector's port → the same: taken, no file, the helper keeps answering
        (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "http://127.0.0.1:{closed_port()}"\n')
        assert mark(port, VIDEO, FIGURE, "unfair", "es 11 %") == (200, {"ok": True})
        time.sleep(1)
        assert list(home.glob(DATED)) == []
        assert request(port, f"/videos/{VIDEO}")[0] == 200

        # Case 3 · no connection, `fact-checker feedback send` → the dated file with both marks; its path printed
        code, out = run(monkeypatch, capsys, "feedback", "send")
        assert code == 0 and str(saved) in out, (code, out)
        body = json.loads(saved.read_text())
        assert sorted(m["flag_id"] for m in body["marks"]) == sorted([FALLACY["id"], FIGURE["id"]])
        saved.unlink()

        # Case 4 · the collector is back, a third mark → one request holds all 3 marks; still no file
        collector.fail = None
        (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
        mark(port, VIDEO, LATER, "unfair")
        end = time.monotonic() + 1
        while not collector.posts and time.monotonic() < end:
            time.sleep(0.02)
        time.sleep(0.3)
        assert len(collector.posts) == 1, collector.posts
        assert sorted(m["flag_id"] for m in collector.posts[0]["marks"]) == sorted(
            [FALLACY["id"], FIGURE["id"], LATER["id"]])
        assert list(home.glob(DATED)) == []

        # Case 5 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
        collector.stop()
    print("PASS S27 A2 · With the collector down, the mark waits and goes with the next one")


# S27 A3 · With sharing off, nothing leaves the laptop (the helper side)
#
# Story: The foot of the side panel says "Tus marcas se comparten con el autor para mejorar el detector · Desactivar en
# ⚙" and has no send button. In ⚙ the tester unticks "Compartir mis marcas con el autor". The foot of the panel now says
# "Tus marcas no se comparten · Activar en ⚙", and `share_marks = false` is in `~/.fact-checker/config.toml` beside the
# existing lines. The tester marks a card: after a second the collector has nothing. The tester ticks the box again and
# marks another card: only that new mark goes; the one given while sharing was off never does.
#
# Setup: a temporary helper home with a flag file of 3 flags and a `config.toml` that holds a comment, `feedback_url`
# pointing to a fake collector on a free local port, and a `[models]` table. The helper HTTP server on another free
# port. Failing fake `claude` and `codex` commands on PATH. The ⚙ box and the panel line are checked in
# tests/extension/settings.test.ts (S27 A3).

def test_sharing_off(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    home_with_flags(home)
    collector = FakeCollector()
    config = home / "config.toml"
    config.write_text(f'# my settings\nfeedback_url = "{collector.url}"\n\n[models]\nparts = "sonnet"\n')
    port, stop = start_helper(home)
    try:
        # Case 1 · no share_marks line → not asked yet: S30 A2 Case 2

        # Case 2 · the box unticked → share_marks = false in config.toml, the other lines kept, top level
        assert request(port, "/share", {"share": False}) == (200, {"share": False})
        settings = tomllib.loads(config.read_text())
        assert settings["share_marks"] is False
        assert settings["feedback_url"] == collector.url and settings["models"] == {"parts": "sonnet"}
        assert "# my settings" in config.read_text()
        assert request(port, "/share") == (200, {"share": False})

        # Case 3 · a mark with sharing off → after a second the collector has nothing
        assert mark(port, VIDEO, FALLACY, "correct") == (200, {"ok": True})
        time.sleep(1)
        assert collector.posts == []

        # Case 4 · the box ticked again → share_marks = true, one line; the next mark sends only itself
        assert request(port, "/share", {"share": True}) == (200, {"share": True})
        assert config.read_text().count("share_marks") == 1
        assert tomllib.loads(config.read_text())["share_marks"] is True
        mark(port, VIDEO, FIGURE, "unfair")
        end = time.monotonic() + 1
        while not collector.posts and time.monotonic() < end:
            time.sleep(0.02)
        time.sleep(0.3)
        assert [m["flag_id"] for p in collector.posts for m in p["marks"]] == [FIGURE["id"]]

        # Case 5 · share_marks = false written by hand → a mark sends nothing
        config.write_text(f'share_marks = false\nfeedback_url = "{collector.url}"\n')
        assert request(port, "/share") == (200, {"share": False})
        mark(port, VIDEO, LATER, "unfair")
        time.sleep(1)
        assert len(collector.posts) == 1

        # Case 6 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
        collector.stop()
    print("PASS S27 A3 · With sharing off, nothing leaves the laptop (the helper side)")


# S28 A1 · A whole analysis uploads its flags; a partial one does not
#
# Story: A tester with sharing on clicks "Analizar este vídeo" at 0:00 on an invented 23-second interview. When the
# analysis ends, the collector gets one upload for that video and language "es": the flags, the judge's verdicts, the
# readers (claude, opus), `lang`, `spoken`, the cost, the helper version and the counts of checked claims and
# questions per speaker (S35), and no mark, stop reason or other field.
# The tester starts another video at 0:15: its analysis ends with the first 15 seconds unread, and nothing is uploaded.
#
# Setup: language_fakes (a fake `yt-dlp` with invented captions, a fake `claude` that answers by schema, a failing `codex`),
# a temporary helper home whose `config.toml` points `feedback_url` to the S28 fake collector on a free local port, and
# the helper's own HTTP server on another free port. Each case posts `/videos/<id>?from=<s>&lang=es` as the extension
# does, then polls the flag file until it is no longer running.

ALLOWED = {"video_id", "lang", "spoken", "status", "published_at", "title", "channel", "duration", "speakers",
           "claims", "questions", "readers", "cost_usd", "analysed_until", "helper_version", "flags",
           "summary"}  # S4: each guest's tally


def analyse(base: str, video: str, start: int = 0, lang: str = "es") -> dict:
    """Starts the analysis of `video` from `start` as the extension does, and polls it until it is no longer running."""
    urllib.request.urlopen(urllib.request.Request(f"{base}/videos/{video}?from={start}&lang={lang}", method="POST"),
                           timeout=10)
    for _ in range(300):
        try:
            data = json.loads(urllib.request.urlopen(f"{base}/videos/{video}?at={start}", timeout=10).read())
            if data["status"] != "running":
                return data
        except urllib.error.HTTPError:
            pass
        time.sleep(0.1)
    raise AssertionError(f"FAIL · the analysis of {video} did not finish in 30 s")


def test_whole_analysis_uploads(tmp_path, monkeypatch):
    home, _ = setup(tmp_path, monkeypatch)
    collector = FakeCollector()
    (home / "config.toml").write_text(f'share_marks = true\nfeedback_url = "{collector.url}"\n')
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        # Case 1 · the whole video read from 0:00 → one PUT /analyses/esview?lang=es
        data = analyse(base, "esview", 0)
        assert data["status"] == "done", f"FAIL S28 A1 · {data['status']} ({data.get('stop_reason')})"
        puts = collector.wait_puts(1)
        assert len(puts) == 1, f"FAIL S28 A1 · {len(puts)} uploads after a whole analysis"
        put = puts[0]
        assert put["path"] == "/analyses/esview" and put["query"] == {"lang": ["es"]}, \
            f"FAIL S28 A1 · uploaded to {put['path']} {put['query']}"

        # Case 2 · the body → the install id, the stripped analysis and its prompts file (S7), nothing else
        body = put["body"]
        assert set(body) == {"install_id", "analysis", "prompts"}, f"FAIL S28 A1 · body fields {sorted(body)}"
        assert body["install_id"] == (home / "install-id").read_text().strip(), "FAIL S28 A1 · not the install id"
        shared = body["analysis"]
        assert set(shared) <= ALLOWED, f"FAIL S28 A1 · extra fields {sorted(set(shared) - ALLOWED)}"
        assert {"flags", "readers", "lang", "spoken", "cost_usd", "helper_version", "status"} <= set(shared), \
            f"FAIL S28 A1 · missing fields {sorted({'flags', 'readers', 'lang', 'spoken', 'cost_usd', 'helper_version'} - set(shared))}"
        assert (shared["video_id"], shared["lang"], shared["spoken"], shared["status"]) == ("esview", "es", "es", "done")
        assert shared["readers"]["parts"] == {"provider": "claude", "model": "opus"}, \
            f"FAIL S28 A1 · readers {shared['readers']}"

        # Case 3 · the flags → the same flags as the local file, with no mark
        local = json.loads((home / "videos" / "esview.json").read_text())
        assert shared["flags"] and [f["id"] for f in shared["flags"]] == [f["id"] for f in local["flags"]], \
            "FAIL S28 A1 · the uploaded flags differ from the local ones"
        assert all("mark" not in f for f in shared["flags"]), "FAIL S28 A1 · a mark was uploaded"

        # Case 4 · a video started at 0:15 → done, the first 15 seconds unread, no upload
        data = analyse(base, "enview", 15)
        assert data["status"] == "done", f"FAIL S28 A1 · {data['status']} ({data.get('stop_reason')})"
        assert all(f["t"] >= 15 for f in data["flags"]), "FAIL S28 A1 · the first 15 seconds were read"
        time.sleep(1.5)
        assert len(collector.puts()) == 1, "FAIL S28 A1 · a partial analysis was uploaded"
    finally:
        httpd.shutdown()
        collector.stop()
    print("PASS S28 A1 · A whole analysis uploads its flags; a partial one does not")


# S28 A2 · A second viewer gets the shared flags at once and for free (the helper side)
#
# Story: The collector holds a Spanish analysis of a video with 2 flags. A second tester with a Spanish browser opens
# that video: the 2 flags show at once, with no LLM reading, no "Analizar este vídeo" button and the note "Análisis
# compartido · gratis" ("Shared analysis · free" in English); the helper keeps the file with `"source": "shared"`. A
# tester with an English browser opens the same video, gets no shared flags and sees "Analyze this video".
#
# Setup: failing fake `claude` and `codex` commands on PATH, the S28 fake collector on a free local port holding the
# invented Spanish analysis, and two temporary helper homes (a Spanish viewer, an English viewer) whose `config.toml`
# points `feedback_url` to it, each with the helper HTTP server on a free port. Each case sends the extension's first
# poll, `GET /videos/<id>?at=0&lang=<es|en>`. The note and the button are checked in tests/extension/start.test.ts (S28 A2).

def test_shared_flags_at_once(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    collector = FakeCollector(analyses={(SHARED_VIDEO, "es"): ANALYSIS})
    homes = {lang: tmp_path / f"home-{lang}" for lang in ("es", "en")}
    helpers = {}
    for lang, home in homes.items():
        home.mkdir()
        (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
        helpers[lang] = start_helper(home)
    try:
        # Case 1 · a Spanish viewer opens the video → 200 with the 2 shared flags, status done, source shared
        status, data = request(helpers["es"][0], f"/videos/{SHARED_VIDEO}?at=0&lang=es")
        assert status == 200, f"FAIL S28 A2 · the Spanish viewer got {status}"
        assert [f["id"] for f in data["flags"]] == [f["id"] for f in ANALYSIS["flags"]], "FAIL S28 A2 · not the shared flags"
        assert (data["status"], data.get("source")) == ("done", "shared"), \
            f"FAIL S28 A2 · status {data['status']!r}, source {data.get('source')!r}"

        # Case 2 · the helper keeps the file with source shared
        saved = json.loads((homes["es"] / "videos" / f"{SHARED_VIDEO}.json").read_text())
        assert saved.get("source") == "shared" and len(saved["flags"]) == 2, "FAIL S28 A2 · no local shared copy"

        # Case 3 · the download → one GET with only the language: no install id, no body
        gets = [r for r in collector.requests if r["method"] == "GET"]
        assert len(gets) == 1, f"FAIL S28 A2 · {len(gets)} downloads"
        assert gets[0]["path"] == f"/analyses/{SHARED_VIDEO}" and gets[0]["query"] == {"lang": ["es"]}, \
            f"FAIL S28 A2 · asked {gets[0]['path']} {gets[0]['query']}"
        install = (homes["es"] / "install-id")
        sent = json.dumps(gets[0])
        assert not install.exists() or install.read_text().strip() not in sent, "FAIL S28 A2 · the install id was sent"

        # Case 4 · a second poll → served from the local copy, no new download
        assert request(helpers["es"][0], f"/videos/{SHARED_VIDEO}?at=3&lang=es")[0] == 200
        assert len([r for r in collector.requests if r["method"] == "GET"]) == 1, "FAIL S28 A2 · downloaded twice"

        # Case 5 · an English viewer → 404, so the extension shows "Analyze this video"; nothing saved
        status, _ = request(helpers["en"][0], f"/videos/{SHARED_VIDEO}?at=0&lang=en")
        assert status == 404, f"FAIL S28 A2 · the English viewer got {status}"
        assert not (homes["en"] / "videos" / f"{SHARED_VIDEO}.json").exists(), "FAIL S28 A2 · a file in another language"

        # Case 6 · the whole run → no `claude` or `codex` command was called, no usage line
        assert not cli_log.exists() or cli_log.read_text() == "", "FAIL S28 A2 · an LLM reading ran"
        assert not any((h / "usage.log").exists() for h in homes.values()), "FAIL S28 A2 · a usage line was written"
    finally:
        for _, stop in helpers.values():
            stop()
        collector.stop()
    print("PASS S28 A2 · A second viewer gets the shared flags at once and for free (the helper side)")


# S28 A4 · With sharing off nothing is uploaded, and downloading still works
#
# Story: A tester unticks "Compartir mis marcas y análisis" in ⚙ and analyses a whole video: the collector gets no
# upload. The same tester opens a video that the collector holds in Spanish and sees its flags at once.
#
# Setup: language_fakes (a fake `yt-dlp` with invented captions, a fake `claude` that answers by schema, a failing `codex`),
# the S28 fake collector on a free local port holding the invented Spanish analysis, a temporary helper home whose
# `config.toml` points `feedback_url` to it, and the helper's own HTTP server on another free port. The ⚙ box is the
# S27 one: it posts `/share` with `{"share": false}`.

def test_sharing_off_uploads_nothing(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    collector = FakeCollector(analyses={(SHARED_VIDEO, "es"): ANALYSIS})
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_port
    base = f"http://127.0.0.1:{port}"
    try:
        # Case 1 · the ⚙ box unticked → sharing off
        assert request(port, "/share", {"share": False}) == (200, {"share": False})

        # Case 2 · a whole analysis from 0:00 → done, and no upload
        data = analyse(base, "esview")
        assert data["status"] == "done", f"FAIL S28 A4 · the analysis did not end done: {data}"
        time.sleep(1.5)
        assert collector.puts() == [], "FAIL S28 A4 · an analysis was uploaded with sharing off"

        # Case 3 · a video the collector holds in Spanish → its flags at once, with no reading
        before = len(readings(log))
        status, shared = request(port, f"/videos/{SHARED_VIDEO}?at=0&lang=es")
        assert status == 200 and shared.get("source") == "shared", f"FAIL S28 A4 · download with sharing off: {status}"
        assert [f["id"] for f in shared["flags"]] == [f["id"] for f in ANALYSIS["flags"]]
        assert len(readings(log)) == before, "FAIL S28 A4 · an LLM reading ran for a shared video"
    finally:
        httpd.shutdown()
        collector.stop()
    print("PASS S28 A4 · With sharing off nothing is uploaded, and downloading still works")


# S30 A1 (helper part) · Only the owner's approved analyses are served
#
# Story: A stranger uploads an analysis of video "abcdefgh" in Spanish: the collector answers 202 and serves nothing for
# it. The owner runs `fact-checker shared list` and sees one line: abcdefgh, es, opus, 2 flags, the uploader's install id
# and the date. `fact-checker shared approve abcdefgh es` makes that upload served to anyone; with two uploads of one
# video it names both and approves only the one given with `--install`. `reject` on another one deletes it
# and it is never served. An upload from the owner's own helper (with the admin token in its `.env`) is served at once.
# A row shared before this slice is pending until the owner approves it.
#
# Setup: a fake collector on a free local port that holds 2 pending uploads (abcdefgh and otherone, in Spanish), answers
# the owner's list, approve and reject only with the admin token, answers 404 to a review of an unknown video, and records
# every request with its Authorization header. A temporary helper home whose `config.toml` sets `feedback_url` to it.
# Failing fake `claude` and `codex` commands on PATH. What the collector stores and serves is checked in
# tests/collector/analyses.test.ts (S30 A1).

STRANGER = "11111111-1111-4111-8111-111111111111"
OTHER_INSTALL = "22222222-2222-4222-8222-222222222222"
PENDING = [
    {"video_id": "abcdefgh", "lang": "es", "model": "opus", "flags": 2, "install_id": STRANGER,
     "received_at": "2026-11-15T10:00:00.000Z"},
    {"video_id": "otherone", "lang": "es", "model": "sonnet", "flags": 5, "install_id": STRANGER,
     "received_at": "2026-11-15T11:00:00.000Z"},
    {"video_id": "twotimes", "lang": "es", "model": "sonnet", "flags": 3, "install_id": STRANGER,
     "received_at": "2026-11-15T12:00:00.000Z"},
    {"video_id": "twotimes", "lang": "es", "model": "opus", "flags": 9, "install_id": OTHER_INSTALL,
     "received_at": "2026-11-15T13:00:00.000Z"},
]


def test_shared_review(tmp_path, monkeypatch, capsys):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    home.mkdir()
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.delenv("FEEDBACK_ADMIN_TOKEN", raising=False)
    collector = FakeCollector(pending=PENDING)
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    try:
        # Case 1 · no admin token → the list names FEEDBACK_ADMIN_TOKEN and exits 1
        code, out = run(monkeypatch, capsys, "shared", "list")
        assert code == 1 and "FEEDBACK_ADMIN_TOKEN" in out, f"FAIL S30 A1 · no token: {code} {out!r}"

        # Case 2 · the token in .env → one line per pending upload: video, lang, model, flags, install id, date
        (home / ".env").write_text(f"FEEDBACK_ADMIN_TOKEN={TOKEN}\n")
        code, out = run(monkeypatch, capsys, "shared", "list")
        assert code == 0, f"FAIL S30 A1 · list exited {code}: {out!r}"
        line = next((x for x in out.splitlines() if "abcdefgh" in x), "")
        for part in ("abcdefgh", " es ", "opus", "2 flags", STRANGER, "2026-11-15"):
            assert part in f" {line} ", f"FAIL S30 A1 · the list line misses {part!r}: {line!r}"
        assert "otherone" in out and TOKEN not in out
        assert collector.requests[-1]["path"] == "/analyses" and collector.requests[-1]["auth"] == f"Bearer {TOKEN}"

        # Case 3 · approve abcdefgh es → POST /analyses/abcdefgh/approve naming its one upload, with the token; exit 0
        code, out = run(monkeypatch, capsys, "shared", "approve", "abcdefgh", "es")
        last = collector.requests[-1]
        assert code == 0, f"FAIL S30 A1 · approve exited {code}: {out!r}"
        assert (last["method"], last["path"], last["query"], last["auth"]) == \
            ("POST", "/analyses/abcdefgh/approve",
             {"lang": ["es"], "install": [STRANGER], "at": ["2026-11-15T10:00:00.000Z"]}, f"Bearer {TOKEN}")

        # Case 3b · two uploads of twotimes → approve names both and sends nothing; --install picks one; exit 0
        sent = len(collector.requests)
        code, out = run(monkeypatch, capsys, "shared", "approve", "twotimes", "es")
        assert code == 1 and STRANGER in out and OTHER_INSTALL in out, f"FAIL · two uploads: {code} {out!r}"
        assert all(r["method"] != "POST" for r in collector.requests[sent:]), "FAIL · approved one of two uploads"
        code, out = run(monkeypatch, capsys, "shared", "approve", "twotimes", "es", "--install", STRANGER[:8])
        last = collector.requests[-1]
        assert code == 0 and last["path"] == "/analyses/twotimes/approve" and last["query"]["install"] == [STRANGER], \
            f"FAIL · --install: {code} {last}"

        # Case 4 · reject otherone es → POST /analyses/otherone/reject?lang=es; the list is then empty
        code, out = run(monkeypatch, capsys, "shared", "reject", "otherone", "es")
        last = collector.requests[-1]
        assert code == 0 and (last["method"], last["path"]) == ("POST", "/analyses/otherone/reject"), \
            f"FAIL S30 A1 · reject: {code} {last['path']}"
        code, out = run(monkeypatch, capsys, "shared", "list")
        assert code == 0 and "0 pending" in out, f"FAIL S30 A1 · empty list: {out!r}"

        # Case 5 · approve a video with nothing pending → the video named, exit 1
        code, out = run(monkeypatch, capsys, "shared", "approve", "zzzzzzzz", "en")
        assert code == 1 and "zzzzzzzz" in out, f"FAIL S30 A1 · unknown video: {code} {out!r}"

        # Case 6 · the owner's helper uploads → the PUT carries the admin token; a tester's helper sends none
        analyses.upload(home, collector.url, ANALYSIS)
        assert collector.requests[-1]["method"] == "PUT" and collector.requests[-1]["auth"] == f"Bearer {TOKEN}", \
            "FAIL S30 A1 · the owner's upload has no admin token"
        (home / ".env").write_text("")
        analyses.upload(home, collector.url, ANALYSIS)
        assert collector.requests[-1]["method"] == "PUT" and collector.requests[-1]["auth"] is None, \
            "FAIL S30 A1 · a tester's upload carries an Authorization header"

        # Case 7 · the whole run → no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        collector.stop()
    print("PASS S30 A1 · Only the owner's approved analyses are served (the helper side)")


# S30 A2 (helper part) · Nothing is shared before the person says yes
#
# Story: A new tester has never answered. They click "✓ De acuerdo" on a card: a box asks "¿Compartir tus marcas y
# análisis con el autor para mejorar el detector? Se envían el aviso, la frase, tu motivo y el vídeo; nada de tu equipo."
# with "Sí, compartir", "No" and a link to the privacy notice (in English with an English browser). Until they answer,
# the collector gets nothing. "Sí, compartir" sends that mark and later whole analyses; "No" keeps them on the laptop.
# The next mark or analysis asks nothing.
#
# Setup: language_fakes (a fake `yt-dlp` with invented captions, a fake `claude` that answers by schema, a failing `codex`),
# the S28 fake collector on a free local port (it records every PUT and POST), a temporary helper home whose
# `config.toml` holds only `feedback_url` (a new install: never answered), and the helper's own HTTP server on another
# free port. The box itself is checked in tests/extension/settings.test.ts (S30 A2); its answer reaches the helper as `POST /share`.

EXAMPLE = Path(server.__file__).parent / "config.example.toml"


def test_consent_first(tmp_path, monkeypatch):
    home, _ = setup(tmp_path, monkeypatch)
    monkeypatch.delenv("FEEDBACK_ADMIN_TOKEN", raising=False)
    collector = FakeCollector()
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_port
    base = f"http://127.0.0.1:{port}"
    posts = lambda: [r for r in collector.requests if r["method"] == "POST"]  # noqa: E731
    try:
        # Case 1 · the settings that setup copies → no share_marks line: a new install has not answered
        assert "share_marks" not in tomllib.loads(EXAMPLE.read_text()), \
            "FAIL S30 A2 · config.example.toml answers the question for the person"

        # Case 2 · never answered → GET /share says null (not asked), not true
        assert request(port, "/share") == (200, {"share": None}), f"FAIL S30 A2 · {request(port, '/share')}"

        # Case 3 · never answered, a whole analysis → done, and no upload
        data = analyse(base, "esview")
        assert data["status"] == "done" and data["flags"], f"FAIL S30 A2 · {data['status']}"
        time.sleep(1.5)
        assert collector.puts() == [], "FAIL S30 A2 · an analysis was uploaded before the answer"

        # Case 4 · never answered, a mark → kept, and nothing sent
        assert mark(port, "esview", data["flags"][0], "correct") == (200, {"ok": True})
        time.sleep(1)
        assert posts() == [], "FAIL S30 A2 · a mark was sent before the answer"

        # Case 5 · "Sí, compartir" → share_marks = true; the next mark goes, and the next whole analysis uploads
        assert request(port, "/share", {"share": True}) == (200, {"share": True})
        assert tomllib.loads((home / "config.toml").read_text())["share_marks"] is True
        assert mark(port, "esview", data["flags"][-1], "correct") == (200, {"ok": True})
        end = time.monotonic() + 2
        while not posts() and time.monotonic() < end:
            time.sleep(0.05)
        assert [m["flag_id"] for p in posts() for m in p["body"]["marks"]] == [data["flags"][-1]["id"]], \
            "FAIL S30 A2 · after yes, the new mark was not sent alone"
        assert analyse(base, "enview", lang="en")["status"] == "done"
        assert len(collector.wait_puts(1)) == 1, "FAIL S30 A2 · after yes, the whole analysis was not uploaded"

        # Case 6 · "No" → share_marks = false; GET /share says false; a mark sends nothing
        assert request(port, "/share", {"share": False}) == (200, {"share": False})
        assert request(port, "/share") == (200, {"share": False})
        sent = len(posts())
        assert mark(port, "enview", analyse(base, "enview", lang="en")["flags"][0], "correct") == (200, {"ok": True})
        time.sleep(1)
        assert len(posts()) == sent, "FAIL S30 A2 · a mark was sent after no"
        assert len(collector.puts()) == 1, "FAIL S30 A2 · an analysis was uploaded after no"
    finally:
        httpd.shutdown()
        collector.stop()
    print("PASS S30 A2 · Nothing is shared before the person says yes (the helper side)")


# S30 A3 (helper part) · The player says "signals, not verdicts" and what an analysis spends
#
# Story: A person with a Spanish browser sees a card with "90%" confidence, and the foot of the side panel reads "Señales
# automáticas, no veredictos" ("Automatic signals, not verdicts" in English). On a video not analysed yet, under
# "Analizar este vídeo" a line reads "Usa tu suscripción de Claude: un vídeo de 1 h gasta una parte notable de tu
# límite"; with Codex it names ChatGPT; with an API provider it reads "Se cobra en tu cuenta de API".
#
# Setup: a temporary helper home whose `config.toml` changes per case, the helper's own HTTP server on a free port, and
# failing fake `claude` and `codex` commands on PATH. The line itself is checked in tests/extension/start.test.ts (S30 A3);
# here the helper names the provider that reads the parts, which picks the line.

def test_provider(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    home.mkdir()
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.delenv("FACT_CHECK_PROVIDER", raising=False)
    port, stop = start_helper(home)
    try:
        # Case 1 · no settings → claude
        assert request(port, "/provider") == (200, {"provider": "claude"}), f"FAIL S30 A3 · {request(port, '/provider')}"

        # Case 2 · provider = "codex" → codex
        (home / "config.toml").write_text('provider = "codex"\n')
        assert request(port, "/provider") == (200, {"provider": "codex"})

        # Case 3 · the parts on their own API provider → that provider, not the default one
        (home / "config.toml").write_text('provider = "claude"\n\n[roles.parts]\nprovider = "chat"\nmodel = "m"\n')
        assert request(port, "/provider") == (200, {"provider": "chat"})

        # Case 4 · no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
    print("PASS S30 A3 · The helper names the provider that reads the parts")
