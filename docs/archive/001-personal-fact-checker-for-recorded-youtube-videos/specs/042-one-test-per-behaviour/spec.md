# S42 One test per behaviour

**Implements**: [ARCHITECTURE · Seams](../../../../ARCHITECTURE.md#seams), [Verify](../../../../ARCHITECTURE.md#verify)
**Approval**: agent · approved 2026-11-16

## Summary

S41 put each test with its part of the system, but kept every test as it was: the same rule is still checked by several tests from different slices, and the same fake exists in several versions with a slice number in its name. This slice keeps one test per behaviour and one version of each fake, so that a contributor who changes a rule changes one test, and the suites shrink without any line of the helper losing its test.

## Acceptance

- [X] A1 · One version of each fake
  - **Story:** A contributor looks for the fake YouTube, the fake transcript or the fake model and finds each one once, in the shared helpers of the tests, with a plain name; no helper or fake carries a slice number such as `FakeClaude_s7a1` any more.
  - **Test:** `check: bash -c '[ -z "$(grep -rlE "\b[A-Za-z_]+_s[0-9]+a[0-9]+\b" tests)" ] && [ -z "$(grep -rhoE "^(class|def) [A-Za-z_0-9]+" tests/support/*.py | sort | uniq -d)" ]'`
- [X] A2 · One test per behaviour
  - **Story:** A contributor opens the judge's suite and finds each rule of the judge checked once, such as "the judge drops no flag", instead of once per slice that touched it; a test that only repeated another, or checked a rule that a later slice replaced, is gone. Each kept test still names the slices it covers in its header.
  - **Test:** `review: the build report lists each removed test with the kept test that checks the same behaviour, and both suites pass`
- [X] A3 · No line of code loses its test
  - **Story:** Before the first change, the build records which lines of the helper the tests run; after the last, the same command shows none that the tests ran before and do not run now.
  - **Test:** `check: bash docs/specs/042-one-test-per-behaviour/coverage.sh compare`

## Files

| Path | Change |
|------|--------|
| `docs/specs/042-one-test-per-behaviour/coverage.sh` | new — the S41 coverage gate, recording next to this spec |
| `tests/support/` | edit — one module per kind of fake, one version of each |
| `tests/helper/`, `tests/extension/`, `tests/collector/`, `tests/contracts/` | edit — duplicate tests merged or removed, imports from `tests/support/` |

## Tasks

- [X] T001 Copy the S41 gate to `coverage.sh` and record the coverage before any change → A3
- [X] T002 Merge the versions of each fake into one in `tests/support/`, and point every suite at it → A1
- [X] T003 In each suite of `tests/helper/`, merge the tests of one behaviour and remove those a later slice replaced; run the suite and the gate after each suite → A2, A3
- [X] T004 The same in `tests/extension/` and `tests/collector/` → A2

## Decisions

- **When two tests check one behaviour, keep the later slice's test** (default) — it states the rule in force; the earlier header joins it.
- **A test of a rule that a later slice replaced goes** (default) — such as "evasion is no longer a fallacy" once the question type exists.
- **The extension and collector suites have no line gate** (default) — the extension has no coverage tool; a removed TS test needs a kept test with the same assertion.

## Out of scope

- Changing what any test asserts about the code; this slice only removes repetition.
- The real-run measurements in `evals/`.
