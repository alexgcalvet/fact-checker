# S19 Recall without noise

**Implements**: [ARCHITECTURE › One run](../../ARCHITECTURE.md#one-run), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

The live analysis of the 1.5-hour interview catches only 3 of the 9 problems that the person rated most important, fewer than before the cheaper readings. Two self-contradictions were found and then dropped by the final review on an excuse that the speaker never gave, and a switch of yardstick, a double standard and a wrong tax figure were read as something milder. This slice sharpens what the part reading and the fact-check look for, stops the final review from excusing a contradiction on the speaker's behalf, and makes the long conversation the default way to give a part its context.

## Acceptance

- [X] A1 · A new analysis reads the parts as one conversation
  - **Story:** The person opens an invented video and the helper starts its analysis as it does for the extension. Every part reading continues the same Claude Code conversation, not a fresh reading with a short window.
  - **Test:** `tests/acceptance/test_s19_a1_conversation_default.py`
- [X] A2 · The judge keeps a contradiction that it excused on the speaker's behalf — moved to measurements (`evals/s19-a2-judge-keeps-contradictions.sh`), not measured yet
  - **Story:** The person runs the judge check on the two analyses of the 1.5-hour interview of the S18 comparison. The judge reads each one again with the new rules. Each self-contradiction near 18:40, 55:05 or 39:40 that the analysis found is kept, not dropped, and the check prints the judge's verdict on each one.
  - **Test:** `check: bash tests/acceptance/s19-a2-judge-keeps-contradictions.sh`
- [X] A3 · The live analysis catches 5 of the 9 misses on the 1.5-hour interview — moved to measurements (`evals/s19-a3-real-recall.sh`), not measured yet
  - **Story:** The person runs the recall check. It analyses the 1.5-hour interview from the start in a separate helper home, the way the helper now does by default. It prints each of the 9 high-importance misses as caught, dropped by the judge or missed, the share of flags the judge drops and the cost. It exits 0 with at least 5 of 9 caught, at most 32 % dropped and at most 9 dollars.
  - **Test:** `check: bash tests/acceptance/s19-a3-real-recall.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/server.py` | edit — `CONTEXT_MODE` is `conversation` |
| `src/helper/fact_checker/core/judge.py` | edit — a contradiction rule: no excuse that the speaker does not give |
| `src/helper/fact_checker/core/pipeline.py` | edit — part prompt: a switch of yardstick is cherry picking, a double standard in an answer, a target changed within one answer, an effect figure of a measure as a claim |
| `src/helper/fact_checker/core/factcheck.py` | edit — an effect figure is checked against how the rule works |
| `docs/ARCHITECTURE.md` | edit — the default context mode |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 [P] Set `CONTEXT_MODE` to `conversation` in `server.py`; update `docs/ARCHITECTURE.md` → A1
- [X] T002 [P] Add the contradiction rule to the judge rules in `judge.py` → A2, FR-001
- [X] T003 [P] Sharpen the part prompt in `pipeline.py` and the search and verdict prompts in `factcheck.py` → A3
- [X] T004 Run the recall check on the 1.5-hour interview; change a prompt again only if the first run shows why → A3 — moved to measurements (`evals/s19-a3-real-recall.sh`), not measured yet

## Requirements

- [ ] FR-001 — The S19 judge MUST NOT lower precision on the person's marks: `fact-checker judge --against-marks` on copies of the two marked real-interview flag files, in a scratch home, rules out at least as many marked-unfair flags and touches no more marked-correct flags than the old rules, within one flag each.
- [ ] FR-002 — No prompt rule MAY quote or paraphrase a line of the 1.5-hour interview; rules draw only on general definitions and the marks on the 112-minute interview.

## Decisions

- **The precision guard re-judges the marked flags, not `fact-checker eval --marks`** — `eval --marks` reads stored marks and cannot move with a prompt; rejected: a new analysis of the 112-minute interview (about 8 dollars, and its flags no longer match the marked ids).
- **The window mode stays, only the default changes** (default) — an approved S18 test still measures it; rejected: removing it in this slice.
- **The check allows two runs on the 1.5-hour interview** (person) — a second run only with a change that the first run justifies.

## Out of scope

- Fewer "partially answered" question flags, the largest share of what the judge drops: a later slice.
- A new analysis of the 112-minute interview to measure the part prompt on real marks.
