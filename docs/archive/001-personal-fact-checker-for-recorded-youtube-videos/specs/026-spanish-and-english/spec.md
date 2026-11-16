# S26 Spanish and English

**Implements**: [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts), [ARCHITECTURE › Hosting](../../../../ARCHITECTURE.md#hosting)
**Approval**: agent · approved 2026-11-15

## Summary

Today every text of fact-checker is Spanish and the helper reads only Spanish videos, so a person with an English browser or an English video cannot use it. After this slice the player, the side panel and the shareable summary speak the person's language (Spanish or English, with a switch in the settings), and an English video is read as English. The reasons of each flag come in the person's language, while the quoted words stay as they were said.

## Acceptance

- [X] A1 · The player and the panel speak the browser's language
  - **Story:** A person with an English Chrome opens a video with a false figure and 2 unsent marks. The card says "False claim" with "✓ Agree" and "✗ Disagree", the tab says "Flags (1)" and the panel button "Send my marks (2)"; the "helper does not answer" notice is in English only. With a Spanish Chrome the same screens say "Dato falso", "✓ De acuerdo", "Avisos (1)" and "Enviar mis marcas (2)". In ⚙ the person clicks "ES": the texts turn Spanish at once and the choice is kept with the other settings.
  - **Test:** `tests/acceptance/s26-a1-interface-language.test.ts`
- [X] A2 · An English video is read as English
  - **Story:** The helper analyses an invented English interview whose captions are English, with a machine-translated Spanish track beside them. It reads the English track; every reading is told the conversation is English, the claims get English search queries, the published fact-check search asks for English, and the figure search looks at the sources of the country the conversation is about instead of Spain's (no INE). The flag quotes the English words, such as "unemployment fell by half in one year".
  - **Test:** `tests/acceptance/test_s26_a2_english_video.py`
- [X] A3 · Reasons come in the viewer's language, quotes stay as said
  - **Story:** A person with a Spanish browser clicks "Analizar este vídeo" on that English interview: the extension sends its language, and the part, fact-check and judge readings ask for reasons in Spanish about an English conversation; the flag file says `lang` "es" and the quote stays English. An English viewer of a Spanish video gets readings that ask for English reasons. With no language sent, the reasons follow the video's language.
  - **Test:** `tests/acceptance/test_s26_a3_reasons_in_viewer_language.py`, `tests/acceptance/s26-a3-analyze-sends-language.test.ts`
- [X] A4 · The shareable summary follows the interface language
  - **Story:** A person whose flag file says `lang` "en" exports the card (S35): the image says "claims, false or misleading", "False." and "Detected with AI", and the page says "Alt text, ready to copy" above an alt text that starts "Profile of". A file with `lang` "es", or none, keeps the Spanish texts.
  - **Test:** `tests/acceptance/test_s26_a4_summary_language.py`

## Files

| Path | Change |
|------|--------|
| `src/extension/src/texts.ts` | edit — one table of every visible string, `es` and `en`; the browser language |
| `src/extension/src/flags.ts`, `overlay.ts`, `panel.ts`, `content.ts`, `sw.ts` | edit — read texts from the table (label names per language stay in `flags.ts`, which a node-run S16 test imports alone); ⚙ ES/EN; `lang` on the analyze request |
| `src/extension/manifest.json`, `src/extension/_locales/{es,en}/messages.json`, `src/extension/build.mjs` | edit, new — the manifest description per locale, copied into the build |
| `src/extension/vitest.config.ts`, `tests/extension/setup-es.ts`, `tests/extension/look.test.ts` | edit, new — earlier tests run with a Spanish browser; labels of both languages |
| `src/helper/fact_checker/extension/` | edit — the rebuilt extension |
| `src/helper/fact_checker/core/languages.py` | new — per language: name, sources of the figure search, tiers, examples |
| `src/helper/fact_checker/core/flags.py` | edit — `Transcript.language`; `Prompt.language`; the system prompt per language |
| `src/helper/fact_checker/core/{pipeline,factcheck,judge,speakers}.py` | edit — prompts for the spoken language, reasons in the reader language |
| `src/helper/fact_checker/adapters/{youtube,whisper,whisper_cli,faster_whisper_cli}.py` | edit — pick the original captions of either language; whisper detects it |
| `src/helper/fact_checker/adapters/llm_{claude_cli,codex_cli,anthropic_api,openai_api,chat_api}.py` | edit — the system prompt from the prompt's language |
| `src/helper/fact_checker/server.py` | edit — `lang` on `POST /videos/<id>`, into the flag file; search language; share page per language |
| `src/helper/fact_checker/core/summary.py`, `src/helper/fact_checker/summary.html` | edit — summary texts per `lang` |
| `README.md`, `INSTALL-AGENT.md`, `docs/ARCHITECTURE.md` | edit — "Spanish or English" lines; `lang`, `spoken` and the request field |
| `tests/acceptance/` | new — the five test files |

## Tasks

- [X] T001 Move every visible string to `texts.ts`, pick the language, add the ⚙ ES/EN line, the locales and the Spanish test setup → A1
- [X] T002 Send `lang` with the analyze request in `content.ts` and `sw.ts` → A3
- [X] T003 Add `languages.py`, `Transcript.language`, `Prompt.language` and the per-language system prompt in the adapters → A2
- [X] T004 Pick the original caption track and the whisper language in `youtube.py` and `whisper*.py` → A2
- [X] T005 Write the prompts of `pipeline.py`, `factcheck.py`, `judge.py`, `speakers.py` for the spoken and reader language; search language in `server.py` → A2, A3
- [X] T006 Take `lang` in `server.py` into the flag file and the readings → A3
- [X] T007 Write the summary and share page texts per `lang` in `summary.py`, `summary.html`, `server.py` → A4
- [X] T008 Rebuild the extension; update `README.md`, `INSTALL-AGENT.md`, `docs/ARCHITECTURE.md` → A1, FR-001

## Requirements

- [X] FR-001 — The precision rules of every prompt (materiality, direction, "nitpick", roles, "most parts have no fallacy") MUST say the same in both languages; only the language names, the example phrases and the source lists change.

## Decisions

- **Browser language from `navigator.language`: `es*` is Spanish, anything else English** — in Chrome it follows the browser's language and it works in tests; beat: `chrome.i18n.getUILanguage()` (absent in every test stub).
- **Caption order `es-orig`, `en-orig`, `es`, `en`** (default) — an `-orig` track is the video's own speech, so a translated track never wins; beat: yt-dlp's `language` field (empty on many videos).
- **Whisper detects the language; English if it says `en`, else Spanish** (default) — the cache keeps it in a `.lang` file beside the words; an old cache without it reads Spanish.
- **The flag file keeps `lang` (texts) and `spoken` (the video)** (default) — the first viewer's language stays for the video; a second viewer in another language reads the same reasons.
- **Earlier tests run with a Spanish browser through a vitest setup file** — no approved test is edited.
- **The display names of labels live in the extension; the label ids stay** — the helper and the golden set are unchanged.

## Out of scope

- Languages beyond Spanish and English, Windows: later slices.
- Measuring precision on real English videos: the lead does it after this slice.
- New thresholds or golden dialogues in English: after that measure.
