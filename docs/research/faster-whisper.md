# Speech to text on any macOS or Linux machine: faster-whisper (S21)

**Sources**
- https://github.com/SYSTRAN/faster-whisper (README, read 2026-11-15)
- https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/utils.py (model names, read 2026-11-15)
- https://pypi.org/project/faster-whisper/ (1.2.1, 2025-10-31) and https://pypi.org/project/ctranslate2/ (4.9.0, 2026-11-10), read 2026-11-15
- Two runs by hand on 2026-11-15 on an Apple M3 (CPU), on the first 60 s of the audio of one public Spanish interview. No transcript text is kept.

## Summary

| Item | Finding |
|---|---|
| Status | confirmed |
| Fit | The same timed words as mlx-whisper, on the CPU of macOS (arm64, x86_64) and Linux (x86_64, aarch64) |
| Cost | Free, local; one model download of about 1.6 GB on the first run |
| Gotcha | faster-whisper 1.2.1 breaks with PyAV 19 (`open() got an unexpected keyword argument 'metadata_errors'`): pin `av==16.1.0` |

## Contract

| Item | Finding |
|---|---|
| What we call | `WhisperModel("large-v3-turbo", device="cpu", compute_type="int8").transcribe(wav, language="es", word_timestamps=True)` → `(segments, info)`; `segments` is a generator, so the work runs while it is read |
| Shape | each segment has `start`, `end`, `text`, `words`; each word has `word`, `start`, `end`, `probability` (floats in seconds). Words carry a leading space, as in mlx-whisper |
| Model | `large-v3-turbo` (alias `turbo`) → Hugging Face repo `mobiuslabsgmbh/faster-whisper-large-v3-turbo`; public, no token |
| Library | `faster-whisper==1.2.1` (Python ≥ 3.9) on CTranslate2; wheels for macOS arm64 and x86_64 (11.0+), Linux x86_64 and aarch64 (glibc ≥ 2.27), CPython 3.9–3.15 |
| Audio | decoded by PyAV, which bundles FFmpeg; a 16 kHz mono WAV works |
| Auth | none |
| GPU | NVIDIA only (CUDA 12, cuDNN 9); not used here. CTranslate2 prints a tip about an experimental MPS backend on Apple silicon |
| Speed | 60 s of audio in 36 s on an M3 CPU with int8, model load included. About 1.7× faster than real time: a 1-hour video takes about 35 minutes |
| Errors and limits | None observed beyond the PyAV pin |
| Environments | the person's machine; no sandbox |

## Use in the helper

- `adapters/faster_whisper_cli.py` runs through `uv run --script`, as `whisper_cli.py` does, and writes the same JSON: `[{word, start, end, probability}]`.
- mlx-whisper stays the engine on Apple silicon: it is about 7× real time there, against about 1.7× for faster-whisper on CPU.
