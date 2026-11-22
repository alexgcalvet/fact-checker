# S0 Foundations

**Implements**: [RFC › Specs S0 and S0 checklist](../../RFC.md)
**Approval**: agent · approved 2026-11-20

## Summary

Before the web backend is built, three outside contracts must be read from their sources and one gate must work. The owner's review page gets a Cloudflare login that only the owner's email passes. The YouTube embed player and the way a Worker serves page files get written down, so the review page (S1) and the test page (S3) build on facts, not guesses.

## Acceptance

- [X] A1 · Only the owner passes the login of the review page
  - **Story:** The owner opens the collector address followed by `/admin` in a private browser window. A Cloudflare login page asks for an email. The owner's email gets a code and passes (the Worker answers 404 until S1 builds the page); any other email is refused.
  - **Edge case:** WHEN a helper sends a mark, or anyone reads an analysis or `/api/` THEN no login appears and the route answers as before.
  - **Test:** `review: the owner tries /admin with their email and another email, and /analyses with no login`
- [X] A2 · The embed research says how a page reads and moves the video time
  - **Story:** A builder opens the YouTube embed research. It names, with a link to Google's docs, the calls that give the current time and the duration, the call that seeks, the events that signal play and pause, and what the player shows for a video whose owner disabled embedding.
  - **Test:** `review: docs/research/youtube-embed.md part 1, each fact with its source`
- [X] A3 · The Cloudflare research states the Access and static assets contracts
  - **Story:** A builder opens the Cloudflare research. It says which header and token Access adds, how a Worker checks it, whether Access can cover one path of a `workers.dev` address, and how one Worker serves page files beside its own routes. Each fact links to Cloudflare's docs.
  - **Test:** `review: docs/research/cloudflare-access-and-assets.md, each fact with its source`

## Files

| Path | Change |
|------|--------|
| `docs/research/youtube-embed.md` | new — part 1: IFrame Player API (time, duration, seek, events, embed disabled) |
| `docs/research/cloudflare-access-and-assets.md` | new — Access header and check; Access on a `workers.dev` path; Workers static assets with a Worker script |
| `src/collector/README.md` | edit — a section "Protect the review page": the steps that set up Access on `/admin` |

## Tasks

- [X] T001 [P] Write part 1 from Google's IFrame Player API docs in `docs/research/youtube-embed.md` → A2
- [X] T002 [P] Write the Access and static assets contracts from Cloudflare's docs in `docs/research/cloudflare-access-and-assets.md` → A3
- [X] T003 Write the Access setup steps for `/admin` in `src/collector/README.md` → A1
- [X] T004 The owner follows the steps in the Cloudflare dashboard and checks the login in a private window → A1

## Decisions

- **Docs only, no live player test** (default) — S3 builds the page and its contract test; a spike page now would be thrown away.
- **Access on the path `/admin` only** (default) — helpers post marks and uploads with no browser; a login on the whole address would break them.

## Out of scope

- The policy on elements over an embed (overlay, cinema mode): the frontend RFC in the brand repo.
- Workers Paid and the deploy login: owner items of the S0 checklist, before the first public link.
- Setting the three contracts to `confirmed` in ARCHITECTURE: `/rfc sync` after this spec.
