# S13 Analysis progress and past marks

**Implements**: [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-14

## Summary

While the helper analyses a video, the person cannot tell whether more cards may still come for the part they are watching. When they watch a video again, they are asked again to mark cards they already marked. This slice makes the flag file say how far the analysis has reached, shows that reach on the strip under the video, and shows the person's own mark on each card they already marked.

## Acceptance

- [X] A1 · The flag file says how far the analysis has reached
  - **Story:** The helper analyses an invented 10-minute video from the start. The part from 2:00 to 4:00 finishes before the part from 0:30 to 2:00. While that happens the flag file says "analysed until 0:30"; once both are done it says "analysed until 4:00".
  - **Test:** `tests/acceptance/test_s13_a1_analysed_until.py`
- [X] A2 · The strip shows the analysed part
  - **Story:** On a page that mimics the YouTube player, a 100-second video has a flag file analysed until second 40 and still running. The strip under the video shows the first 40 % as analysed and the rest as pending; when the file says done, the whole strip is analysed.
  - **Test:** `tests/acceptance/s13-a2-analysed-strip.test.ts`
- [X] A3 · The helper returns the person's latest mark on each flag
  - **Story:** The person marked a card unfair and then correct. When the extension asks for the flag file, that flag comes with the mark "correct", and flags with no mark come without one.
  - **Test:** `tests/acceptance/test_s13_a3_marks_in_flag_file.py`
- [X] A4 · A card already marked shows the mark instead of the buttons
  - **Story:** On the mimic player, a card marked "unfair" shows at its second. It reads "Marcaste: ✗ Injusto" with a "cambiar" link instead of the two buttons; the link brings the buttons back.
  - **Test:** `tests/acceptance/s13-a4-past-mark.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/server.py` | edit — keep `analysed_until` as parts finish; add the latest mark to each flag on `GET` |
| `src/helper/fact_checker/store.py` | edit — read the latest mark per flag of a video |
| `src/extension/src/flags.ts`, `panel.ts`, `overlay.ts` | edit — the analysed part on the strip; the past mark on the card |
| `docs/ARCHITECTURE.md` | edit — `analysed_until` and `mark` in the flag file contract |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Keep `analysed_until`, the end of the parts done without a gap from the start second, in `src/helper/fact_checker/server.py` → A1
- [X] T002 [P] Show the analysed part on the strip in `src/extension/src/panel.ts` and `flags.ts` → A2
- [X] T003 Add the latest mark to each flag on `GET` in `src/helper/fact_checker/server.py` and `store.py`; update `docs/ARCHITECTURE.md` → A3
- [X] T004 Show a past mark with a link to change it in `src/extension/src/overlay.ts` → A4

## Decisions

- **`analysed_until` counts only parts done without a gap from the start second** (default) — a later part done early does not mean the earlier one is.
- **The mark is added to the flag on `GET`, not written into the flag file** (default) — the marks log stays the only record of marks.

## Out of scope

- Marks shared between people: Phase 2.
