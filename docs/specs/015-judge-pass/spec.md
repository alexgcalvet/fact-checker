# S15 Judge pass

**Implements**: [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-14

## Summary

Each flag is found while reading one part of the video, so it can miss who is speaking to whom, the rest of the sentence, or how much a small error matters. This slice adds a judge: once the analysis of a video ends, one more Claude reading takes the whole conversation and every flag, and keeps each flag, turns it into a "puntualización" (a minor correction), drops it, or gives it to another speaker, with a one-line reason. The person's own marks always win, and the original flag stays, so the judge can be undone.

## Acceptance

- [X] A1 · The judge rules on every flag once the analysis ends
  - **Story:** The helper analyses an invented 10-minute interview with a fallacy, a false figure, a disputed figure and a context card. Before the flag file says done, one more Claude reading gets the whole transcript with speakers and minutes and the three non-context flags. In the done file, the fallacy keeps its verdict, the false figure says "puntualización: 49,8 M frente a 49,4 M, el fondo se sostiene", the disputed figure is kept (S32: the judge drops no flag), and the fallacy passes from "Luis" to "Ana Ruiz"; each original label, speaker and reason is still there.
  - **Edge case:** WHEN the judge's Claude reading fails THEN the file still ends done, with the flags as found and no verdicts.
  - **Test:** `tests/acceptance/test_s15_a1_judge_verdicts.py`
- [X] A2 · The player and the panel follow the judge unless the person marked the flag
  - **Story:** On a page that mimics the YouTube player, the flag file has a kept fallacy, a false figure judged "puntualización", a dropped flag and a dropped flag the person marked correct. The fallacy shows as usual; the "puntualización" shows as a small grey card titled "Puntualización" with the judge's reason; the dropped flag never shows on the player and appears struck through in the panel as "Descartado por el juez"; the flag marked correct shows as found.
  - **Test:** `tests/acceptance/s15-a2-judge-display.test.ts`
- [X] A3 · The shareable summary takes the speaker from the judge
  - **Story:** A flag marked correct that the judge gave from "Luis" to "Ana Ruiz" appears on Ana Ruiz's card (S35), and a flag the judge dropped and the person never marked appears nowhere.
  - **Test:** `tests/acceptance/test_s15_a3_summary_speaker.py`
- [X] A4 · The judge agrees with the person's marks on the 1.5-hour interview
  - **Story:** The person runs `fact-checker judge <video id> --against-marks` on the analysed 1.5-hour interview. It judges it again and prints how many of the flags the person marked unfair the judge dropped or turned into "puntualización", and how many of those marked correct it touched; it exits 0 only with at least 6 unfair ruled out and at most 1 correct touched (first blind run: 8 of 9 and 4 of 10; after the person reviewed the judge's reasons: 12 of 13 and 0 of 6).
  - **Test:** `check: bash tests/acceptance/s15-a4-judge-real-marks.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/judge.py` | new — the prompt, the schema and the verdict per flag |
| `src/helper/fact_checker/server.py` | edit — run the judge before the file says done |
| `src/helper/fact_checker/cli.py` | edit — `fact-checker judge <id> [--against-marks]` |
| `src/helper/fact_checker/core/summary.py` | edit — the judge's speaker; skip dropped flags |
| `src/extension/src/flags.ts`, `overlay.ts`, `panel.ts` | edit — the "Puntualización" card and the dropped row |
| `docs/ARCHITECTURE.md` | edit — the `judge` field |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Write the judge and run it before the file says done in `core/judge.py` and `server.py` → A1
- [X] T002 [P] Show "Puntualización" and dropped flags in `flags.ts`, `overlay.ts`, `panel.ts` → A2
- [X] T003 [P] Use the judge's speaker and skip dropped flags in `core/summary.py`; update `docs/ARCHITECTURE.md` → A3
- [X] T004 Add `fact-checker judge` with `--against-marks` in `cli.py` → A4

## Requirements

- [X] FR-001 — The judge MUST make one Claude tool call per started 2 video-hours, with no web search, counted in the video's budget.
- [X] FR-002 — The judge's rules MUST come from the person's principles and the marks on the 112-minute interview only; no case from that interview may appear in the prompt.

## Decisions

- **Verdicts in a `judge` field on each flag: `{verdict: keep|nitpick|drop, reason, speaker?}`** (default) — the found flag stays, so the judge is reversible; rejected: rewrite the flag.
- **The file says done only after the judge** (default) — the extension stops polling at done; rejected: a new `judging` status.
- **"puntualización" applies to inaccuracies only; a weak fallacy, question or contradiction is dropped** (default).
- **All non-context flags go to the judge, on the player or not** (default) — same single call.

## Out of scope

- Fixing caption errors in quotes ("Teuta").
- Re-checking figures on the web: the judge reads only the sources that the flags already hold.
