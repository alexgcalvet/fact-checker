import json
import subprocess
from pathlib import Path

from fact_checker.core.flags import Segment

CLI = Path(__file__).with_name("whisper_cli.py")  # mlx-whisper: Apple silicon
FASTER_CLI = Path(__file__).with_name("faster_whisper_cli.py")  # faster-whisper: CPU of any macOS or Linux machine


class Whisper:
    """Timed words of a video's audio and their language through a Whisper script (`CLI` or `FASTER_CLI`), in its own
    uv environment; cached in `workdir`."""

    def __init__(self, workdir: Path, audio, cli: Path = CLI):
        self.workdir = Path(workdir)
        self.audio = audio
        self.cli = cli

    def segments(self, video_id: str) -> list[Segment]:
        out = self.workdir / f"{video_id}.words.json"
        if not out.exists():
            self.workdir.mkdir(parents=True, exist_ok=True)
            run = subprocess.run(["uv", "run", "--quiet", "--script", str(self.cli), str(self.audio.audio(video_id)), str(out)],
                                 capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(f"transcription failed: {run.stderr.strip()[-200:]}")
        return [Segment(t=w["start"], text=w["word"].strip()) for w in json.loads(out.read_text()) if w["word"].strip()]

    def language(self, video_id: str) -> str:
        """`en` when the engine heard English, else `es`; a cache from before S26 has no language and reads Spanish."""
        found = self.workdir / f"{video_id}.words.lang"
        return "en" if found.exists() and found.read_text().strip() == "en" else "es"
