# S4 Feedback on cards

**Implements**: [RFC › Specs S4](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: person · approved 2026-11-14

## Summary

The player shows many flags on purpose for now, so that the person can find the false positives on real videos. This slice puts a "correct" and an "unfair" button on each card, with an optional reason, keeps those marks on the laptop, and adds a table to the eval with the real precision per type and per name, measured on the person's own marks. The bars can then come from real videos instead of the easy invented dialogues.

## Acceptance

- [X] A1 · Marking a card keeps the mark on the laptop
  - **Story:** On a page that mimics the YouTube player, the person clicks "✗ Injusto" on an ad hominem card, types "es una pregunta, no un ataque" and saves. The helper's marks log gets one line with the video, the flag, its words, its name, "unfair" and that reason.
  - **Edge case:** WHEN the person marks the same card again with "✓ Correcto" THEN the log gets a second line, and the latest mark is the one that counts.
  - **Test:** `check: bash tests/acceptance/s4-a1-mark-a-card.sh`
- [X] A2 · A card under the mouse stays until the person is done
  - **Story:** On the mimic player, a card shows at second 42. The person moves the mouse over it at second 49 and starts typing a reason; at second 55 the card is still there. When the mouse leaves, the card goes.
  - **Test:** `tests/acceptance/s4-a2-card-stays-under-mouse.test.ts`
- [X] A3 · The eval prints the real precision from the marks
  - **Story:** The marks log holds 3 evasion marks (1 correct, 2 unfair) and 4 inaccuracy marks (3 correct, 1 unfair). The person runs the eval of marks and reads: fallacy 33% (1 of 3), with evasion 33% (1 of 3) under it; inaccuracy 75% (3 of 4).
  - **Test:** `tests/acceptance/test_s4_a3_real_precision.py`
- [X] A4 · The person marks a real interview and reads the real precision
  - **Story:** The person reloads the extension, opens a 112-minute interview, marks at least 10 cards, and runs the eval of marks; the table lists those marks by type and name.
  - **Test:** `review: the person's marks and the printed table`

## Files

| Path | Change |
|------|--------|
| `src/extension/src/overlay.ts` | edit — "✓ Correcto" and "✗ Injusto" buttons, a reason field after "✗", a card under the mouse stays |
| `src/extension/src/content.ts` | edit — send each mark to the service worker |
| `src/extension/src/sw.ts` | edit — `POST /videos/<id>/marks` to the helper |
| `src/helper/fact_checker/server.py` | edit — accept a mark for a flag of a known video; reject other flags |
| `src/helper/fact_checker/store.py` | edit — append the mark to `marks.jsonl` with the flag's words, name, type and confidence |
| `src/helper/fact_checker/cli.py` | edit — `eval --marks` prints the real precision per type and name; plain `eval` prints it after the golden table |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Accept and store marks in `src/helper/fact_checker/server.py` and `src/helper/fact_checker/store.py` → A1
- [X] T002 [P] Add the buttons, the reason field and the mouse hold in `src/extension/src/overlay.ts` → A1, A2
- [X] T003 Send marks through `src/extension/src/content.ts` and `src/extension/src/sw.ts` → A1
- [X] T004 Print the real precision per type and name in `src/helper/fact_checker/cli.py` → A3
- [X] T005 Reload the extension and helper for the person's review → A4

## Requirements

- [X] FR-001 — Marks MUST stay in the helper home on the laptop; they quote real people and never enter the repo.

## Decisions

- **"✓" saves at once; "✗" opens an optional reason field with a save button** (default) — one click for the common case.
- **A log of every mark, the latest per flag counts** (default) — no mark is lost; a change of mind is cheap.
- **`eval --marks` skips the golden run** (default) — reading the marks takes a second; the golden run takes minutes.
- **The real precision table shows the bar the marks would give, with the same rule as the golden one** (default) — the person sees when real marks start to disagree.

## Out of scope

- Setting the saved bars from the marks: the person decides once there are enough marks.
- Showing past marks on cards when a video is watched again.
