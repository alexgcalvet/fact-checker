# S25 One-step install

**Implements**: [ARCHITECTURE › Hosting](../../ARCHITECTURE.md#hosting), [ARCHITECTURE › Security](../../ARCHITECTURE.md#security)
**Approval**: agent · approved 2026-11-15

## Summary

Today an install takes seven steps, Node.js and Homebrew, so only technical people can use fact-checker. After this slice a person who barely knows a terminal pastes one sentence into their Claude or ChatGPT, in Spanish or English, and the agent installs everything with one script; the person only logs in once in the browser and clicks three times in Chrome. The helper picks the subscription that is already logged in, keys are typed only in a hidden prompt, and the extension's "helper does not answer" notice gives the same sentence.

## Acceptance

- [X] A1 · One script installs everything, and a second run changes nothing
  - **Story:** On a fresh macOS or Linux account with Claude Code logged in and no uv, yt-dlp, ffmpeg or helper, a person runs `./install.sh` from the repo. It installs uv with the official installer, yt-dlp, an ffmpeg from a Python wheel (no Homebrew), and the helper, runs `fact-checker setup`, and ends with the ready extension folder, such as `~/.fact-checker/extension`, which holds a built extension with no Node.js. A second run prints "already there" for uv, yt-dlp, ffmpeg and the helper, downloads and installs nothing, and leaves every file the same.
  - **Test:** `tests/acceptance/test_s25_a1_installer.py`
- [X] A2 · Setup picks the logged-in subscription and keeps an existing settings file
  - **Story:** A person with no `~/.fact-checker/config.toml` runs `fact-checker setup`. With Claude Code logged in, the new settings file says `provider = "claude"`; with only Codex logged in, `provider = "codex"`; with neither, setup prints one line, "provider: no agent CLI logged in", with the fix, writes no settings file and starts nothing. A settings file that says `provider = "codex"` stays byte for byte, also when Claude Code is logged in.
  - **Test:** `tests/acceptance/test_s25_a2_provider_detection.py`
- [X] A3 · A key goes in through a hidden prompt, and doctor answers in JSON
  - **Story:** A person with `provider = "anthropic"` runs `fact-checker doctor --json`: an agent reads `"ok": false` and the check `ANTHROPIC_API_KEY` with state "missing" and its fix, the same as in the text output. The person runs `fact-checker key set ANTHROPIC_API_KEY` in a terminal and types an invented key: the screen never shows it, and `~/.fact-checker/.env` gets one `ANTHROPIC_API_KEY=` line with it, readable only by the person. A second `key set` replaces that line. `doctor --json` then says "set", and its output never holds the key.
  - **Test:** `tests/acceptance/test_s25_a3_key_and_doctor_json.py`
- [X] A4 · One sentence leads any agent through the install, in Spanish and English
  - **Story:** The README starts with the sentence to paste into Claude or ChatGPT, in Spanish and English; the extension's "helper does not answer" notice shows the same sentence in both languages. The agent guide names only commands that exist, and each message it tells the person has a Spanish and an English text. The person reads the guide and the README quick start in both languages.
  - **Test:** `tests/acceptance/test_s25_a4_agent_guide.py`, then `review: INSTALL-AGENT.md and the README quick start, in Spanish and English`

## Files

| Path | Change |
|------|--------|
| `install.sh` | new — uv, yt-dlp, ffmpeg, helper, setup; each step skips what is there |
| `src/extension/build.mjs`, `src/extension/package.json` | new, edit — `npm run build` writes the loadable extension into the helper package |
| `src/helper/fact_checker/extension/` | new — the built extension, committed |
| `.gitignore` | edit — keep the `dist/` of the built extension |
| `src/helper/fact_checker/install.py` | edit — provider detection, extension copy, `set_key`, doctor JSON |
| `src/helper/fact_checker/cli.py` | edit — `key set <NAME>`, `doctor --json` |
| `tests/helper/test_settings_files.py` | edit — the provider argument of the settings files |
| `tests/extension/bundle.test.ts` | new — the committed extension equals a fresh build |
| `src/extension/src/texts.ts`, `src/extension/src/content.ts` | new, edit — the notice texts per language |
| `INSTALL-AGENT.md`, `README.md` | new, edit — the agent guide; the sentence and the quick start in Spanish and English |
| `docs/ARCHITECTURE.md` | edit — Hosting: install and extension rows |
| `docs/research/one-step-install.md` | new — sources of the choices |
| `tests/acceptance/` | new — the four tests |

## Tasks

- [X] T001 [P] Add `build.mjs`, the build script, the built extension, the `.gitignore` line and `bundle.test.ts` → A1, FR-001
- [X] T002 Detect the provider, copy the extension in `setup`, update `test_settings_files.py` in `install.py` → A1, A2
- [X] T003 Write `install.sh` → A1
- [X] T004 Add `key set` and `doctor --json` in `install.py` and `cli.py` → A3
- [X] T005 [P] Move the notice texts to `texts.ts` with the sentence, in `content.ts` → A4
- [X] T006 Write `INSTALL-AGENT.md`, the README quick start and the Hosting rows of `docs/ARCHITECTURE.md` → A4

## Requirements

- [X] FR-001 — The extension in the helper package MUST equal a fresh `npm run build` of `src/extension`; `tests/extension/bundle.test.ts` fails otherwise.
- [X] FR-002 — `install.sh` MUST run with `sh` and never call `sudo`.

## Decisions

- **The built extension ships inside the helper package and `setup` copies it to `~/.fact-checker/extension`** — a person needs no Node.js and gets one short folder path; beat: a committed `src/extension/dist` (still needs a path into the repo), a release zip (the repo is not published yet).
- **ffmpeg from the imageio-ffmpeg wheel, copied next to the uv tools** ([research](../../research/one-step-install.md)) — a static binary for macOS and Linux, no Homebrew, no sudo; beat: Homebrew or apt, `static-ffmpeg` (downloads binaries at run time).
- **Without a clone, the installer installs the helper from the GitHub archive of `main`** (default) — needs no git; the repo address is one variable, `FACT_CHECKER_REPO`; beat: `git+https` (needs git, which macOS lacks by default).
- **Each step of the installer runs only if its command is missing** (default) — this makes it idempotent; an update stays `uv tool install --reinstall` plus `setup`, as the README says.
- **The installer installs no agent CLI** (default) — the agent that runs it is that CLI; the guide gives the official installers of Claude Code and Codex for the other case.
- **Setup writes no settings file while no agent CLI is logged in** (default) — a later run can still detect one; an API provider is set by hand.
- **The notice shows Spanish, then English** (default) — until S26 adds the language switch.

## Out of scope

- Windows, a Chrome Web Store listing, a release zip of the extension: later slices.
- Translating the extension UI: S26.
