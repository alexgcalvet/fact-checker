# S3 Try one video on a test page

**Implements**: [RFC › Specs S3](../../RFC.md) · [ARCHITECTURE › Components (Test page), Contracts (`GET /try/<video_id>`), External systems › YouTube IFrame Player API](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-20

## Summary

Anyone with the link of an approved video can watch it on a plain web page with the same flag panel that the extension shows on YouTube, without installing anything. The page plays the video in a YouTube embed, reads its flags from the public API, lights each flag as the video reaches it, and jumps the video to a flag when the person clicks it. It lets the owner try the backend in a browser and on a phone before the branded site exists.

## Acceptance

- [X] A1 · The page lights each flag of an approved video as the video plays
  - **Story:** Someone opens the test page of the invented debate in a Spanish browser. The video player loads and the panel lists its 12 flags. When the video reaches second 50, the flag at second 45 is the lit one; at second 80, the flag at second 75 is.
  - **Edge case:** WHEN the analysis exists only in Spanish and the browser is English THEN the page shows the Spanish flags with a note that names the language.
  - **Test:** `tests/web/try-flags.test.ts`
- [X] A2 · A click on a flag moves the video to that flag
  - **Story:** On the test page of the invented debate, the person clicks the flag at second 1210 in the panel. The video jumps to second 1210 and keeps playing.
  - **Test:** `tests/web/try-seek.test.ts`
- [X] A3 · The page says why it shows no flags
  - **Story:** Someone opens the test page of a video with no approved analysis: the page says that this video has no reviewed analysis yet. Someone opens the page of an approved video whose owner does not allow embedding: the page says so and links to the video on YouTube.
  - **Test:** `tests/web/try-cannot-show.test.ts`
- [X] A4 · A real approved video plays with its flags on a laptop and a phone
  - **Story:** After the deploy, the owner opens the test page of a real approved debate on a laptop and on a phone. The video plays, its flags light up at their second, and a click on a flag moves the video. Search engines are told not to index the page.
  - **Test:** `review: the owner opens /try/<id> of a real approved video on a laptop and a phone; curl shows X-Robots-Tag noindex`

## Files

| Path | Change |
|------|--------|
| `src/extension/src/try.ts` | new — the page script: reads the video id from the address, loads the video and its flags from `/api/`, creates the embed, adapts the player to the video interface of the panel, mounts the overlay and the panel |
| `src/extension/build.mjs` | edit — also bundle `src/try.ts` into `src/collector/web/try/try.js` |
| `src/collector/web/try/index.html` | new — the blank page: the player box, the script, `noindex` |
| `src/collector/web/try/try.js` | new — built from `try.ts`, committed like the extension's build |
| `src/collector/src/index.ts` | edit — `GET /try/<video_id>` serves the page with `X-Robots-Tag: noindex` and a referrer policy that keeps the origin |
| `src/collector/wrangler.toml` | edit — `/try/*` in `run_worker_first` |
| `src/extension/vitest.config.ts` | edit — run `tests/web/*.test.ts` |
| `tests/support/youtube_fake.ts` | new — a fake `YT.Player`: time, duration, state, `seekTo` calls, `onError` |
| `src/collector/README.md` | edit — the test page route and how to try a video |

## Tasks

- [X] T001 Write the fake player in `tests/support/youtube_fake.ts`, and add `tests/web/*.test.ts` to `src/extension/vitest.config.ts` → A1, A2, A3
- [X] T002 Load the video and flags from the API, adapt the player and mount the overlay and the panel in `src/extension/src/try.ts` → A1
- [X] T003 Seek the embed from the panel through the adapter in `src/extension/src/try.ts` → A2
- [X] T004 Show the no-analysis and embed-blocked messages in `src/extension/src/try.ts` → A3
- [X] T005 Write `src/collector/web/try/index.html`, bundle `try.js` in `src/extension/build.mjs`, and serve `/try/<video_id>` in `src/collector/src/index.ts` and `src/collector/wrangler.toml` → A4
- [X] T006 Write the route in `src/collector/README.md`, deploy, and check the noindex header → A4

## Decisions

- **The panel's own module, bundled for the web** (default) — `mountOverlay` and `mountPanel` run unchanged over an adapter object with `currentTime`, `duration`, `paused` and the `timeupdate` and `durationchange` events; a setter on `currentTime` calls `seekTo(t, true)`. Rejected: a second panel.
- **Language from the browser** (default) — `es*` asks for Spanish, else English, as the extension does; the API's `requested` gives the note.
- **No marks, no consent, no helper on the page** (default) — the card's mark buttons do nothing until S6; the panel gets no sharing switch.
- **The player time is polled every 250 ms** (default) — the API has no time event (`docs/research/youtube-embed.md`).
- **`try.js` is committed** (default) — the deploy uploads `web/` as it is, with no build step, like the review page.

## Out of scope

- Marks from the page and consent: S6. Feedback on the method: S8.
- Design, fullscreen with the panel, share preview: frontend RFC in the brand repo.
- The live contract test of the IFrame facts read as a summary: the A4 review on a real video checks them.
