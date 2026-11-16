# S40 The helper checks itself

**Implements**: [ARCHITECTURE · Hosting (Install)](../../../../ARCHITECTURE.md#hosting), [Contracts · Helper API](../../../../ARCHITECTURE.md#contracts), [Security](../../../../ARCHITECTURE.md#security)
**Approval**: agent · approved 2026-11-15

## Summary

The check looks at the agent's terminal, but the helper runs at login with its own search path, so the check can say all is fine while the helper cannot find its reader, yt-dlp or ffmpeg. After this slice, the helper reports what it finds itself, setup refuses a Claude that would vanish on the next app update, and a person who reads with an API key pastes it in a page of the helper opened from the extension, never in a chat or a Terminal.

## Acceptance

- [X] A1 · The check shows what the helper finds
  - **Story:** The login helper runs with a search path that holds no yt-dlp, while the agent's terminal finds it. The agent runs `fact-checker doctor`. The yt-dlp line says "the helper does not find yt-dlp" with the fix `fact-checker setup`, and is not ok. The same holds for ffmpeg, uv and the command of the provider in use.
  - **Test:** `test_s40_a1_doctor_from_helper.py`
- [X] A2 · Setup refuses a Claude that moves on update
  - **Story:** The only `claude` on the agent's search path lives under the Claude app's versioned folder, such as `…/Claude/claude-code/2.1.299/…`. The agent runs `fact-checker setup --provider claude`. Setup stops with "claude: inside the Claude app, it moves on each update · fix: curl -fsSL https://claude.ai/install.sh | bash" and starts no helper.
  - **Test:** `test_s40_a2_versioned_claude.py`
- [X] A3 · A key saved from the extension
  - **Story:** The provider is `anthropic` and no key is set. On YouTube, the person opens ⚙ and clicks "Claves". A helper page lists `ANTHROPIC_API_KEY` as "falta". The person pastes the key in a hidden field and saves. The page says "guardada", never shows the value, the key file is readable only by the person, and the next analysis reads with that key with no restart.
  - **Test:** `test_s40_a3_key_page.py`, `s40-a3-settings-opens-keys.test.ts`
- [X] A4 · The key page refuses other sites
  - **Story:** A web page on another site posts a key to the helper's key page, or reaches it through a host name other than 127.0.0.1. The helper answers 403 and the key file does not change.
  - **Test:** `test_s40_a4_key_page_origin.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/server.py` | edit — `/health` adds `tools` (provider command, yt-dlp, ffmpeg, uv: found or not, from the helper's own PATH); `GET /keys` page and `POST /keys` |
| `src/helper/fact_checker/install.py` | edit — doctor takes tool lines from `/health` when the helper answers; setup refuses a versioned Claude app CLI; one writer of `.env` shared with `key set` |
| `src/extension/src/overlay.ts`, `src/extension/src/texts.ts` | edit — "Claves" in ⚙ opens the helper's key page |
| `src/extension/src/sw.ts` | edit — open the key page on the found port |
| `src/helper/fact_checker/extension/` | edit — rebuilt extension |
| `INSTALL-AGENT.md` | edit — the key message points to ⚙ → Claves, not the Terminal |
| `docs/ARCHITECTURE.md`, `docs/RFC.md` | edit — `/health` tools, `/keys`, S40 row |

## Tasks

- [X] T001 `/health` tools from the helper's PATH in `server.py`; doctor uses them in `install.py` → A1
- [X] T002 Setup refuses a Claude under the Claude app's versioned folder in `install.py` → A2
- [X] T003 `GET /keys` and `POST /keys` with the Host and Origin checks in `server.py`, one `.env` writer with `key set` → A3, A4
- [X] T004 "Claves" in ⚙ opens the key page in `overlay.ts`, `texts.ts`, `sw.ts`; rebuild the shipped extension → A3
- [X] T005 [P] Key message in `INSTALL-AGENT.md` → FR-001
- [X] T006 [P] `/health` tools, `/keys` and S40 row in `docs/ARCHITECTURE.md`, `docs/RFC.md` → A1

## Requirements

- [X] FR-001 — `INSTALL-AGENT.md` MUST tell the person to paste a key in ⚙ → Claves, and MUST still never ask for a key in the chat.
- [X] FR-002 — The key page MUST never send a key value back, in a page, an answer or a log; it lists only names and "falta" or "guardada".

## Decisions

- **A form on the helper, guarded by Host and Origin** — the key never crosses the chat or the extension's storage; beat a field in ⚙ that would pass the key through the YouTube page.
- **A POST is kept only with Origin `http://127.0.0.1:<port>`** (default) — the form posts to itself; any other Origin, `null` or none is refused.
- **Refuse the versioned Claude, do not copy it** — copying a signed app binary breaks on updates too; the standalone installer keeps `~/.local/bin/claude` stable.

## Out of scope

- Keys for the collector owner (`feedback pull`): they stay in the Terminal.
- Windows.
