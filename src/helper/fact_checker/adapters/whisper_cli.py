# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["mlx-whisper==0.4.3"]
# ///
"""Timed words of a WAV file as JSON: [{word, start, end, probability}], and the detected language in a `.lang` file
beside it. Runs in its own uv environment."""
import json
import sys
from pathlib import Path

import mlx_whisper

MODEL = "mlx-community/whisper-large-v3-turbo"


def main() -> None:
    audio, out = sys.argv[1], sys.argv[2]
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL, word_timestamps=True)
    words = [{"word": w["word"], "start": round(float(w["start"]), 2), "end": round(float(w["end"]), 2),
              "probability": round(float(w["probability"]), 3)}
             for s in result["segments"] for w in s["words"]]
    with open(out, "w") as f:
        json.dump(words, f, ensure_ascii=False)
    Path(out).with_suffix(".lang").write_text(result["language"])


if __name__ == "__main__":
    main()
