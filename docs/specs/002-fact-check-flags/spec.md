# S2 Fact-check flags

**Implements**: [RFC › Specs S2](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts), [ARCHITECTURE › Google Fact Check Tools API](../../ARCHITECTURE.md#external-systems)
**Approval**: person · approved 2026-11-14

## Summary

While a recorded interview plays, the person now also sees when a figure or a fact that someone states is wrong or misleading, with the source that says so and its date. The helper picks out checkable claims, looks first for fact-checks that Maldita, Newtral and others already published, and only then searches the web on official sources, comparing with the data valid on the day the video was published. A claim is shown only when a dated source contradicts it, so the feed stays precise.

## Acceptance

- [X] A1 · A real interview gets inaccuracy flags with dated sources
  - **Story:** The person starts the helper with their Google key and asks it for a 112-minute interview. When the analysis ends, the flag file holds at least one inaccuracy flag; each one quotes the words, says "false" or "misleading", and names at least one source with its publisher, link and date.
  - **Test:** `check: bash tests/acceptance/s2-a1-real-inaccuracy-flags.sh "$S2_VIDEO_URL"`
- [X] A2 · A published fact-check is used first, with its own date
  - **Story:** In an invented dialogue a guest says youth unemployment doubled last year. A published fact-check by Newtral, rated "Falso" on 12 May 2025, matches it. The check step receives that fact-check, and the flag cites Newtral with the date 2025-05-12, even if the web search gives no date.
  - **Test:** `tests/acceptance/test_s2_a2_published_check_first.py`
- [X] A3 · A claim is flagged only when a dated source contradicts it
  - **Story:** In the same dialogue three claims are checked: one the sources confirm, one they contradict but with no date anywhere, and one the INE contradicts in a release dated 2025-10-28. Only the third becomes a flag, citing INE and that date.
  - **Test:** `tests/acceptance/test_s2_a3_flag_needs_dated_source.py`
- [X] A4 · An inaccuracy card shows the source and the date
  - **Story:** On a page that mimics the YouTube player, with an inaccuracy flag at second 30 with confidence 0.9, rated "false", sourced to INE on 2025-10-28, the person plays to second 30 and sees a card with "Dato falso", the words, "INE · 2025-10-28" and "90%".
  - **Edge case:** WHEN the flag has a note that the figure changed after the video was published THEN the card also shows "Dato actualizado:" with the note.
  - **Test:** `tests/acceptance/s2-a4-inaccuracy-card.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/flags.py` | edit — `Claim` and `PublishedCheck` types |
| `src/helper/fact_checker/core/pipeline.py` | edit — the chunk call also returns checkable claims, each with up to 3 search queries |
| `src/helper/fact_checker/core/factcheck.py` | new — check prompt and the rule: a flag needs a dated contradicting source |
| `src/helper/fact_checker/core/scheduler.py` | edit — the budget counts every Claude tool call, not every chunk |
| `src/helper/fact_checker/adapters/factcheck_google.py` | new — `claims:search` with the header key, `languageCode=es`, 5 results per query |
| `src/helper/fact_checker/adapters/llm_claude_cli.py` | edit — optional allowed tools (WebSearch, WebFetch) |
| `src/helper/fact_checker/server.py` | edit — fact-check step after each chunk with claims; key from `FACT_CHECK_API_KEY` |
| `src/extension/src/flags.ts`, `src/extension/src/overlay.ts` | edit — inaccuracy cards with source, date and note |
| `tests/fakes/google-factcheck/claims-search.json` | new — cleaned real response |
| `tests/acceptance/` | new — the four tests and the Fact Check Tools API contract test |

## Tasks

- [X] T001 Add `Claim` and `PublishedCheck` in `src/helper/fact_checker/core/flags.py` → A2, A3
- [X] T002 [P] Search published fact-checks in `src/helper/fact_checker/adapters/factcheck_google.py` → A1, A2
- [X] T003 [P] Pass allowed tools to `claude -p` in `src/helper/fact_checker/adapters/llm_claude_cli.py` → A1
- [X] T004 Extract checkable claims in the chunk call in `src/helper/fact_checker/core/pipeline.py` → A2, A3
- [X] T005 Build the check call and the dated-source rule in `src/helper/fact_checker/core/factcheck.py` → A2, A3
- [X] T006 Count every Claude tool call against the budget in `src/helper/fact_checker/core/scheduler.py` → FR-001
- [X] T007 Run the fact-check step and log it in `src/helper/fact_checker/server.py` → A1, A2, A3
- [X] T008 [P] Show inaccuracy cards in `src/extension/src/overlay.ts` → A4

## Requirements

- [X] FR-001 — The budget of 60 Claude tool calls per video-hour MUST count fact-check calls too; a chunk with no claims makes no fact-check call.
- [X] FR-002 — The fact-check step MUST pass the video's publish date and ask for data valid on that date.

## Decisions

- **Claims are found in the existing chunk call; one more call per chunk checks all its claims** (default) — keeps about 60 calls per hour; a call per claim would break the budget.
- **True and unverifiable claims are not shown** (default) — precision first; the side panel of S11 may show them later.
- **Inaccuracy labels are `false` and `misleading`** (default) — the flag file needs a label; this extends the ARCHITECTURE contract.
- **The helper reads the key from `FACT_CHECK_API_KEY`; the person starts it after loading `.env`** (default) — no config file.

## Out of scope

- Contradictions with the speaker's record and promises: S9. Setting the threshold from measurements: S3.
- Showing confirmed claims: S11. The demo threshold in the overlay is restored to 0.80 before S2 builds.
