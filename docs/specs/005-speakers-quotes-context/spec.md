# S5 Speakers, quotes and context

**Implements**: [RFC › Specs S5](../../RFC.md#specs), [ARCHITECTURE › External systems › pyannote](../../ARCHITECTURE.md#external-systems), [ARCHITECTURE › Decisions](../../ARCHITECTURE.md#decisions)
**Approval**: agent · approved 2026-11-14

## Summary

On a real interview, most unfair cards came from the tool not knowing who was speaking: it pinned the host's words on the guest, took a rhetorical question for a dodge, and read a described hoax as a claim. This slice separates the voices from the audio, names them from the interview, and lets a stronger model read each part with who says what and ten minutes of context. A card now names the person whose voice said the words, and a published fact-check only counts when it is about the same event.

## Acceptance

- [X] A1 · The voices of a real video are separated and named
  - **Story:** The person asks the helper for the 14-minute interview used in S1. When it ends, the flag file names two voices, the host and the guest, by name or role, and every card names one of them.
  - **Test:** `check: bash tests/acceptance/s5-a1-voices-named.sh "$S1_VIDEO_URL"`
- [X] A2 · A card names the voice that said its words
  - **Story:** In an invented interview the host says "la oposición no tiene autoridad para hablar". The model calls it an ad hominem by the guest. The card says the host said it, because the audio puts those words in the host's voice.
  - **Edge case:** WHEN the quoted words cross from one voice to the other THEN no card is made.
  - **Test:** `tests/acceptance/test_s5_a2_speaker_from_voice.py`
- [X] A3 · A published fact-check about another event does not count
  - **Story:** A guest says 80,000 people crossed into Ceuta in two days. A published fact-check about a different crossing says "hundreds" and is rated false. The check step says it is another event, so it gives no source and no date, and no card is made from it.
  - **Test:** `tests/acceptance/test_s5_a3_other_event_ignored.py`
- [ ] A4 · The unfair cards of the person's marks are gone on a new analysis
  - **Story:** The person's marks on a 112-minute interview hold 6 cards marked unfair (wrong speaker, a described hoax, another event) and 5 marked correct. After a new analysis of that interview, none of the 6 comes back, and at least 4 of the 5 do.
  - **Test:** `check: bash tests/acceptance/s5-a4-marks-regression.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/adapters/diarization.py` | new — run pyannote in its own uv environment, return voice turns |
| `src/helper/fact_checker/adapters/diarize_cli.py` | new — the script that the uv environment runs: audio in, JSON turns out |
| `src/helper/fact_checker/adapters/youtube.py` | edit — also fetch the audio as 16 kHz mono WAV |
| `src/helper/fact_checker/core/flags.py` | edit — `Segment.speaker`, `Transcript.speakers` (voice → name) |
| `src/helper/fact_checker/core/speakers.py` | new — give each word its voice; name the voices with one model call |
| `src/helper/fact_checker/core/pipeline.py` | edit — parts with speaker turns and 10 minutes of context; the card's speaker comes from the voice of its words; quotes and self-questions are not claims |
| `src/helper/fact_checker/core/factcheck.py` | edit — the model says which published checks are about the same event; others give no source |
| `src/helper/fact_checker/core/scheduler.py`, `server.py` | edit — separate voices before the analysis; Opus for the parts and the checks |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Fetch the audio and separate the voices in `src/helper/fact_checker/adapters/diarization.py` and `diarize_cli.py` → A1
- [X] T002 Give each word its voice and name the voices in `src/helper/fact_checker/core/speakers.py` → A1, A2
- [X] T003 Take the card's speaker from its words' voice and reject words across voices in `src/helper/fact_checker/core/pipeline.py` → A2
- [X] T004 Ask for the same event and drop other-event checks in `src/helper/fact_checker/core/factcheck.py` → A3
- [X] T005 Wire voices, longer context and Opus in `src/helper/fact_checker/server.py` and `core/scheduler.py` → A1, A4
- [ ] T006 Re-analyse the 112-minute interview and compare with the person's marks → A4

## Requirements

- [X] FR-001 — The audio, the voice turns and the captions MUST stay in the helper home; they never enter the repo.
- [X] FR-002 — Separating the voices MUST not use the Claude budget; the 60 calls per started video-hour stay as they are.

## Decisions

- **pyannote runs in its own environment through `uv run`, called as a subprocess** (default) — the helper stays standard-library only; torch is large.
- **The voices are separated for the whole video before the analysis** (default) — names need the whole interview; on a 2-hour video the first cards come about 11 minutes later. Rejected: analysing without voices first.
- **Ten minutes of context before each part, with speaker labels** (default) — enough to see who asked what; more makes each call slower.
- **Opus for the parts and the checks** (default) — the person asked for a smarter model; Sonnet stays if the marks do not improve.
- **The question, metric and tense of each claim move to S6** (default) — S6 is the first slice that uses them; this keeps S5 at 4 items.

## Out of scope

- Cards for disputed figures, definition swaps and plans told as facts: S6.
- Starting the analysis before the voices are separated, for live streams: Step 3.
