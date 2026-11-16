# S8 Contradictions in the video

**Implements**: [RFC › Specs S8](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-14

## Summary

A speaker who says one thing and later the opposite gives the viewer a reason to doubt both. This slice flags such a contradiction at the moment of the second statement, quotes both statements on the card, and only does so when the audio shows that the same voice said both. The eval also scores contradictions on invented dialogues, so their precision is measured like the other types.

## Acceptance

- [X] A1 · A speaker who contradicts themself gets a flag at the second statement
  - **Story:** In an invented interview, the guest says "no vamos a subir el IVA" and, four minutes later, "subiremos el IVA de la luz el año que viene". When the helper analyses it, the flag file has a contradiction flag at the second of the second statement, quoting it, with the first statement and its second as the earlier utterance.
  - **Edge case:** WHEN the audio puts the two statements in different voices THEN no contradiction flag is made.
  - **Test:** `tests/acceptance/test_s8_a1_self_contradiction.py`
- [X] A2 · A contradiction card shows both statements
  - **Story:** On a page that mimics the YouTube player, a contradiction flag shows at its second. The card reads "Contradicción", quotes the earlier statement with its minute, then the new one, and gives the reason.
  - **Test:** `tests/acceptance/s8-a2-contradiction-card.test.ts`
- [X] A3 · The eval scores contradictions
  - **Story:** The person runs the eval. The golden dialogues now hold planted contradictions, and the printed table has a contradiction row with its precision and recall next to the fallacy and inaccuracy rows.
  - **Test:** `tests/acceptance/test_s8_a3_eval_scores_contradictions.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/pipeline.py` | edit — the part pass also lists contradictions of a speaker with their own earlier words in the part or its context; same voice only |
| `src/helper/fact_checker/cli.py` | edit — the eval scores the contradiction type |
| `tests/golden/` | new — two invented dialogues with planted contradictions and decoys |
| `src/extension/src/flags.ts`, `src/extension/src/overlay.ts` | edit — the contradiction type and its card |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 List contradictions with the earlier statement, and keep only those where both statements are in the same voice, in `src/helper/fact_checker/core/pipeline.py` → A1
- [X] T002 [P] Show the contradiction type with both statements on the card in `src/extension/src/overlay.ts` and `flags.ts` → A2
- [X] T003 Add two golden dialogues with planted contradictions in `tests/golden/` and score the type in `src/helper/fact_checker/cli.py` → A3

## Decisions

- **Contradictions come from the same part pass, in the same tool call, over the part and its ten minutes of context** (default) — no extra Claude tool calls. Rejected: a pass over the whole video, which arrives late and costs calls.
- **The voice decides the speaker; when either statement has no voice, the flag needs the model to name the same speaker for both** (default) — videos without voices still get contradictions.
- **The label of a contradiction is `self`** (default) — S9 adds `record` for contradictions with earlier public statements.
- **The golden dialogues with contradictions are written by a stronger model and follow the format of the existing ones** (default) — the person reviews them with the diff.

## Out of scope

- Contradictions more than ten minutes apart: a later change, once the cost of a whole-video pass is measured.
- Contradictions with the speaker's earlier public statements: S9.
