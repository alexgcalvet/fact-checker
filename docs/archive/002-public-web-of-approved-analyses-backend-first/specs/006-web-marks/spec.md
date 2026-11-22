# S6 Marks from the web

**Implements**: [RFC › Specs S6](../../RFC.md) · [ARCHITECTURE › Components (Test page, Collector), Collector API (`POST /marks`), Security (web id)](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-20

## Summary

A viewer of the test page can say whether a flag is fair, as a tester does in the extension, with no install and no account. The page asks once before anything leaves the browser, then sends each mark under a random anonymous id kept in that browser. The owner reads these marks next to the testers' marks, and a daily stop for all web viewers keeps the collector cheap even if someone makes many ids.

## Acceptance

- [X] A1 · Nothing leaves the page before the viewer says yes, and the page asks once
  - **Story:** Someone opens the test page of the invented debate in a Spanish browser and presses ✓ on a flag card. A box asks whether to share their marks with the author, with a privacy link; nothing is sent yet. They answer No: the card keeps their mark and nothing is sent. A second mark, and a mark after a reload, ask nothing and send nothing.
  - **Test:** `tests/web/try-consent.test.ts`
- [X] A2 · A mark given on the page reaches the owner under one anonymous web id
  - **Story:** In a fresh browser, someone marks the flag at second 45 of the invented debate unfair with the reason "el dato es correcto" and answers Yes. After a reload, they mark the flag at second 75 correct with no question. The owner's review page lists both marks with source `web` and the same anonymous id, and the owner's read that `feedback pull` uses returns both rows with helper version `web`.
  - **Test:** `tests/web/try-marks.test.ts`
- [X] A3 · Web marks stop for the day at 2,000 for all web ids
  - **Story:** On one UTC day, 100 web ids give 2,000 marks and the collector keeps all of them. The next web mark is refused, and the page that sent it says that marks are closed for today; a tester's helper mark is still kept. The next UTC day, a web mark is kept again.
  - **Test:** `tests/web/try-marks-daily-stop.test.ts`
- [X] A4 · The owner sees a real web mark in the review page and in feedback pull
  - **Story:** After the deploy, the owner opens the test page of a real approved video, answers Yes and marks one flag. The mark shows in the Marks list of `/admin` and in the file that `fact-checker feedback pull` writes, with helper version `web`.
  - **Test:** `review: the owner gives one mark on /try/<real id>, then reads it in /admin and in fact-checker feedback pull; curl shows /api/videos 200, /try/<id> noindex, /admin/pending and /admin/marks 302`

## Files

| Path | Change |
|------|--------|
| `src/extension/src/try.ts` | edit — the mark buttons on the cards, the consent box, the web id and the answer in browser storage, `POST /marks`, the closed-for-today note |
| `src/collector/web/try/try.js` | edit — rebuilt from `try.ts` |
| `src/collector/src/index.ts` | edit — the daily stop of web marks in `store()`; `GET /admin/marks` behind Access |
| `src/collector/web/admin/index.html` | edit — a Marks list under the pending uploads |
| `tests/support/api_fakes.ts` | edit — the collector fake also answers a POST, as the page's `fetch` |
| `src/collector/README.md` | edit — the web marks, the stop and `/admin/marks` |
| `PRIVACY.md` | edit — what the test page sends, and its anonymous id |

## Tasks

- [X] T001 Let the collector fake answer any request in `tests/support/api_fakes.ts` → A1, A2, A3
- [X] T002 Ask once, keep the answer and the web id in browser storage, and send each mark after yes in `src/extension/src/try.ts` → A1, A2
- [X] T003 Serve the latest marks at `/admin/marks` in `src/collector/src/index.ts`, and list them in `src/collector/web/admin/index.html` → A2
- [X] T004 Stop web marks at 2,000 per UTC day in `src/collector/src/index.ts`, and show the closed note in `src/extension/src/try.ts` → A3
- [X] T005 Rebuild `src/collector/web/try/try.js`, and write `src/collector/README.md` and `PRIVACY.md` → A4
- [X] T006 Deploy, and check `/api/videos`, `/try/<id>` and `/admin/pending` with curl → A4

## Decisions

- **A web mark is one whose helper version is `web`** (default) — the contract names it so; a client that claims another version still meets the stop of 20 requests per id.
- **The stop counts marks, in the `requests` table under the id `web`** (default) — no schema change; `web` never matches an install id. Rejected: a new table.
- **The consent box sits on the player, with texts of the page, not the extension's** (default) — the page sends no analysis, so the extension's text would promise too much.
- **Storage keys `fc-web-id` and `fc-share` in `localStorage`; in memory when storage fails** (default) — the page then asks again after a reload.
- **Provider and model are null on a web mark; the reason is cut to 500 characters** (default) — the public API serves no readers per flag.
- **`/admin/marks` lists the latest 200 marks, newest first** (default) — the owner reads them; `feedback pull` keeps the full history.

## Out of scope

- Feedback on the method and on a rule: S8.
- A switch to turn sharing off later on the page: frontend RFC in the brand repo.
