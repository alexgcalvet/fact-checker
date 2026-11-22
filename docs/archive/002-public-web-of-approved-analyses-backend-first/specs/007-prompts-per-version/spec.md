# S7 Prompts of each analysis

**Implements**: [RFC › Specs S7, Proposal (Prompts)](../../RFC.md) · [ARCHITECTURE › Components (Prompt export, Shared analyses, Collector), Collector API (`GET /api/prompts/<version>`, Prompts file)](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-20

## Summary

Anyone who reads an approved analysis can now read the exact rules that the models followed to make it. The helper turns its prompts into one file with a fixed id for each reading and each rule, and names it by a version that changes whenever a word of a prompt changes. A shared analysis carries that file, and the public API serves it, so each flag leads to the rule that produced it.

## Acceptance

- [X] A1 · The helper exports its prompts, with one rule for each label that a flag can carry
  - **Story:** The owner runs `fact-checker prompts` and gets JSON with a version such as `0.1.0+3f2a9c1b7d4e` and the readings `system`, `speakers`, `screen`, `parts`, `search`, `search_results`, `check`, `verdict` and `judge`. The `parts` reading has a rule `insinuation` whose text is the insinuation line of its prompt. Each label that a flag can carry (the 11 fallacies, `partial`, `dodged`, `self`, `person`, `case`, `event`, `false`, `misleading`, `disputed`, `definition_swap`, `plan_as_fact`, `record`, `promise`) finds exactly one rule.
  - **Edge case:** WHEN one character of a prompt changes THEN the part of the version after `+` changes.
  - **Test:** `tests/helper/test_prompts.py`
- [X] A2 · A shared analysis names its prompts version and carries that prompts file
  - **Story:** A tester with sharing on finishes a whole analysis. The collector gets the analysis with helper version `0.1.0+3f2a9c1b7d4e` (the version of that helper) and, in the same upload, the prompts file of that version. For the invented prompts file of the API examples, the helper computes the same version that the file states.
  - **Test:** `tests/helper/test_sharing_prompts.py`
- [X] A3 · The API gives the prompts of an approved video, and nobody can replace them
  - **Story:** The owner has approved the invented debate. Anyone asks for the debate and sees its prompts version; the invented interview, made before prompts were exported, shows none. They ask for that version and get the file of the API examples; each flag of the debate, labelled `false`, finds rule `false` in the reading `verdict`. A version that only a pending upload names, or that nobody uploaded, gives "not found".
  - **Edge case:** WHEN a stranger uploads a file under the debate's version whose text differs THEN the collector refuses the upload (400), and the API still gives the first file.
  - **Test:** `tests/collector/api-prompts.test.ts`
- [X] A4 · A real approved video leads to its prompts on the deployed API
  - **Story:** After the deploy, the owner analyses a real video with the new helper and sharing on, so it is served at once. They ask the API for that video and get a prompts version; they ask for that version and get the file, and each flag of the video finds its rule.
  - **Test:** `review: the owner's curl of /api/videos/<real id>, then /api/prompts/<version>, and a jq check that lists no flag label missing from the rule ids of the file (ids are unique in it); curl shows /api/videos 200, /try/<id> 200 noindex, /admin/pending 302`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/prompts.py` | new — `export()`, `version_of()`, the readings and the rule of each label, cut from the prompt texts in `core/` |
| `src/helper/fact_checker/cli.py` | edit — `fact-checker prompts` prints the export |
| `src/helper/fact_checker/analyses.py` | edit — `strip()` names the prompts version; `upload()` sends the prompts file |
| `tests/helper/test_sharing.py` | edit — the S28 A1 body holds `prompts` too |
| `src/collector/src/index.ts` | edit — check and keep the prompts of an upload, once per version; `prompts` in the video call; `GET /api/prompts/<version>` |
| `src/collector/schema.sql` | edit — table `prompts` |
| `tests/support/api_fakes.ts` | edit — the debate carries the example prompts version and file |
| `docs/api-examples/` | new `prompts.json`; edit `debate.json`, `interview-en.json` — the `prompts` field |
| `src/collector/README.md` | edit — the prompts in the upload, the new route, the deploy check |

## Tasks

- [X] T001 Build the export, its version and the rule of each label in `src/helper/fact_checker/prompts.py`, and `fact-checker prompts` in `src/helper/fact_checker/cli.py` → A1
- [X] T002 Name the prompts version in `strip()` and send the prompts file in `upload()` in `src/helper/fact_checker/analyses.py`; update `tests/helper/test_sharing.py` → A2
- [X] T003 Write `docs/api-examples/prompts.json`, the debate's version in `tests/support/api_fakes.ts`, and table `prompts` in `src/collector/schema.sql` → A2, A3
- [X] T004 Check and keep the prompts, serve `GET /api/prompts/<version>` and `prompts` in the video call in `src/collector/src/index.ts`; update `docs/api-examples/` → A3
- [X] T005 Write `src/collector/README.md`, apply the schema, deploy, and check the routes with curl → A4

## Requirements

- [X] FR-001 — The collector MUST serve a prompts file only for a version that an approved analysis names.

## Decisions

- **The prompts file travels inside the analysis upload, as an optional `prompts` field** (default) — no new write route, and the upload's limits (1 MB, 10 a day per id) bound it. Rejected: a separate PUT per version. An older helper's upload without it still works.
- **Version `<package version>+<12 hex of SHA-256>` of the components as compact JSON (UTF-8, no ASCII escapes)** (default) — the package version stays `0.1.0` while the prompts change, so only a hash names them.
- **The collector recomputes the hash and keeps the first file of a version** (default) — anyone can make an install id; a file whose hash differs is refused, so no stranger can replace or squat a version.
- **`prompts` in the video call is null when the collector holds no file for its version** (default) — older analyses name `0.1.0` alone.
- **The verdict rules live once, in `verdict`; `check` has none** (default) — both readings share the same judging text, and a rule id stays unique in the file.
- **A component's text is its fixed rules, with `{placeholders}` unfilled** (default) — the message templates and answer schemas stay out.

## Out of scope

- The explore page's Prompts tab built from the export: `/explore`.
- Feedback on a rule or a quoted span: S8.
- Prompts of analyses approved before this slice: the owner re-analyses them.
