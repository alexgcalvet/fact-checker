# S7 Visits and the end of `/try/`

**Implements**: [RFC Specs S7](../../RFC.md) · [ARCHITECTURE Contracts: `GET /`, `/es/*`, `/en/*`, `POST /api/visits`, `GET /admin/visits`, `GET /try/<video_id>`](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

The owner sees on the review page how many times each video was opened and how many times someone jumped to a flag's moment, per day and language, with no cookie and nothing that tells one person from another. The old test page goes: its links open the new viewer, so there is one place to watch an analysis.

## Acceptance

- [X] A1 · Opening a video page counts a visit
  - **Story:** Someone opens `/es/v/debate01` twice and `/en/v/debate01` once today. The owner opens `/admin` and its visits table shows debate01, "es", today, 2 visits; and debate01, "en", today, 1 visit.
  - **Edge case:** WHEN someone opens `/es/v/nope` (no approved video) THEN the table shows no row for it.
  - **Test:** `tests/collector/visits-page.test.ts`
- [X] A2 · A jump to a flag's moment counts a seek
  - **Story:** A viewer on `/es/v/debate01` taps the time 20:10 of a flag, then a mark on the timeline. Two seeks are sent, with no consent question; the owner's visits table shows debate01, "es", today, 2 seeks.
  - **Test:** `tests/web/viewer-seek-counted.test.ts`
- [X] A3 · An old test page link opens the viewer
  - **Story:** Someone with a Spanish browser opens an old link `/try/debate01` and lands on `/es/v/debate01`; with an English browser, on `/en/v/debate01`. `/try/try.js` no longer exists.
  - **Test:** `tests/collector/try-redirects.test.ts`
- [X] A4 · The owner sees real visits
  - **Story:** After deploy, the owner opens a real approved debate on the viewer, taps two flags' times, and sees one visit and two seeks for it today on `/admin`; an old `/try/` link of it opens the viewer.
  - **Test:** `review: /admin after one visit and two seeks on the deployed viewer, and an old /try/ link`

## Requirements

- [X] FR-001 — Each counter (video, language, day, visit or seek) MUST stop at 10,000 a day.

## Files

| Path | Change |
|------|--------|
| `src/collector/schema.sql` | edit — the `visits` table: video, language, UTC day, kind, count |
| `src/collector/src/index.ts` | edit — count a visit on a video page, `POST /api/visits`, `GET /admin/visits`, `/try/<id>` redirects |
| `src/collector/web/admin/index.html` | edit — the visits table |
| `src/collector/wrangler.toml`, `src/collector/README.md` | edit — the routes without the test page |
| `src/web/src/Viewer.tsx` | edit — send a seek on each jump to a flag |
| `src/collector/web/try/`, `src/extension/src/try.ts`, `src/extension/build.mjs`, `tests/web/try-*.test.ts` | remove — the test page, its build and its tests |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Add the `visits` table and count a visit when the Worker serves an approved video page, in `src/collector/schema.sql` and `src/collector/src/index.ts` → A1, FR-001
- [X] T002 Add `POST /api/visits` and send a seek from each jump to a flag, in `src/collector/src/index.ts` and `src/web/src/Viewer.tsx` → A2, FR-001
- [X] T003 Add `GET /admin/visits` and the visits table of the review page, in `src/collector/src/index.ts` and `src/collector/web/admin/index.html` → A1, A2
- [X] T004 Redirect `/try/<id>` by browser language and remove the test page, its build and its tests, in `src/collector/src/index.ts`, `src/collector/wrangler.toml`, `src/collector/README.md`, `src/extension/build.mjs` → A3
- [X] T005 Apply the schema, build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **A seek is sent with no consent question** (default) — it is one anonymous counter with no id, as the visit; rejected: behind the marks' consent.
- **A chat app fetching a link counts as a visit** (default) — no user-agent guessing; rejected: a bot filter.
- **`/try/` answers 301 by the browser's language, as `/` does** (default) — the viewer shows the note when only the other language exists.

## Out of scope

- The test page's comment on the method: S6 brings it back on "Cómo funciona".
- A chart of visits over time: the table is enough for the beta.
