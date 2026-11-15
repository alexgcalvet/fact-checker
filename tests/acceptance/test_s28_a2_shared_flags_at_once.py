"""S28 A2 · A second viewer gets the shared flags at once and for free (the helper side)

Story: The collector holds a Spanish analysis of a video with 2 flags. A second tester with a Spanish browser opens
that video: the 2 flags show at once, with no LLM reading, no "Analizar este vídeo" button and the note "Análisis
compartido · gratis" ("Shared analysis · free" in English); the helper keeps the file with `"source": "shared"`. A
tester with an English browser opens the same video, gets no shared flags and sees "Analyze this video".

Setup: failing fake `claude` and `codex` commands on PATH, the S28 fake collector on a free local port holding the
invented Spanish analysis, and two temporary helper homes (a Spanish viewer, an English viewer) whose `config.toml`
points `feedback_url` to it, each with the helper HTTP server on a free port. Each case sends the extension's first
poll, `GET /videos/<id>?at=0&lang=<es|en>`. The note and the button are checked in s28-a2-shared-note.test.ts.
"""
import json

from s23_fakes import fail_clis
from s24_fakes import request, start_helper
from s28_fakes import ANALYSIS, SHARED_VIDEO, FakeCollector


def test_shared_flags_at_once(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    collector = FakeCollector({(SHARED_VIDEO, "es"): ANALYSIS})
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
