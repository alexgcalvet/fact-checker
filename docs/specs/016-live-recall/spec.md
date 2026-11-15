# S16 Live recall

**Implements**: [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts), [ARCHITECTURE › One run](../../ARCHITECTURE.md#one-run)
**Approval**: agent · approved 2026-11-14

## Summary

On the 1.5-hour interview, a whole-video reading found things the live analysis missed: a guest contradicting himself a minute later, insinuations put as questions, a double standard, cherry-picked data, and an appeal to fear. This slice makes the live analysis catch them while the video plays: it looks for four new kinds of fallacy, and each part receives a running list of what each speaker has stated so far in the whole video, so a contradiction 40 minutes apart is visible. It also logs every checkable figure taken from a part and what happened to it, so a missed figure can be traced to extraction or to the check.

## Acceptance

- [X] A1 · The live analysis flags four new kinds of fallacy
  - **Story:** The helper analyses an invented interview. The guest asks "¿es verdad que su campaña se pagó con dinero de la prostitución? ¿Sí o no?" with no evidence; demands the rival resign for a case in his circle but excuses his own leader for the same; picks the one measure that suits him; and calls immigrants an invasion. The player shows "Insinuación", "Doble rasero", "Datos a conveniencia" and "Apelación al miedo", each with the colour of a fallacy.
  - **Test:** `tests/acceptance/test_s16_a1_new_fallacies.py`
- [X] A2 · A part sees what each speaker stated earlier in the whole video
  - **Story:** In an invented 30-minute interview the guest says at 3:00 "no vamos a quitar el Ministerio de Igualdad", and at 25:00 "no habrá Ministerio de Igualdad". The part at 25:00 receives a list with "Invitado (3:00): no quitará el Ministerio de Igualdad", and the contradiction flag at 25:00 quotes the words at 3:00 with their second.
  - **Edge case:** WHEN the part that holds 3:00 is not done yet (parts run from the playback second) THEN the list holds only what finished parts before 25:00 stated.
  - **Test:** `tests/acceptance/test_s16_a2_positions_ledger.py`
- [X] A3 · Every extracted figure is logged with what happened to it
  - **Story:** A part of an invented video yields three figures: one becomes a "Dato falso" flag, one checks out as right, and one is cut by the budget. The claims log of the video has three lines with their second, speaker and outcome: `flagged`, `ok` and `unchecked`.
  - **Test:** `tests/acceptance/test_s16_a3_claims_log.py`
- [ ] A4 · The live analysis catches the high-importance misses on the 1.5-hour interview
  - **Story:** The person runs the recall check. It analyses the 1.5-hour interview again in a separate helper home (the real flag file and marks stay untouched), and prints how many of the 9 high-importance misses (minute ± 1 and kind, kept in the person's helper home) the new flags hold, and the share of flags the judge drops. It exits 0 with at least 6 of 9 caught and a judge drop share no higher than 47 %, the share before this slice.
  - **Test:** `check: bash tests/acceptance/s16-a4-real-recall.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/flags.py` | edit — four fallacy labels |
| `src/helper/fact_checker/core/pipeline.py` | edit — label definitions; the positions per speaker in and out of the part pass |
| `src/helper/fact_checker/server.py` | edit — keep the list of positions across parts; the claims log |
| `src/helper/fact_checker/store.py` | edit — append to the claims log |
| `src/extension/src/flags.ts` | edit — the Spanish names of the new labels |
| `docs/ARCHITECTURE.md` | edit — labels, claims log, positions in the part pass |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 [P] Add `insinuation`, `double_standard`, `cherry_picking`, `appeal_to_fear` in `flags.py`, `pipeline.py` and `flags.ts` → A1
- [X] T002 Return each speaker's positions from the part pass and feed the list to later parts in `pipeline.py` and `server.py` → A2
- [X] T003 Log each claim with its outcome in `server.py` and `store.py`; update `docs/ARCHITECTURE.md` → A3
- [X] T004 Write the misses list in the person's helper home and the recall check script → A4

## Requirements

- [X] FR-001 — The positions list MUST add no Claude tool call and MUST hold at most 60 lines, the oldest merged first.
- [X] FR-002 — The 9 misses MUST stay in the person's helper home as minute and kind only; no quote enters the repo.

## Decisions

- **The four new kinds are fallacy labels, not a new type** (default) — they share the purple and the fallacy bar; rejected: a new type with its own colour.
- **Positions come out of the same part call** (default) — no extra call; rejected: a separate summary call per part.
- **The claims log is `~/.fact-checker/claims.jsonl`, one line per claim: video, second, speaker, outcome** (default) — no quote, so it holds no transcript.
- **The judge stays as the last safety net** (default).

## Out of scope

- Splitting the part pass into a rhetoric call and a facts call: next, if A4 misses.
- Flags on the host's own bias.
