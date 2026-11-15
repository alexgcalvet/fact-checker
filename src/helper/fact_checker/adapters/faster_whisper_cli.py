# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["faster-whisper==1.2.1", "av==16.1.0"]
# ///
"""Timed words of a WAV file as JSON: [{word, start, end, probability}], on the CPU of any macOS or Linux machine.

The same output as whisper_cli.py, with the detected language in a `.lang` file beside it. Runs in its own uv
environment.
"""
import json
import sys
from pathlib import Path

from faster_whisper import WhisperModel

MODEL = "large-v3-turbo"


def main() -> None:
    audio, out = sys.argv[1], sys.argv[2]
    segments, info = WhisperModel(MODEL, device="cpu", compute_type="int8").transcribe(audio, word_timestamps=True)
    words = [{"word": w.word, "start": round(float(w.start), 2), "end": round(float(w.end), 2),
              "probability": round(float(w.probability), 3)}
             for s in segments for w in s.words]
    with open(out, "w") as f:
        json.dump(words, f, ensure_ascii=False)
    Path(out).with_suffix(".lang").write_text(info.language)


if __name__ == "__main__":
    main()
