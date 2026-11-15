# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["pyannote.audio==4.0.7"]
# ///
"""Voice turns of a WAV file as JSON: [{start, end, speaker}]. Runs in its own uv environment."""
import json
import os
import sys

import torch
from pyannote.audio import Pipeline

MODEL = "pyannote/speaker-diarization-community-1"


def main() -> None:
    audio, out = sys.argv[1], sys.argv[2]
    pipeline = Pipeline.from_pretrained(MODEL, token=os.environ["HF_TOKEN"])
    pipeline.to(torch.device("mps" if torch.backends.mps.is_available() else "cpu"))
    result = pipeline(audio)
    turns = [{"start": round(t.start, 2), "end": round(t.end, 2), "speaker": s}
             for t, s in result.exclusive_speaker_diarization]
    with open(out, "w") as f:
        json.dump(turns, f)


if __name__ == "__main__":
    main()
