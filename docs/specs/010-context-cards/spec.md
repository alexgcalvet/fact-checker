# S10 Context cards

**Implements**: [RFC › Specs S10](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-14

## Summary

An interview names people, cases and events that many viewers do not know, and the point is lost without them. This slice shows a short, neutral card the first time a person, a case or an event is named: who or what it is, in one sentence, with no judgement. Later mentions of the same name get no card.

## Acceptance

- [X] A1 · A named person gets one context card, at the first mention
  - **Story:** In an invented interview, the guest names "Marta Gil" at minute 3 and again at minute 9, in another part. When the helper analyses it, the flag file has one context flag for that minister, at the second of the first mention, with one sentence saying who he is.
  - **Edge case:** WHEN the later part is analysed before the earlier one THEN the file still keeps one context flag, at the first mention.
  - **Test:** `tests/acceptance/test_s10_a1_first_mention.py`
- [X] A2 · A context card shows who or what was named
  - **Story:** On a page that mimics the YouTube player, a context flag shows at its second. The card reads "Contexto", names "Marta Gil" and gives the sentence, with no buttons to mark it unfair as a claim.
  - **Test:** `tests/acceptance/s10-a2-context-card.test.ts`
- [X] A3 · A real interview gets a context card for a named minister
  - **Story:** The helper analyses the part of a 112-minute interview from 26:40 to 28:40, where a minister is named. The flag file has a context flag for that minister with one sentence on who he is.
  - **Test:** `check: bash tests/acceptance/s10-a3-real-context.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/pipeline.py` | edit — the part pass also lists people, cases and events named in the part, with a neutral sentence each |
| `src/helper/fact_checker/store.py` | edit — keep one context flag per name, the earliest |
| `src/extension/src/flags.ts`, `src/extension/src/overlay.ts` | edit — the context type and its card |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 List named people, cases and events with a neutral sentence in `src/helper/fact_checker/core/pipeline.py` → A1, A3
- [X] T002 Keep one context flag per name, the earliest, in `src/helper/fact_checker/store.py` → A1
- [X] T003 [P] Show the context card in `src/extension/src/overlay.ts` and `flags.ts` → A2

## Decisions

- **Context comes from the same part pass, from the model's knowledge, in the same tool call** (default) — no extra Claude tool calls; well-known people need no search. Rejected: a web search per name.
- **The label is the kind (`person`, `case`, `event`); the quote is the name as said; the reason is the sentence** (default) — the flag file stays one shape.
- **Context cards have no correct/unfair buttons** (default) — they are not claims about the speaker.
- **Context cards show from the default bar of 0.8, like other types without a bar** (default).

## Out of scope

- Context from a web search for people the model does not know: a later change, if marks show gaps.
