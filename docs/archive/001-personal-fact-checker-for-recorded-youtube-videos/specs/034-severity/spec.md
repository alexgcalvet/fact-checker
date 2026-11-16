# S34 Severity

**Implements**: [RFC › Specs](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

Today every kept flag weighs the same: a misleading figure that changes little looks like one that changes the whole argument. After this slice, the final review also says how serious each kept flag is (minor, moderate or serious) by how much the error changes the point, how central it is to what the speaker argues and how big it is, never by what the speaker meant. A serious card says so in its title, and quiet mode shows only the serious ones; a "Puntualización" stays apart, grey, with no severity.

## Acceptance

- [X] A1 · The judge rules a severity on each flag it keeps
  - **Story:** The person runs the judge on an invented interview with three flags. The judge keeps a false figure as serious, keeps a weak generalisation as minor and turns a near date into a puntualización. The flag file holds `serious` and `minor` on the two kept flags and no severity on the puntualización.
  - **Edge case:** WHEN a provider answers a kept flag with no severity or an unknown one THEN the flag is kept with no severity.
  - **Test:** `test_s34_a1_severity_on_keep.py`
- [X] A2 · A serious card says "grave" in its title
  - **Story:** The person plays a video whose file holds a serious false figure, a moderate misleading one and a puntualización. The first card reads "Dato falso · grave" ("False claim · serious" in English), the second reads "Dato engañoso", and the puntualización stays grey with no severity word. The side panel rows read the same.
  - **Test:** `s34-a2-serious-title.test.ts`
- [X] A3 · Quiet mode shows serious flags only
  - **Story:** The person turns on quiet mode, now called "Solo graves", on the same video. The serious card shows; the moderate one does not. While the analysis is still running and nothing is judged yet, a flag shows only with a confidence of 90 % or more, as before.
  - **Test:** `s34-a3-quiet-serious.test.ts`
- [X] A4 · The judge spreads the 1.5-hour interview over the three levels
  - **Story:** The person runs the severity check. It judges a copy of the 1.5-hour interview again in a separate helper home and prints how many kept flags fall in each level, and the minute, label and reason of each serious one. It exits 0 when each level holds at least one flag and serious ones are at most a third of the kept flags.
  - **Test:** `check: bash tests/acceptance/s34-a4-real-severity.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/judge.py` | edit — `severity` in the schema and the rulings, the rubric in the rules, kept only on a `keep` |
| `src/extension/src/flags.ts` | edit — `severity` in the judge type; the title adds the serious word |
| `src/extension/src/overlay.ts` | edit — the quiet rule: serious only, confidence ≥ 0.9 for an unjudged flag |
| `src/extension/src/texts.ts` | edit — the serious word and the quiet label in Spanish and English |
| `tests/acceptance/` | new — the tests and the check |

## Tasks

- [X] T001 Add severity and the rubric to the judge in `judge.py` → A1, A4
- [X] T002 [P] Add severity to the judge type and the serious word to the title in `flags.ts`, `texts.ts` → A2
- [X] T003 Make quiet mode serious-only with the confidence rule for unjudged flags in `overlay.ts`, `texts.ts` → A3

## Decisions

- **An unjudged flag uses the old quiet rule** (default) — the judge runs only after the last part, so a serious-only rule would hide every card while the analysis runs; rejected: hide all until judged.
- **Only serious adds a word to the title** (default) — the RFC names "· grave" only; minor and moderate keep the plain title.
- **The A4 bar: every level used, serious ≤ ⅓ of kept** (default) — a rubric that calls most flags serious tells the viewer nothing; the person reads the serious list for the rest.
- **The rubric lives in the judge rules** (default) — the page that publishes it for viewers is the link of the card (S35).

## Out of scope

- Severity counts and the two most serious quotes on the card: S35. Per-hour rates: S36.
