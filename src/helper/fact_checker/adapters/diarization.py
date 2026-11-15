import json
import subprocess
from pathlib import Path

CLI = Path(__file__).with_name("diarize_cli.py")


class Diarizer:
    """Voice turns of a video through pyannote, in its own uv environment; the token comes from HF_TOKEN."""

    def __init__(self, workdir: Path, audio):
        self.workdir = Path(workdir)
        self.audio = audio

    def turns(self, video_id: str) -> list[dict]:
        out = self.workdir / f"{video_id}.turns.json"
        if not out.exists():
            self.workdir.mkdir(parents=True, exist_ok=True)
            run = subprocess.run(["uv", "run", "--quiet", "--script", str(CLI), str(self.audio.audio(video_id)), str(out)],
                                 capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(f"diarization failed: {run.stderr.strip()[-200:]}")
        return json.loads(out.read_text())
