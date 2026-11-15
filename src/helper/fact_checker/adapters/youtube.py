import json
import subprocess
from dataclasses import replace
from pathlib import Path

from fact_checker.core.flags import Segment, Transcript

__all__ = ["YouTube", "parse_json3", "Segment", "Transcript"]


def parse_json3(data: dict, published_at: str | None) -> Transcript:
    segments = []
    for event in data.get("events", []):
        start = event.get("tStartMs", 0)
        for seg in event.get("segs", []):
            text = seg.get("utf8", "").strip()
            if text:
                segments.append(Segment(t=(start + seg.get("tOffsetMs", 0)) / 1000, text=text))
    return Transcript(segments=sorted(segments, key=lambda s: s.t), published_at=published_at)


# The caption tracks in order: an `-orig` track is the video's own speech, so a translated track never wins over it.
TRACKS = ("es-orig", "en-orig", "es", "en")


class YouTube:
    """Captions (the first of TRACKS) with their language, the publish date, title, channel and duration, and the audio
    through yt-dlp.

    With no Spanish or English captions, `speech` transcribes the audio, if given.
    """

    def __init__(self, workdir: Path, speech=None):
        self.workdir = Path(workdir)
        self.speech = speech

    def fetch(self, video_id: str) -> Transcript:
        out = self.workdir / video_id
        out.mkdir(parents=True, exist_ok=True)
        run = subprocess.run(
            ["yt-dlp", "--no-simulate", "--skip-download", "--write-subs", "--write-auto-subs",
             "--sub-langs", ",".join(TRACKS), "--sub-format", "json3", "--print", "%(upload_date)s\t%(duration)s\t%(channel)s\t%(title)s",
             "-o", str(out / "%(id)s"), f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True)
        # YouTube can refuse one track (HTTP 429 on an automatic translation) after another was written: yt-dlp
        # then exits 1, and the video is read from the tracks it has.
        if run.returncode and not any(out.glob(f"{video_id}.*.json3")):
            raise subprocess.CalledProcessError(run.returncode, run.args, run.stdout, run.stderr)
        # A yt-dlp that prints only the date (an older fake) leaves the other fields empty.
        date, duration, channel, title = (run.stdout.strip().splitlines()[-1].split("\t", 3) + ["", "", ""])[:4]
        published_at = f"{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 else None
        # A live stream has no duration yet: yt-dlp prints NA.
        meta = {"title": title or None, "channel": channel or None, "duration": float(duration) if duration.isdigit() else None}
        for track in TRACKS:
            path = out / f"{video_id}.{track}.json3"
            if path.exists():
                return replace(parse_json3(json.loads(path.read_text()), published_at), language=track[:2], **meta)
        if self.speech:
            return Transcript(segments=self.speech.segments(video_id), published_at=published_at,
                              language=self.speech.language(video_id), **meta)
        raise RuntimeError("no Spanish captions, and no speech engine on this machine: run fact-checker doctor")

    def audio(self, video_id: str) -> Path:
        """The audio as 16 kHz mono WAV, downloaded once."""
        wav = self.workdir / video_id / f"{video_id}.wav"
        if not wav.exists():
            subprocess.run(
                ["yt-dlp", "-x", "--audio-format", "wav", "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                 "-o", str(wav.parent / "%(id)s.%(ext)s"), f"https://www.youtube.com/watch?v={video_id}"],
                capture_output=True, text=True, check=True)
        return wav
