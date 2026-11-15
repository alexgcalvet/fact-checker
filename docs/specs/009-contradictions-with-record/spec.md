# S9 Contradictions with the record and promises

**Implements**: [RFC › Specs S9](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-14

## Summary

Politicians often talk about what they said or promised before, and the viewer cannot check it live. This slice searches published fact-checks and the web when a speaker talks about their own earlier words or promises. If the record contradicts them, the card quotes the earlier public statement with its date and a link. For a promise, the card shows when it was made, its figure, its deadline and its status today.

## Acceptance

- [X] A1 · A claim about one's own earlier words that the record contradicts is flagged with the earlier statement
  - **Story:** In an invented interview, the guest says "yo nunca dije que no pactaría con ese partido". The check finds a dated interview in a newspaper where the guest said "no pactaré con ese partido". The flag file has a contradiction flag with the label "record", quoting the guest, with the earlier statement, its date and its link.
  - **Edge case:** WHEN the earlier statement has no date that a source confirms THEN no flag is made.
  - **Test:** `tests/acceptance/test_s9_a1_record_contradiction.py`
- [X] A2 · A promise shows when it was made, its figure, its deadline and its status
  - **Story:** In an invented interview, the guest says "hemos cumplido lo que prometimos en vivienda". The check finds the promise of 184,000 homes made in April 2023 for 2026, and that far fewer are delivered. The flag file has a contradiction flag with the label "promise" that holds the date of the promise, the figure, the deadline, the status "not met" and a dated source.
  - **Test:** `tests/acceptance/test_s9_a2_promise_status.py`
- [X] A3 · The card shows the earlier statement or the promise
  - **Story:** On a page that mimics the YouTube player, a record flag shows the earlier statement with its date and its source as a link; a promise flag shows "Prometido en abril de 2023: 184.000 viviendas para 2026 · Estado: no cumplida".
  - **Test:** `tests/acceptance/s9-a3-record-card.test.ts`
- [X] A4 · A real promise shows its status on a 112-minute interview
  - **Story:** The helper analyses the part of a 112-minute interview from 1:29:00 to 1:32:00, where homes delivered come up. The flag file has a promise flag about homes with the date of the promise, its figure and its status, and a dated source.
  - **Test:** `check: bash tests/acceptance/s9-a4-real-promise.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/flags.py` | edit — `Claim.kind` (`fact`, `own_words`, `promise`); `Flag.promise` |
| `src/helper/fact_checker/core/pipeline.py` | edit — the part pass marks claims about the speaker's own earlier words or promises |
| `src/helper/fact_checker/core/factcheck.py` | edit — those claims are checked against the speaker's record; record and promise flags need a dated source |
| `src/extension/src/flags.ts`, `src/extension/src/overlay.ts` | edit — the record and promise lines on the card |
| `docs/ARCHITECTURE.md` | edit — the `promise` field and the `record` and `promise` labels |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Mark claims about own words and promises in `src/helper/fact_checker/core/pipeline.py` and `core/flags.py` → A1, A2
- [X] T002 Check them against the record and make record and promise flags with dated sources in `src/helper/fact_checker/core/factcheck.py`; update `docs/ARCHITECTURE.md` → A1, A2, A4
- [X] T003 [P] Show the earlier statement and the promise on the card in `src/extension/src/overlay.ts` and `flags.ts` → A3

## Decisions

- **The record is checked in the same check tool call as the other claims of the part** (default) — no extra Claude tool calls; the check step already has web search.
- **A record or promise flag needs a source with a date, like an inaccuracy** (default) — an undated earlier statement cannot be shown as the record.
- **Promise status is one of `met`, `partly met`, `not met`, `in progress`; only `partly met` and `not met` make flags when the speaker says it was met** (default) — a kept promise is not a flag.

## Out of scope

- A database of each politician's promises kept between videos: Phase 2.
