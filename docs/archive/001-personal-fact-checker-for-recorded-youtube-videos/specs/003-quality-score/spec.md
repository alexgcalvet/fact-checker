# S3 Quality score

**Implements**: [RFC › Specs S3](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts), [ARCHITECTURE › Components](../../../../ARCHITECTURE.md#components)
**Approval**: person · approved 2026-11-14

## Summary

Today nobody knows how often a flag is right, and the 0.80 bar on the player was a guess: on a real interview it showed almost nothing. This slice adds a set of invented Spanish dialogues with known errors and a command that runs the real analysis on them and prints, per flag type, how many flags are right and how many errors are found. From those numbers it picks, per type, the lowest confidence at which flags are right at least 8 times in 10, and only flags above that bar reach the player.

## Acceptance

- [X] A1 · The eval prints precision and recall per flag type on the golden dataset
  - **Story:** The person runs the eval command with their Google key. After some minutes it prints a table with one row per flag type (fallacy, inaccuracy) and, for each, the precision and recall at the bars 0.5, 0.6, 0.7, 0.8 and 0.9, and the bar it recommends.
  - **Test:** `check: bash tests/acceptance/s3-a1-eval-on-golden.sh`
- [X] A2 · The eval scores flags against the expected ones
  - **Story:** Two invented dialogues hold 4 expected fallacies. The model returns 3 fallacies: 2 on the expected words with the expected name, 1 elsewhere. The eval reports fallacy precision 67% and recall 50%.
  - **Edge case:** WHEN a flag has the expected name but quotes only part of the expected words THEN it counts as right if it shares at least half of their words.
  - **Test:** `tests/acceptance/test_s3_a2_eval_scores.py`
- [X] A3 · The eval picks the bar per type and saves it
  - **Story:** The fallacy flags of a run have confidences 0.9 right, 0.85 right, 0.7 wrong, 0.6 right, 0.5 wrong; the inaccuracy flags are all wrong. With "save", the eval writes fallacy 0.85 and inaccuracy "never" to the thresholds file.
  - **Test:** `tests/acceptance/test_s3_a3_pick_threshold.py`
- [X] A4 · Only flags above their type's bar reach the player
  - **Story:** With bars fallacy 0.5 and inaccuracy 0.9, the helper marks a 0.55 fallacy for the player and a 0.85 inaccuracy not; on the mimic player page the fallacy card shows and the inaccuracy card does not.
  - **Test:** `check: bash tests/acceptance/s3-a4-bar-per-type.sh`

## Files

| Path | Change |
|------|--------|
| `tests/golden/` | new — 10 dialogues, one JSON file each: lines with second, speaker and text; expected flags; publish date |
| `src/helper/fact_checker/core/score.py` | new — match flags to expected ones, precision and recall per type and bar, pick the bar |
| `src/helper/fact_checker/cli.py` | new — `serve`, `analyze <url>` and `eval [--save]` |
| `src/helper/fact_checker/thresholds.json` | new — the bar per type; starts at 0.80 for both |
| `src/helper/fact_checker/server.py` | edit — mark `on_player` on each flag from the bars |
| `src/helper/pyproject.toml` | edit — the `fact-checker` command points at the CLI |
| `src/extension/src/flags.ts`, `src/extension/src/overlay.ts` | edit — show a flag when `on_player` is true; 0.80 when the field is missing |
| `tests/acceptance/` | new — the four tests |

## Tasks

- [X] T001 Write the 10 dialogues with a stronger model in `tests/golden/` → A1, FR-002
- [X] T002 Match, score and pick the bar in `src/helper/fact_checker/core/score.py` → A2, A3
- [X] T003 Add `serve`, `analyze` and `eval` in `src/helper/fact_checker/cli.py` and the command in `src/helper/pyproject.toml` → A1, A2, A3
- [X] T004 Mark `on_player` from `src/helper/fact_checker/thresholds.json` in `src/helper/fact_checker/server.py` → A4
- [X] T005 [P] Show flags by `on_player` in `src/extension/src/overlay.ts` → A4
- [X] T006 Run the eval, save the bars and report them → A1

## Requirements

- [X] FR-001 — One eval run MUST stay under 100 Claude tool calls.
- [X] FR-002 — Each dialogue MUST be reviewed by the person before it enters `tests/golden/`; inaccuracies use real public figures with their source.

## Decisions

- **10 dialogues of 3–5 minutes, with 2–4 planted fallacies, 1–3 false figures and as many true claims and fair arguments as decoys** (default) — decoys measure precision; about 60 calls per run.
- **The bar is the lowest confidence at which the flags at or above it have precision ≥ 0.80; a type with fewer than 5 scored flags, or no such confidence, gets "never"** (default) — fewer flags make the number noise.
- **Bars per type, not one bar** (default) — the model's fallacy confidences run lower than its fact checks.
- **The person reviews the dialogues by reading them in chat before they are saved** (default) — FR-002.

## Out of scope

- Prompt tuning to raise the scores, and source tiers that lower confidence for non-primary sources (an interview decision S2 did not build): S6, once S3 gives a baseline.
- Scores for questions and contradictions: S7 and S8 add their expected flags to the dataset.
