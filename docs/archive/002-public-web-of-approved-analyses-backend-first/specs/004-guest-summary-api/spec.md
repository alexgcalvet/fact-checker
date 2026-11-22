# S4 Guest summary in the API

**Implements**: [RFC › Specs S4](../../RFC.md) · [ARCHITECTURE › Contracts (`GET /api/videos/<id>?lang=`, shared analysis), Decisions (guest summary)](../../../../ARCHITECTURE.md) · [interview](../../research/interview-remaining-backend.md)
**Approval**: agent · approved 2026-11-21

## Summary

The public video call gives, for each guest, the numbers of the helper's profile card: claims checked, false, misleading, nitpicks and correct, the severities, the rhetorical devices, the dodged questions and the two gravest flags. The helper computes them when it shares an analysis and writes, for each flag, which numbers it adds to, so the collector can later drop a hidden flag from the counts without Python. The owner can share a local analysis again, so a real approved video gets its summary and its prompts file.

## Acceptance

- [X] A1 · A shared analysis carries each guest's summary, and its flags add up to the card
  - **Story:** The helper shares the invented debate (guests Ana and Luis). The upload holds, for each guest, the claims checked and questions asked, and for each flag of that guest the numbers it adds to. Adding up every flag gives exactly the numbers of the guest's profile card, such as Ana's false, misleading, nitpick and correct claims of her claims checked. The upload of the invented debate is the one written in the API examples.
  - **Test:** `tests/helper/test_summary_upload.py`
- [X] A2 · The video call shows each guest's summary
  - **Story:** Anyone asks the API for the invented debate in Spanish and gets a summary for Ana and one for Luis: checked, the verdicts, the severities, the devices with their counts, dodged, partial, asked, and the ids of the two gravest flags. The answer is the one in the API examples. The interview, uploaded before summaries existed, gives no summary.
  - **Test:** `tests/collector/api-summary.test.ts`
- [X] A3 · The owner's upload replaces the stored analysis
  - **Story:** The owner runs `fact-checker shared upload <video> es` for a video already approved, read by the same model. The collector keeps the new upload, with its summary and prompts, in place of the old one. A stranger's upload of that video by the same model is still refused.
  - **Test:** `tests/collector/owner-replaces.test.ts`, `tests/helper/test_shared_upload.py`
- [X] A4 · A real approved video shows the numbers of its profile card
  - **Story:** After the deploy, the owner shares a real approved debate again. The API shows, for each guest, the numbers of the profile card that the helper renders for that guest, and `/api/prompts/<version>` gives its prompts file.
  - **Test:** `review: the owner's curl of /api/videos/<real id> beside the two profile cards of the helper; /api/prompts/<version> 200`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/summary.py` | edit — `tally(data, name)`: a guest's `checked`, `asked`, the numbers each flag adds to, the gravest candidates in order; `card` counts from it |
| `src/helper/fact_checker/analyses.py` | edit — the shared analysis gets `summary`: the tally of each guest |
| `src/helper/fact_checker/cli.py` | edit — `fact-checker shared upload <video_id> <lang>` shares a local analysis again |
| `src/collector/src/index.ts` | edit — check `summary` on upload; an owner's upload replaces a stored one by an equal model; the video call sums the tallies |
| `tests/support/api_fakes.ts` | edit — the debate uploads carry the summary of `docs/api-examples/summary-upload.json` |
| `docs/api-examples/` | new `summary-upload.json` (the invented debate's upload summary); edit `debate.json`, `interview-en.json` |
| `docs/ARCHITECTURE.md` | edit — the shape of `summary` in the video call and in the shared analysis |
| `src/collector/README.md` | edit — `shared upload` and the summary |

## Tasks

- [X] T001 Write `tally` and count the card from it in `src/helper/fact_checker/core/summary.py`, and write `docs/api-examples/summary-upload.json` from the invented debate → A1
- [X] T002 Add `summary` to the shared analysis in `src/helper/fact_checker/analyses.py` → A1
- [X] T003 Check `summary` on upload and sum it in the video call in `src/collector/src/index.ts`; feed the fakes in `tests/support/api_fakes.ts`; update `debate.json` and `interview-en.json` → A2
- [X] T004 Let the owner's upload replace a stored one in `src/collector/src/index.ts`, and add `shared upload` in `src/helper/fact_checker/cli.py` → A3
- [X] T005 Write the summary shape in `docs/ARCHITECTURE.md` and `src/collector/README.md`, deploy, share a real debate again → A4

## Decisions

- **The upload summary is keyed by flag id** (default) — per guest `{checked, asked, flags: {<id>: {verdict, severity, device, question}}, gravest: [<id>…]}`; the flags stay as they are, and S5 drops a hidden id. Rejected: a tag inside each flag, which the flags call would serve.
- **The video call serves `summary: {<guest>: {checked, verdicts, severity, devices, dodged, partial, asked, gravest}}`** (default) — `guests` stays a list of names, as in the list call; `gravest` holds flag ids, which the flags call gives in full; `correct` is `checked` less false, misleading and nitpick.
- **Counted from the judge's verdicts only** (default) — the uploader's marks never travel, so the public summary is the card with no marks.
- **The owner's upload replaces one by an equal or worse model** (default) — the owner is the review; a stranger's still needs a better model.

## Out of scope

- Hiding a flag and its effect on the counts: S5.
- "Correct" counting only true verdicts, unverifiable apart: S9, next RFC.
- The comparison card of several people, and the card images: frontend RFC.
