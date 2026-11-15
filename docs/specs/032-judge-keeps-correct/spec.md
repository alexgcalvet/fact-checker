# S32 Judge keeps correct flags

**Implements**: [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

The judge that reads the whole video once more drops 5 to 7 correct flags per video and never the unfair one, so a person sees about 4 correct flags instead of about 10 (docs/research/abc-quality-2026-11-15.md). This slice makes the judge keep every flag: it can only keep a flag, turn a small slip of any kind into a "Puntualización", or give the line to the speaker who said it. The person's marks still win, and the found flag still stays under the judge's verdict.

## Acceptance

- [X] A1 · The judge drops no flag
  - **Story:** The helper judges an invented interview with a fallacy, a false figure and a disputed figure. The judge's reading is offered only "keep" and "nitpick" and is told that it never drops a flag. When it still answers "drop" for the disputed figure, as a provider that ignores the schema can, the flag file shows that figure as "keep" with the judge's reason, and no flag says dropped.
  - **Test:** `tests/acceptance/test_s32_a1_judge_drops_nothing.py`
- [X] A2 · A small slip of any kind becomes a "Puntualización"
  - **Story:** In the same interview, the judge rules "nitpick" on the fallacy ("el ataque es leve, lo matiza en la frase siguiente") and on a self-contradiction. The flag file keeps both as "nitpick" with those reasons, so the player shows them as grey "Puntualización" cards; each original label and reason is still there.
  - **Test:** `tests/acceptance/test_s32_a2_nitpick_any_type.py`
- [X] A3 · A speaker fix rules out an unfair flag in the marks check
  - **Story:** The person runs `fact-checker judge <video id> --against-marks` on an invented analysed interview. They marked unfair one flag that gives the host's words to the guest, and marked two flags correct. The judge gives the unfair one to the host and keeps the other two. The check prints "marked unfair, nitpicked or given to another speaker: 1 of 1" and "marked correct, touched: 0 of 2".
  - **Test:** `tests/acceptance/test_s32_a3_marks_speaker_fix.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/judge.py` | edit — verdicts `keep\|nitpick`, rules without drop, any other answer is `keep`, nitpick for every type |
| `src/helper/fact_checker/cli.py` | edit — `--against-marks` counts a speaker fix on an unfair flag |
| `docs/ARCHITECTURE.md` | edit — the `judge` field |
| `tests/acceptance/` | new — the tests and `s32_fakes.py` |

## Tasks

- [X] T001 Keep or nitpick only, nitpick for every type, rules without drop in `core/judge.py` → A1, A2
- [X] T002 [P] Count a speaker fix on an unfair flag as ruled out in `cli.py` → A3
- [X] T003 [P] The `judge` field in `docs/ARCHITECTURE.md` → A1, A2

## Decisions

- **The judge has no drop verdict; any answer other than "nitpick" becomes "keep"** — the person: "que no tire aciertos"; a chat provider's JSON fallback does not enforce the enum; rejected: trusting the model's drop.
- **No "quote not in the transcript" check** — every flag's quote is found word for word in the captions before it becomes a flag, so the check could never fire; rejected: a deterministic drop on a missing quote.
- **"nitpick" applies to every flag type** (default) — a weak fallacy or a contradiction the speaker reconciles is a small slip, not a wrong flag; rejected: S15's nitpick-to-drop for non-inaccuracies.
- **Old flag files keep their "drop" verdicts, and the extension still shows them struck through** (default) — no migration; `fact-checker judge <id>` rules on a file again.
- **The marks check counts a nitpick or a speaker fix on an unfair flag as ruled out** (default) — the one unfair flag of the ABC test was a misattribution.

## Out of scope

- Judging the ABC fragment again with real readings and the person's marks: the lead, later.
- The drop-share limits of the S16 and S19 real checks: they measure a verdict that no longer exists; `/rfc sync`.
