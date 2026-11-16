# S7 Unanswered questions

**Implements**: [RFC › Specs S7](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts), [ARCHITECTURE › Decisions](../../../../ARCHITECTURE.md#decisions)
**Approval**: agent · approved 2026-11-14

## Summary

In an interview, the question that the guest does not answer often matters more than any figure. This slice gives each question of the interviewer a status when its answer ends: answered, partly answered or dodged. An answer that gives a different figure from the one asked counts as dodged. A dodged question shows a card at the end of the answer with the question and a one-line reason, and "evasion" stops being a fallacy.

## Acceptance

- [X] A1 · A dodged question is flagged at the end of its answer
  - **Story:** In an invented interview, the host asks "¿cuántas viviendas se han entregado?" and the guest talks for a minute about the housing law. When the helper analyses it, the flag file has a "question" flag with status "dodged" at the second the answer ends; it holds the host's question and a reason.
  - **Edge case:** WHEN the guest answers with another figure, "184.000 viviendas entregadas o en proceso", THEN the question is still "dodged".
  - **Test:** `tests/acceptance/test_s7_a1_dodged_question.py`
- [X] A2 · A dodged-question card shows the question
  - **Story:** On a page that mimics the YouTube player, a dodged-question flag shows at its second. The card reads "Pregunta esquivada", quotes the host's question, and gives the reason.
  - **Test:** `tests/acceptance/s7-a2-dodged-card.test.ts`
- [X] A3 · "Evasion" is no longer a fallacy
  - **Story:** In an invented interview, the model still names a passage "evasion" as a fallacy. The flag file has no fallacy flag for it; the passage only goes to the log of candidate names.
  - **Test:** `tests/acceptance/test_s7_a3_evasion_not_fallacy.py`
- [X] A4 · A real dodged question shows on a 112-minute interview
  - **Story:** The helper analyses the part of a 112-minute interview from 1:29:00 to 1:32:00, where the host asks about homes delivered. The flag file has a "question" flag with status "dodged" that quotes the host's question about homes.
  - **Test:** `check: bash tests/acceptance/s7-a4-real-dodged-question.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/flags.py` | edit — `evasion` leaves the fallacy list; `Flag.answer` |
| `src/helper/fact_checker/core/pipeline.py` | edit — the part pass also lists each interviewer question whose answer ends in the part, with its status |
| `src/extension/src/flags.ts`, `src/extension/src/overlay.ts` | edit — the question type and its card |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 List the questions whose answer ends in the part, with status and reason, and make flags for dodged and partial ones in `src/helper/fact_checker/core/pipeline.py` and `core/flags.py` → A1, A4
- [X] T002 Remove `evasion` from the fallacy list and the prompt in `src/helper/fact_checker/core/flags.py` and `core/pipeline.py` → A3
- [X] T003 [P] Show the question type with the question on the card in `src/extension/src/overlay.ts` and `flags.ts` → A2

## Decisions

- **The questions come from the same part pass, in the same tool call** (default) — no extra Claude tool calls, so the budget of 60 per video-hour stays; this answers the open budget question for S7. Rejected: a separate pass per question.
- **A question is judged in the part where its answer ends; the question can sit in the ten minutes of context** (default) — the status needs the whole answer.
- **Only "dodged" and "partial" make flags; "answered" makes none** (default) — a card for every answered question is noise.
- **The question type has no bar yet; the player shows it from 0.8 confidence, as other types without a bar** (default) — the person's marks will set it.

## Out of scope

- Scoring questions in the golden eval: a later change, once marks exist.
- Questions answered in a later part of the video: Step 3.
