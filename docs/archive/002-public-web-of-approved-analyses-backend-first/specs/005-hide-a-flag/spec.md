# S5 Hide a flag

**Implements**: [RFC › Specs S5](../../RFC.md) · [ARCHITECTURE › Components (Collector, Review page), Contracts (hide, `GET /analyses`), Decisions (hidden flags)](../../../../ARCHITECTURE.md) · [interview](../../research/interview-remaining-backend.md)
**Approval**: agent · approved 2026-11-21

## Summary

The owner can hide one bad flag of a good analysis from the review page, before or after approving it, and show it again later. A hidden flag leaves everything that the public and other helpers see: the flags, the flag count, and the guest's numbers, where its claim counts as correct, as when someone marks a flag unfair. Nothing is deleted.

## Acceptance

- [X] A1 · A hidden flag leaves the public API and its guest's numbers
  - **Story:** The owner hides the flag at second 1210 of the invented debate in Spanish, a misleading claim of Ana's. Anyone then gets 11 flags from the flags call, 11 in the list of videos, and Ana's summary shows one misleading claim less and one correct claim more, with the same claims checked; the hidden flag is not among her gravest. The owner shows it again and all of it comes back.
  - **Test:** `tests/collector/hide-api.test.ts`
- [X] A2 · A hidden flag never reaches another helper, also when hidden before approval
  - **Story:** The owner hides a flag of a pending upload, then approves it. A helper that downloads the analysis gets every flag but that one. A flag hidden in an approved analysis also leaves the download.
  - **Test:** `tests/collector/hide-download.test.ts`
- [X] A3 · Only the owner can hide or show a flag
  - **Story:** Someone with no Access login, or a helper with no admin token, asks to hide a flag: the answer is refused and the flag stays. Hiding a flag id that the analysis does not hold answers "not found".
  - **Test:** `tests/collector/hide-owner-only.test.ts`
- [X] A4 · The owner hides a flag of a real video on the review page
  - **Story:** After the deploy, the owner opens a real approved debate on the review page, hides one flag, and sees it gone from `/try/` and from its guest's counts in the API within a minute; then shows it again.
  - **Test:** `review: the owner hides and shows one flag of a real approved video in /admin; curl of /api/videos/<id> and its flags before and after`

## Files

| Path | Change |
|------|--------|
| `src/collector/schema.sql` | edit — `hidden (video_id, lang, flag_id, hidden_at)`, safe to re-apply |
| `src/collector/src/index.ts` | edit — `POST /admin/analyses/<id>/flags/<flag_id>/hide\|show?lang=` (Access) and `/analyses/…` (admin token); the approved list for the page; drop hidden ids from the flags call, the list count, the summary and `GET /analyses/<id>` |
| `src/collector/web/admin/index.html` | edit — approved videos beside pending uploads; a Hide or Show button on each flag |
| `docs/ARCHITECTURE.md` | edit — the hide routes and the approved list of the page |
| `src/collector/README.md` | edit — hiding a flag |

## Tasks

- [X] T001 Add the `hidden` table in `src/collector/schema.sql`, and the hide and show routes in `src/collector/src/index.ts` → A3
- [X] T002 Drop hidden ids from the flags call, the list count and the summary in `src/collector/src/index.ts` → A1
- [X] T003 Drop hidden ids from `GET /analyses/<id>` in `src/collector/src/index.ts` → A2
- [X] T004 List approved videos and add Hide and Show on each flag in `src/collector/web/admin/index.html`; write the routes in `docs/ARCHITECTURE.md` and `src/collector/README.md`; apply the schema, deploy, hide a real flag → A4

## Decisions

- **Hidden ids live in their own table, keyed by video, language and flag id** (default) — one hide covers the pending upload and the approved one, and survives the owner's re-upload of the same flags. Rejected: editing the stored analysis.
- **The page's calls go under `/admin/` behind Access; the same routes under `/analyses/` take the admin token** (default) — as approve and reject do today.
- **A hidden id is dropped from the summary's flags before the sums** (default) — the claim stays in `checked`, so it counts as correct (interview).

## Out of scope

- A reason or a note on a hidden flag; a list of hidden flags in the CLI.
- "Correct" counting only true verdicts: S9, next RFC.
