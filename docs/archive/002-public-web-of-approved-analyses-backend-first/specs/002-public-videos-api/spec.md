# S2 Read approved videos through the API

**Implements**: [RFC › Specs S2](../../RFC.md) · [ARCHITECTURE › Contracts (collector routes, Cursor, Examples)](../../../../ARCHITECTURE.md)
**Approval**: person · approved 2026-11-20

## Summary

Anyone can read the approved analyses through a public JSON interface: the list of approved videos, one video in the language they ask for, and its flags. The flags come with a cursor, so a page that asks again later gets only what is new; this is the same call that will serve live streams. Example answers of an invented debate and interview let the frontend of the brand be designed now, before it can call the real one.

## Acceptance

- [X] A1 · The list shows each approved video once, and never a pending upload
  - **Story:** The owner has approved an invented debate in Spanish and English and an invented interview in Spanish; a tester's upload of a third video waits for review. Anyone opens the list of videos and sees two entries: the debate with languages "es, en", type "debate", its two guests and 12 flags; the interview with "es", type "interview", one guest and 5 flags. The third video is not there. The answer is the one written in the API examples.
  - **Edge case:** WHEN a web page on any other site reads the list from a browser THEN the browser allows it.
  - **Test:** `tests/collector/api-videos.test.ts`
- [X] A2 · One video comes in the asked language, or in the other one with a note
  - **Story:** Anyone asks for the debate in English and gets its English title, channel, duration, date, type and guests, marked as English. They ask for the interview in English: it exists only in Spanish, so they get the Spanish one, marked as Spanish and as asked in English. A video that is unknown, or only pending, gives "not found". Both answers are the ones in the API examples.
  - **Test:** `tests/collector/api-video.test.ts`
- [X] A3 · The flags come in order with a cursor, and the cursor gives nothing new
  - **Story:** Anyone asks for the flags of the debate in Spanish and gets its 12 flags in the order of their second, a cursor, and "not live". They ask again with that cursor and get no flag and the same cursor. The first answer is the one in the API examples.
  - **Edge case:** WHEN the cursor is not one that the API gave THEN the answer is "bad cursor" (400), never every flag again.
  - **Test:** `tests/collector/api-flags.test.ts`
- [X] A4 · A real approved video reads through the deployed API, from the cache
  - **Story:** After the deploy, the owner asks the list of videos and sees the real video approved in the review page. They ask for its flags and get them all with a cursor; the cursor gives nothing new. They ask the same list twice: the second answer comes from Cloudflare's cache. Its field names are those of the API examples.
  - **Test:** `review: the owner's curl of the deployed /api/videos, its flags with and without the cursor, and Cf-Cache-Status HIT on a repeated call`

## Files

| Path | Change |
|------|--------|
| `src/collector/src/index.ts` | edit — `GET /api/videos`, `/api/videos/<id>?lang=`, `/api/videos/<id>/flags?lang=&after=` from `analyses` only; a cached entrypoint for `/api/*`; CORS and `Cache-Control` headers |
| `src/collector/wrangler.toml` | edit — `[cache]` on, off for the default entrypoint; `/api/*` in `run_worker_first` |
| `tests/support/api_fakes.ts` | new — the invented debate (es, en) and interview (es) as stored analyses, no real name, quote or id |
| `docs/api-examples/` | new — `videos.json`, `debate.json`, `interview-en.json`, `debate-flags.json`: the answers to those fakes |
| `src/collector/README.md` | edit — the three `/api/` routes, the cache and the deploy check |

## Tasks

- [X] T001 Write the invented debate and interview in `tests/support/api_fakes.ts` → A1, A2, A3
- [X] T002 Serve `GET /api/videos` from the approved analyses, with CORS, in `src/collector/src/index.ts`, and write `docs/api-examples/videos.json` → A1
- [X] T003 Serve `GET /api/videos/<id>?lang=` with the language fallback in `src/collector/src/index.ts`, and write `docs/api-examples/debate.json` and `interview-en.json` → A2
- [X] T004 Serve `GET /api/videos/<id>/flags` with the cursor in `src/collector/src/index.ts`, and write `docs/api-examples/debate-flags.json` → A3
- [X] T005 Move `/api/*` to a cached entrypoint with `Cache-Control: public, max-age=60` in `src/collector/src/index.ts` and `src/collector/wrangler.toml` → A4
- [X] T006 Write the routes in `src/collector/README.md`, deploy, and check a real video and the cache → A4

## Requirements

- [X] FR-001 — Every response outside `/api/*` MUST stay out of the cache: the default entrypoint runs with caching off.

## Decisions

- **CORS open to any origin** (user, 2026-11-20) — read-only public data with no credentials; one cached answer serves every origin. Rejected: a list of frontend origins.
- **Workers Caching on a separate entrypoint, 60 s** (default) — it works on `workers.dev`, and with caching on for the whole Worker an answer with no header is cached for 2 hours, `/admin*` included (`docs/research/workers-caching.md`). An approval shows within a minute; a deploy starts a fresh cache. Rejected: the Cache API, a purge on approve.
- **The list has one entry per video** (default) — its fields and flag count come from its newest approved language; `langs` lists all of them.
- **The cursor is the number of flags already given** (default) — a live stream appends flags, so a position stays valid; clients treat it as opaque.
- **Only the video call falls back to the other language** (default) — the flags call takes the `lang` that the video call returned, and gives 404 for a language with no analysis.
- **A flag is served as approved** (default) — the same fields as `GET /analyses/<id>` serves; hiding is S5.

## Out of scope

- Guest summaries and the prompts version in the video call: S4 and S7.
- Hidden flags: S5. Live flags and `live: true`: Step 3.
- The test page that reads this API: S3.
