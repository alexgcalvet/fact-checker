# S6 Disputed figures, definition swaps and plans told as facts

**Implements**: [RFC › Specs S6](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts), [ARCHITECTURE › Decisions](../../ARCHITECTURE.md#decisions)
**Approval**: agent · approved 2026-11-14

## Summary

Official figures are often defined or framed to fit a side, so a fact-check that trusts one figure takes a side. This slice makes a figure "false" only when every credible measure contradicts it, shows a "disputed" card with each measure and its source when the measures disagree, and adds a note when the metric itself has a documented controversy. It also catches two tricks the person found in a 112-minute interview: an answer that swaps the metric that was asked for a wider one, and a plan told as if it already existed.

## Acceptance

- [X] A1 · A figure that a credible measure supports is disputed, not false
  - **Story:** A guest says "tenemos casi tres millones y medio de parados registrados". The check finds three measures: SEPE registered unemployment (2.4 million, against), registered unemployment plus inactive fijos discontinuos (about 3.3 million, for) and the EPA (2.6 million, against). The flag file gets a "disputed" flag with the three measures and a note on the fijos discontinuos controversy, not a "false" flag.
  - **Edge case:** WHEN the only measure that contradicts a claim comes from a think tank or a newspaper THEN no "false" flag is made.
  - **Test:** `tests/acceptance/test_s6_a1_disputed_not_false.py`
- [X] A2 · A disputed card shows each measure and the controversy
  - **Story:** On a page that mimics the YouTube player, a disputed flag shows at its second. The card reads "Dato discutido", lists each measure as "name: value (source)", and shows the controversy line under them.
  - **Test:** `tests/acceptance/s6-a2-disputed-card.test.ts`
- [X] A3 · An answer that swaps the metric asked is flagged
  - **Story:** In a 112-minute interview, around 1:30:07, the host asks about homes delivered and the guest answers with homes "entregadas o en proceso". After the helper analyses that part, the flag file has a "definition_swap" flag on those words that names the metric asked and the metric given.
  - **Test:** `check: bash tests/acceptance/s6-a3-a4-real-window.sh definition_swap`
- [X] A4 · A plan told as a fact is flagged
  - **Story:** In the same interview, around 1:30:42, the guest talks about Casa 47 homes as if they already existed. After the helper analyses that part, the flag file has a "plan_as_fact" flag on those words with a dated source on the plan's real status.
  - **Test:** `check: bash tests/acceptance/s6-a3-a4-real-window.sh plan_as_fact`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/flags.py` | edit — `Claim.question`; `Flag.measures`, `Flag.controversy` |
| `src/helper/fact_checker/core/pipeline.py` | edit — each claim carries the question asked just before it, if any |
| `src/helper/fact_checker/core/factcheck.py` | edit — measures with tier and support; the false/disputed rule in code; verdicts `definition_swap` and `plan_as_fact`; controversy line |
| `src/extension/src/flags.ts`, `src/extension/src/overlay.ts` | edit — new names; measures and controversy on the card |
| `docs/ARCHITECTURE.md` | edit — the inaccuracy labels and the `measures` fields of the flag file |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Ask for measures with tier and support, and apply the false/disputed rule in `src/helper/fact_checker/core/factcheck.py` and `core/flags.py` → A1
- [X] T002 [P] Show the measures and the controversy on the card in `src/extension/src/overlay.ts` and `flags.ts` → A2
- [X] T003 Carry the question asked before each claim in `src/helper/fact_checker/core/pipeline.py` → A3, A4
- [X] T004 Add the `definition_swap` and `plan_as_fact` verdicts in `src/helper/fact_checker/core/factcheck.py` and update the labels in `docs/ARCHITECTURE.md` → A3, A4

## Decisions

- **The false/disputed rule runs in code from the measures; the model only lists them** (default) — the rule is the point of the slice and must not depend on the model's mood. Rejected: trusting the model's verdict.
- **The model assigns each measure its tier from the five tiers in the prompt** (default) — a fixed table of publishers would miss most of them. Tier 5 alone never makes a "false".
- **Definition swaps and plans told as facts are found in the check step, with web search** (default) — telling a plan from a built home needs a source. Rejected: the chunk pass, which has no tools.
- **`measures` gains a `supports` field** (default) — the rule needs to know which side each measure is on.

## Out of scope

- Promises and their status over time: S9.
- Questions answered with another figure as dodged questions: S7.
