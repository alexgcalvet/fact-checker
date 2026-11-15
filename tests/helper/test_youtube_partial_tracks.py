"""YouTube may refuse one caption track (HTTP 429 on an automatic translation) while yt-dlp already wrote another:
the video is read from the track it has, not failed."""
import json
import os

import pytest

from fact_checker.adapters.youtube import YouTube

TRACK = {"events": [{"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "hola a todos"}]}]}


def fake_ytdlp(tmp_path, monkeypatch, write: bool):
    script = tmp_path / "bin" / "yt-dlp"
    script.parent.mkdir()
    out = tmp_path / "captions" / "vid123"
    body = f"echo '{json.dumps(TRACK)}' > {out}/vid123.es-orig.json3\n" if write else ""
    script.write_text(f"#!/bin/sh\nmkdir -p {out}\n{body}printf '20261114\\t891\\tCanal\\tTitulo\\n'\n"
                      "echo 'ERROR: Unable to download video subtitles for en: HTTP Error 429' >&2\nexit 1\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{script.parent}{os.pathsep}{os.environ['PATH']}")


def test_a_refused_track_does_not_fail_the_video(tmp_path, monkeypatch):
    fake_ytdlp(tmp_path, monkeypatch, write=True)
    transcript = YouTube(tmp_path / "captions").fetch("vid123")
    assert transcript.language == "es" and transcript.title == "Titulo"


def test_no_track_at_all_still_fails(tmp_path, monkeypatch):
    fake_ytdlp(tmp_path, monkeypatch, write=False)
    with pytest.raises(Exception):
        YouTube(tmp_path / "captions").fetch("vid123")
