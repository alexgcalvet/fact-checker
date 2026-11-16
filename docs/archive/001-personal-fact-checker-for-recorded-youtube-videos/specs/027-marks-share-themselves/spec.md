# S27 Marks share themselves

**Implements**: [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts), [ARCHITECTURE › External systems](../../../../ARCHITECTURE.md#external-systems)
**Approval**: agent · approved 2026-11-15

## Summary

Today a tester must find a small "send my marks" button at the foot of the side panel, and few marks reach the author. After this slice each mark goes to the author's collector by itself, a moment after the tester gives it, and one line in the panel says so, with a switch in ⚙ to turn it off. Each card also asks "Is this flag fair?" with two large buttons, so a mark is one obvious click.

## Acceptance

- [X] A1 · A mark reaches the collector by itself
  - **Story:** A tester marks an ad hominem card as fair. Within a second the author's collector gets one request with that mark only (video, second, type, label, quote, confidence, verdict, reason, provider, model, helper version, install id), and the card answers at once even when the collector is slow. The tester marks a false-figure card: the next request holds only that mark. Two marks given at the same instant are each sent once.
  - **Edge case:** WHEN the tester changes the verdict of a sent mark THEN it goes out again with the new verdict.
  - **Test:** `tests/acceptance/test_s27_a1_mark_sends_itself.py`
- [X] A2 · With the collector down, the mark waits and goes with the next one
  - **Story:** The collector answers 503, then nothing listens on its port. The tester marks 2 cards: the helper takes each mark as always and reports no error, and no file appears in `~/.fact-checker/`. The collector comes back; the tester marks a third card and one request holds all 3 marks.
  - **Edge case:** WHEN a tester with no connection runs `fact-checker feedback send` THEN the pending marks go to `~/.fact-checker/feedback-<date>.json`, the command prints that path, and they stay pending.
  - **Test:** `tests/acceptance/test_s27_a2_down_collector_waits.py`
- [X] A3 · With sharing off, nothing leaves the laptop
  - **Story:** The foot of the side panel says "Tus marcas se comparten con el autor para mejorar el detector · Desactivar en ⚙" and has no send button. In ⚙ the tester unticks "Compartir mis marcas con el autor". The foot of the panel now says "Tus marcas no se comparten · Activar en ⚙", and `share_marks = false` is in `~/.fact-checker/config.toml` beside the existing lines. The tester marks a card: after a second the collector has nothing. The tester ticks the box again and marks another card: only that new mark goes; the one given while sharing was off never does.
  - **Test:** `tests/acceptance/test_s27_a3_sharing_off.py`, `tests/acceptance/s27-a3-share-toggle.test.ts`
- [X] A4 · Each card asks the question with two large buttons
  - **Story:** A person with a Spanish browser sees a fallacy card: its foot reads "¿Es justo este aviso?" with the buttons "✓ De acuerdo" and "✗ No", taller than the card's other text buttons. In English they read "Is this flag fair?", "✓ Agree", "✗ Disagree". A click on "✓ De acuerdo" marks the flag correct as today, and a marked card says "Marcaste: ✓ De acuerdo" with "cambiar".
  - **Test:** `tests/acceptance/s27-a4-fair-question.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/feedback.py`, `store.py` | edit — a send that writes no file; a mark given with sharing off is kept local and never sent; `share_marks` written into `config.toml` |
| `src/helper/fact_checker/server.py` | edit — a background send after each mark and at helper start, one at a time; `GET`/`POST /share`; the `/feedback` routes go |
| `src/helper/fact_checker/cli.py` | edit — `fact-checker feedback send` |
| `src/extension/src/overlay.ts`, `flags.ts`, `texts.ts` | edit — the question row and the two vote buttons; `ROSE` exported; new texts, the button texts go |
| `src/extension/src/panel.ts`, `sw.ts`, `content.ts` | edit — the sharing line and the ⚙ box; the `share` requests in place of the feedback ones |
| `src/helper/fact_checker/extension/` | edit — the rebuilt extension |
| `src/helper/fact_checker/config.example.toml`, `README.md`, `src/collector/README.md` | edit — `share_marks`; "Share your marks" and "Data" without the button |
| `tests/acceptance/` | new — the five test files |

## Tasks

- [X] T001 Kept-local marks in `store.py`; a send with no file, `unsent` skipping kept-local marks and `set_share` in `feedback.py` → A1, A2, A3
- [X] T002 Background send with a lock after a mark and in `serve`, `GET`/`POST /share`, no `/feedback` routes in `server.py` → A1, A2, A3
- [X] T003 `fact-checker feedback send` in `cli.py` → A2
- [X] T004 [P] Question row and vote buttons in `overlay.ts`, `flags.ts`, `texts.ts` → A4
- [X] T005 Sharing line and ⚙ box in `panel.ts`, `texts.ts`; `share` and `set-share` in `sw.ts`, `content.ts` → A3, A4
- [X] T006 Rebuild the extension; update `config.example.toml`, `README.md`, `src/collector/README.md` → A3

## Decisions

- **Each mark is sent at once by a background thread, one sender at a time; the send reuses the S24 batch and record** (lead) — rejected: the panel button (testers missed it).
- **An automatic send that fails writes no file and shows nothing; the marks go with the next mark or the next helper start** (lead).
- **The ⚙ box writes `share_marks` into `config.toml` through `POST /share`; the panel asks `GET /share`** — one switch for the browser, the helper start and the CLI; rejected: the mark request carries the setting (the helper start could not know it). The line is replaced in place, or put first in the file so it stays above every table.
- **A mark given while sharing is off is stored with `"shared": false` and never sent, also after sharing is on again** (default) — a choice to keep local holds; rejected: send the backlog once sharing is back.
- **`fact-checker feedback send` stays for people offline: it sends now, or writes the S24 dated file and prints its path; it ignores `share_marks`, since running it is the consent** (default).
- **The `/feedback` routes and the S24 panel texts go** — nothing calls them; the S24 button tests retire with them.
- **The panel line is hidden while the helper does not answer** (default) — the helper notice already says so.
- **Vote buttons: glass `.fc-s`, 34 px high, 13.5 px semibold, ✓ in cyan and ✗ in rose; the question row spans the card foot under a hairline** (lead) — rejected: today's 26 px text buttons.

## Out of scope

- A count or a history of the shared marks in the panel.
- Updating `docs/ARCHITECTURE.md` with `/share` and the automatic send: `/rfc sync` after this slice.
