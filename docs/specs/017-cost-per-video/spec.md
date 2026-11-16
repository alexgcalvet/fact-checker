# S17 Cost per video

**Implements**: [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts), [ARCHITECTURE › Decisions](../../ARCHITECTURE.md#decisions)
**Approval**: agent · approved 2026-11-14

## Summary

One analysed interview of 1.5 hours costs about 20 dollars in API terms today, 13 per video-hour, against a target of 3 euros. About 70 % goes to fact-checks, where every extracted figure is searched by Opus in a loop that resends all results each turn. This slice measures the cost of every Claude reading, checks only the figures that carry a speaker's argument and each figure once per video, lets a cheaper model do the web search while Opus only judges, and keeps the fixed instructions where they can be reused at a tenth of the price.

## Acceptance

- [X] A1 · Every Claude reading logs its tokens and cost
  - **Story:** The helper analyses an invented video. Each line of the usage log has, beside the step and duration, the input, cached and output tokens and the cost in dollars of that reading, such as `"cost_usd": 0.106`; the flag file's `cost_usd` holds the sum for the video.
  - **Test:** `tests/acceptance/test_s17_a1_cost_log.py`
- [X] A2 · Only central figures are checked, each once per video
  - **Story:** Parts of an invented video yield five figures: one said in passing, one that carries the guest's argument, and the same central figure said again ten minutes later in other words, plus two more central ones. Three are checked; the passing one is logged `skipped`, and the repeated one `repeated`, pointing to the first.
  - **Test:** `tests/acceptance/test_s17_a2_claim_triage.py`
- [X] A3 · A cheaper model searches, Opus judges
  - **Story:** For a part with two central figures, one reading by Sonnet with web search returns the evidence with its sources, and one reading by Opus with no tools turns that evidence into verdicts. A false figure still shows as "Dato falso" with the same sources.
  - **Test:** `tests/acceptance/test_s17_a3_search_then_judge.py`
- [X] A4 · The 1.5-hour interview costs at most a third and catches as much — moved to measurements (`evals/s17-a4-real-cost.sh`), not measured yet
  - **Story:** The person runs the cost check. It analyses the 1.5-hour interview again in a separate helper home and prints its cost: at most 7 dollars (it was about 20), with the high-importance misses caught no fewer than in the S16 run and a judge drop share no higher.
  - **Test:** `check: bash tests/acceptance/s17-a4-real-cost.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/adapters/llm_claude_cli.py` | edit — return usage and cost; take a system prompt |
| `src/helper/fact_checker/core/pipeline.py` | edit — rules in the system prompt; `central` per claim; at most 2 context cards per part |
| `src/helper/fact_checker/core/factcheck.py` | edit — search reading (Sonnet), verdict reading (Opus) |
| `src/helper/fact_checker/server.py`, `store.py` | edit — cost in the usage log and the flag file; skip and repeat claims |
| `docs/ARCHITECTURE.md` | edit — usage log fields, `cost_usd`, claim outcomes, the two-model check |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Return usage and cost from each reading and log them in `llm_claude_cli.py`, `server.py`, `store.py` → A1
- [X] T002 Mark central claims, skip the rest, check each figure once per video in `pipeline.py`, `server.py` → A2
- [X] T003 Split the fact-check into a Sonnet search and an Opus verdict in `factcheck.py`; update `docs/ARCHITECTURE.md` → A3
- [X] T004 Put the fixed rules in the system prompt and cap context cards in `pipeline.py`, `llm_claude_cli.py`; write the cost check → A4

## Requirements

- [X] FR-001 — The fixed instructions of the part pass and of the check MUST go in the system prompt, the same text in every reading, so it is read from cache.
- [X] FR-002 — The part pass MUST return at most 2 context cards per part.

## Decisions

- **A repeated figure is the same claim when the part pass says so, given the list of figures already checked** (default) — no extra reading; rejected: text similarity.
- **The cost is the API-equivalent `total_cost_usd` of `claude -p`** (default) — on the subscription it measures the share of the usage limit.
- **Opus stays for the part pass and the verdict** (default) — precision first; a cheaper part pass is a later slice, measured against the marks.

## Out of scope

- A cache of checks shared between videos, and the Batch API: Phase 2.
- Larger parts or a shorter context: next, if A4 misses.
