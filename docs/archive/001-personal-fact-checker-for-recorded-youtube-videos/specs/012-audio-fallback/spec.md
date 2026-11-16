# S12 Audio fallback

**Implements**: [RFC › Specs S12](../../RFC.md#specs), [ARCHITECTURE › External systems › Whisper](../../../../ARCHITECTURE.md#external-systems)
**Approval**: agent · approved 2026-11-14

## Summary

Some videos have no Spanish captions, so the tool shows nothing on them. This slice transcribes the audio on the laptop with Whisper when a video has no usable Spanish captions, word by word with times, and the analysis then runs as on any other video. The audio and the transcript stay on the laptop.

## Acceptance

- [X] A1 · A video with no Spanish captions is analysed from its audio
  - **Story:** The helper analyses an invented video whose captions exist only in English. It transcribes the audio instead and the flag file gets a fallacy flag at the second where the transcript puts the words, with the publish date of the video.
  - **Edge case:** WHEN the video has Spanish captions THEN the audio is not transcribed.
  - **Test:** `tests/acceptance/test_s12_a1_audio_when_no_captions.py`
- [X] A2 · Whisper turns real audio into timed words
  - **Story:** The person runs the check on the 14-minute interview used in S1, through the audio path. It prints the number of words, at least 2,000, with times that only go up and end before the video ends.
  - **Test:** `check: bash tests/acceptance/s12-a2-whisper-real.sh "$S1_VIDEO_URL"`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/adapters/whisper.py` | new — run Whisper in its own uv environment; words with times; cache the transcript in the helper home |
| `src/helper/fact_checker/adapters/whisper_cli.py` | new — the script that the uv environment runs: audio in, JSON words out |
| `src/helper/fact_checker/adapters/youtube.py` | edit — with no Spanish captions, transcribe the audio; keep the publish date |
| `src/helper/fact_checker/server.py` | edit — give the YouTube adapter the Whisper fallback |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Transcribe audio into timed words, cached, in `src/helper/fact_checker/adapters/whisper.py` and `whisper_cli.py` → A2
- [X] T002 Fall back to the audio when no Spanish captions exist in `src/helper/fact_checker/adapters/youtube.py` and wire it in `server.py` → A1

## Requirements

- [X] FR-001 — The audio and the transcript MUST stay in the helper home; they never enter the repo.

## Decisions

- **mlx-whisper with `whisper-large-v3-turbo`, through `uv run`, as with pyannote** (default) — the helper stays standard-library only; 7× real time on the person's M3. Rejected: faster-whisper on CPU, slower on this laptop.
- **One transcript of the whole audio before the analysis** (default) — about 16 minutes on a 2-hour video; the voices need the audio anyway. Rejected: transcribing part by part.
- **Words with a probability under 0.2 are kept** (default) — the part pass reads them in context; dropping words breaks quotes.

## Out of scope

- Live streams: Step 3.
- Other languages than Spanish.
