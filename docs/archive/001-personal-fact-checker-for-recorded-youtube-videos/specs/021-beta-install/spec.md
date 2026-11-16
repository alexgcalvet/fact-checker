# S21 Install for a beta: setup, doctor and autostart on macOS and Linux

**Implements**: [ARCHITECTURE › Hosting](../../../../ARCHITECTURE.md#hosting), [ARCHITECTURE › External systems](../../../../ARCHITECTURE.md#external-systems)
**Approval**: agent · approved 2026-11-15

## Summary

Today only the author can run the fact-checker: the helper is started by hand, speech to text works only on Apple silicon, and the extension fails in silence when the helper is not there. This slice lets other technical people install it with their own Claude subscription on macOS (Apple silicon and Intel) and Linux: one install command, one setup command that checks the tools and starts the helper at every login, a doctor command that says what is missing, and an extension that says when the helper is down. It also measures what is lost when a tester has no Hugging Face token for speaker separation.

## Acceptance

- [X] A1 · Setup checks the tools and starts the helper at every login
  - **Story:** A tester installs the helper with `uv tool install` and runs `fact-checker setup`. On a Linux machine without yt-dlp, setup prints one line, "yt-dlp: missing", with its fix, "uv tool install yt-dlp", and installs nothing. Once yt-dlp is there, setup installs a systemd user service on Linux, or a launchd agent on macOS, that runs `fact-checker serve` at login. `fact-checker doctor` prints one line per check, such as "helper: not running on port 8765 · fix: fact-checker setup", and "speaker separation: off (optional)" without a Hugging Face token.
  - **Test:** `tests/acceptance/test_s21_a1_setup_and_doctor.py`
- [X] A2 · A video without captions uses the speech engine of the machine
  - **Story:** The helper analyses an invented video with no Spanish captions. On an Apple silicon Mac it transcribes the audio with mlx-whisper; on an Intel Mac or on Linux, with faster-whisper; the flags come from the transcribed words in both cases.
  - **Edge case:** WHEN the machine has no speech engine (no uv) THEN the analysis stops with the reason "no Spanish captions, and no speech engine on this machine: run fact-checker doctor".
  - **Test:** `tests/acceptance/test_s21_a2_speech_engine.py`
- [X] A3 · Without a Hugging Face token, the speakers come from the text, and the loss is measured
  - **Story:** The person runs the comparison check on the 112-minute interview, analysed once with no Hugging Face token in a scratch helper home. It prints, for the run with voices and the run without: the share of flags whose speaker (host or guest) matches the voice heard at that second, and how many of the 4 cards the person marked unfair for a wrong speaker come back. It never prints a quote.
  - **Test:** `check: bash tests/acceptance/s21-a3-no-diarization.sh <scratch helper home>`
- [X] A4 · The extension says when the helper is down
  - **Story:** A tester opens a YouTube video with the helper stopped. Instead of the "Analizar este vídeo" button, the player shows "El ayudante de fact-checker no responde", how to install it and to run `fact-checker doctor`. When the helper comes back, the message goes and the button shows. If the helper stops during an analysis, the message shows again.
  - **Test:** `tests/acceptance/s21-a4-helper-down.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/install.py` | new — the checks of setup and doctor, the launchd and systemd files |
| `src/helper/fact_checker/cli.py` | edit — `setup` and `doctor` commands |
| `src/helper/pyproject.toml` | edit — a build backend, so `uv tool install` ships `thresholds.json` and `summary.html` |
| `src/helper/fact_checker/adapters/faster_whisper_cli.py` | new — faster-whisper, same words as `whisper_cli.py` |
| `src/helper/fact_checker/adapters/whisper.py` | edit — the script to run is a parameter |
| `src/helper/fact_checker/adapters/screenshot.py` | edit — find Chrome or Chromium on macOS and Linux |
| `src/helper/fact_checker/adapters/youtube.py` | edit — the stop reason with no speech engine |
| `src/helper/fact_checker/server.py` | edit — pick the speech engine; `serve` reads `<home>/.env` |
| `src/extension/src/sw.ts`, `content.ts` | edit — the "helper down" answer and message |
| `README.md` | new — the install steps of a tester |
| `docs/ARCHITECTURE.md` | edit — the faster-whisper system, Hosting |
| `tests/acceptance/` | new — the tests and the faster-whisper contract test |

## Tasks

- [X] T001 [P] Add `install.py` (checks, Chrome lookup, launchd plist, systemd unit), `setup` and `doctor` in `cli.py`, the `.env` of the home in `server.py`, a build backend in `pyproject.toml` → A1
- [X] T002 [P] Add `faster_whisper_cli.py`, the script parameter in `whisper.py`, the engine pick in `server.py`, the stop reason in `youtube.py`, Chrome lookup in `screenshot.py` → A2
- [X] T003 Write the comparison check and run it on the run without a token → A3
- [X] T004 [P] Return "helper down" from `sw.ts` on a failed connection and show the message in `content.ts` → A4
- [X] T005 Write `README.md` and update Hosting and External systems in `docs/ARCHITECTURE.md` → A1

## Decisions

- **The helper reads optional keys from `~/.fact-checker/.env`** (default) — an autostarted helper has no shell; rejected: keys in the unit file.
- **The autostart unit carries the PATH of the setup shell** (default) — launchd and systemd start with a bare PATH that lacks `claude` and `yt-dlp`.
- **mlx-whisper stays on Apple silicon** (default) — about 7× real time against 1.7× for faster-whisper on CPU ([research](../../../../research/faster-whisper.md)).
- **No pass bar on the measured loss** (default) — the check reports it; the person decides if speaker separation becomes required.

## Out of scope

- Windows, an API-key mode and a store or zip release of the extension: later slices.
- Showing other stop reasons (such as "no speech engine") in the extension.
