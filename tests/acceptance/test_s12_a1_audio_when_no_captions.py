"""S12 A1 · A video with no Spanish captions is analysed from its audio

Story: The helper analyses an invented video whose captions exist only in English. It transcribes the
audio instead and the flag file gets a fallacy flag at the second where the transcript puts the words,
with the publish date of the video.
Edge case: when the video has Spanish captions, the audio is not transcribed.

Setup: a fake yt-dlp on the PATH that prints the publish date 20240315 and writes Spanish captions only
for the video "captioned" (the invented dialogue of tests/fakes/youtube/); the YouTube adapter with the
Whisper adapter as its fallback; the Whisper transcript of the video "uncaptioned" already cached in the
helper home from the synthetic fake tests/fakes/whisper/transcribe.json, where "autoridad" has a low
probability; an audio source that records each request; a fake Claude that flags "La oposición no tiene
autoridad para hablar." as an ad hominem; a temporary helper home.
"""
import json
import os
import shutil
from pathlib import Path

from fact_checker.adapters.whisper import Whisper
from fact_checker.adapters.youtube import YouTube
from fact_checker.server import run_analysis

FAKES = Path(__file__).parents[1] / "fakes"

FAKE_YTDLP = f"""#!/usr/bin/env python3
import shutil, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1].replace("%(id)s", "")
video = args[-1].split("v=")[-1]
if video == "captioned":
    shutil.copy("{FAKES / 'youtube' / 'invented-dialogue.json3'}", out + "captioned.es.json3")
print("20240315")
"""


class Audio:
    def __init__(self):
        self.requests = []

    def audio(self, video_id):
        self.requests.append(video_id)
        raise RuntimeError("no audio in this test")


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": []}
        return {"flags": [{"quote": "La oposición no tiene autoridad para hablar.", "label": "ad_hominem",
                           "speaker": "ministro", "reason": "Ataca a la oposición.", "confidence": 0.9}],
                "claims": []}


def helper(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "yt-dlp").write_text(FAKE_YTDLP)
    (bin_dir / "yt-dlp").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    speech = tmp_path / "home" / "speech"
    speech.mkdir(parents=True)
    shutil.copy(FAKES / "whisper" / "transcribe.json", speech / "uncaptioned.words.json")
    audio = Audio()
    youtube = YouTube(tmp_path / "home" / "captions", speech=Whisper(speech, audio))
    return youtube, audio, tmp_path / "home"


def test_audio_when_no_captions(tmp_path, monkeypatch):
    youtube, audio, home = helper(tmp_path, monkeypatch)

    # Case 1 · no Spanish captions → the fallacy quotes the Whisper words, at the second of the first word
    run_analysis("uncaptioned", 0, transcript=youtube, llm=FakeClaude(), home=home)
    data = json.loads((home / "videos" / "uncaptioned.json").read_text())
    assert data["status"] == "done", data
    assert [(f["label"], f["quote"]) for f in data["flags"]] == [
        ("ad_hominem", "La oposición no tiene autoridad para hablar.")], data["flags"]
    assert abs(data["flags"][0]["t"] - 12.4) < 0.01

    # Case 2 · the captions step still gives the date → the publish date of the video
    assert data["published_at"] == "2024-03-15"

    # Case 3 · Spanish captions exist → the audio is not requested and the captions are analysed
    run_analysis("captioned", 0, transcript=youtube, llm=FakeClaude(), home=home)
    data = json.loads((home / "videos" / "captioned.json").read_text())
    assert data["status"] == "done", data
    assert audio.requests == []
    assert not (home / "speech" / "captioned.words.json").exists()
    assert abs(data["flags"][0]["t"] - 42.0) < 0.01
    print("PASS S12 A1 · A video with no Spanish captions is analysed from its audio")
