"""Contract · Whisper (faster-whisper) · transcribe

The first minute of a real video's audio, fetched as the helper fetches it, goes through faster_whisper_cli.py, which
returns timed words with the same field names and types as the synthetic fake of mlx-whisper in
tests/fakes/whisper/transcribe.json: the two engines are interchangeable. Values are never compared. Skips when
S1_VIDEO_URL is not set, when uv is missing, or when yt-dlp fails.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "whisper" / "transcribe.json"


def test_contract_faster_whisper_transcribe(tmp_path):
    url = os.environ.get("S1_VIDEO_URL")
    if not url or not shutil.which("uv"):
        pytest.skip("SKIP contract faster-whisper: sandbox not reachable")
    run = subprocess.run(["yt-dlp", "-x", "--audio-format", "wav", "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                          "--download-sections", "*0-60", "-o", str(tmp_path / "a.%(ext)s"), url], capture_output=True)
    audio = tmp_path / "a.wav"
    if run.returncode or not audio.exists():
        pytest.skip("SKIP contract faster-whisper: sandbox not reachable")

    from fact_checker.adapters.whisper import FASTER_CLI
    out = tmp_path / "words.json"
    run = subprocess.run(["uv", "run", "--quiet", "--script", str(FASTER_CLI), str(audio), str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, f"FAIL contract faster-whisper: {run.stderr[-300:]}"
    live = json.loads(out.read_text())
    fake = json.loads(FAKE.read_text())
    assert isinstance(live, list) and live, "FAIL contract faster-whisper: words"
    for field, value in fake[0].items():
        assert type(live[0].get(field)).__name__ == type(value).__name__, f"FAIL contract faster-whisper: {field}"
