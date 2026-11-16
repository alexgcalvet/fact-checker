# S41 Tests by component

**Implements**: [ARCHITECTURE · Seams](../../ARCHITECTURE.md#seams), [Verify](../../ARCHITECTURE.md#verify)
**Approval**: person · approved 2026-11-16

## Summary

The tests grew one folder per slice: 169 files and 14,400 lines, more than twice the code, where the same rule is tested in several places and paid runs on real interviews sit next to the tests that CI runs. This slice puts each test with the part of the system that it checks, moves the paid runs to a folder of measurements, and keeps a slice's tests apart only while that slice is open. A contributor then finds every test of the judge in one file, and a change to one rule touches one test.

## Acceptance

- [X] A1 · Paid runs are measurements, not tests
  - **Story:** A contributor opens the measurements folder and finds each run on a real interview or a paid model, such as the recall run on the 1.5-hour interview, with one line on how to run it. CI does not run them. The slices that waited only on such a run (S5, S16 to S20) are closed, each with "moved to measurements, not measured yet".
  - **Test:** `check: bash -c '[ -z "$(find tests/acceptance -name "*.sh")" ] && ls evals/*.sh && ! grep -l "^- \[ \] A" docs/specs/0{05,16,17,18,19,20}-*/spec.md'`
- [X] A2 · Each part of the system has one test suite
  - **Story:** A contributor looks for the tests of the judge and finds one file for it under the helper's tests; the same holds for the reading, the fact check, setup, sharing, the summary card, each screen of the extension and each route of the collector. One folder of shared helpers holds the fakes, and none is copied.
  - **Test:** `check: [ -z "$(ls tests/acceptance)" ] && [ -z "$(find tests -name 's[0-9]*_fakes.*')" ] && (cd src/helper && uvx --quiet pytest -c pyproject.toml -q) && (cd src/extension && npx vitest run)`
- [X] A3 · No line of code loses its test
  - **Story:** Before the move, the build records which lines of the helper the tests run. After the move, the same command shows no line that the tests ran before and do not run now, such as a line of the judge's rules.
  - **Test:** `check: bash docs/specs/041-tests-by-component/coverage.sh compare`
- [X] A4 · A finished slice's tests join their suite
  - **Story:** A contributor reads the project rules and the contributing guide: a slice's acceptance tests stay in the acceptance folder, untouched, while the slice is open; when its last item is done, the closing run of the build moves them into the suite of their part, where they can be merged or removed.
  - **Test:** `review: the rule in CLAUDE.md, CONTRIBUTING.md and ARCHITECTURE · Seams and Verify`

## Files

| Path | Change |
|------|--------|
| `docs/specs/041-tests-by-component/coverage.sh` | new — `record` saves the covered lines of `fact_checker`; `compare` fails on a line covered before and not now |
| `evals/` | new — the 13 real-run scripts, a README line each |
| `tests/helper/`, `tests/extension/`, `tests/collector/`, `tests/contracts/` | new or edit — one suite per part |
| `tests/support/` | new — the shared fakes and helpers of the tests, no test |
| `tests/acceptance/` | edit — emptied |
| `src/extension/vitest.config.ts` | edit — include `tests/collector/` |
| `docs/specs/0{05,16,17,18,19,20}-*/spec.md` | edit — the open real-run items closed as moved |
| `CLAUDE.md`, `CONTRIBUTING.md`, `docs/ARCHITECTURE.md` | edit — the rule and the test paths |

## Tasks

- [X] T001 Record the coverage before any move with `coverage.sh` → A3
- [X] T002 Move the 13 real-run scripts to `evals/` and close their open items in the six specs → A1
- [X] T003 Merge the 11 `sNN_fakes.py` and `s24_d1_fake.ts` into `tests/support/` → A2
- [X] T004 Merge the helper tests into one suite per part in `tests/helper/`, the contract tests into `tests/contracts/` → A2, A3
- [X] T005 Merge the extension and collector tests into one suite per screen or route; the 11 local scripts become tests or join a suite → A2
- [X] T006 Write the rule (close a slice with `/mini-implement <id> promote`) and the new paths in `CLAUDE.md`, `CONTRIBUTING.md` and `docs/ARCHITECTURE.md` → A4

## Decisions

- **Close the waiting items without a paid run** (default) — a measurement is not a regression test; running six paid runs only to close specs beat nothing.
- **Shared fakes in `tests/support/`** (default) — the place `/mini-implement promote` already uses; the recorded answers stay in `tests/fakes/`.
- **Closed specs keep their old test paths** (default) — they are history; `/rfc close` archives them.

## Out of scope

- The same rule in the mini-spec plugin, for other projects: a change in that repo.
- A cap on test lines.
- Clearing the ARCHITECTURE marks of the closed specs: `/rfc sync` after this slice.
