"""Contract · pyannote (Hugging Face) and YouTube audio · diarize

The first minute of a real video's audio, fetched as the helper fetches it, is a 16 kHz mono WAV, and
diarize_cli.py returns voice turns with the same field names and types as the recorded fake in
tests/fakes/pyannote/diarize.json. Values are never compared. Skips when S1_VIDEO_URL or HF_TOKEN is not
set, or when yt-dlp fails.
"""
import json
import os
import subprocess
import wave
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "pyannote" / "diarize.json"


def test_contract_pyannote_diarize(tmp_path):
    url = os.environ.get("S1_VIDEO_URL")
    if not url or not os.environ.get("HF_TOKEN"):
        pytest.skip("SKIP contract pyannote: sandbox not reachable")
    run = subprocess.run(["yt-dlp", "-x", "--audio-format", "wav", "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                          "--download-sections", "*0-60", "-o", str(tmp_path / "a.%(ext)s"), url], capture_output=True)
    audio = tmp_path / "a.wav"
    if run.returncode or not audio.exists():
        pytest.skip("SKIP contract pyannote: sandbox not reachable")
    with wave.open(str(audio)) as w:
        assert (w.getnchannels(), w.getframerate()) == (1, 16000), "FAIL contract youtube: audio format"

    from fact_checker.adapters.diarization import CLI
    out = tmp_path / "turns.json"
    run = subprocess.run(["uv", "run", "--quiet", "--script", str(CLI), str(audio), str(out)],
                         capture_output=True, text=True)
    assert run.returncode == 0, f"FAIL contract pyannote: {run.stderr[-300:]}"
    live = json.loads(out.read_text())
    fake = json.loads(FAKE.read_text())
    assert isinstance(live, list) and live, "FAIL contract pyannote: turns"
    for field, value in fake[0].items():
        assert type(live[0].get(field)).__name__ == type(value).__name__, f"FAIL contract pyannote: {field}"
