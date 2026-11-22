# S8 Feedback on the method

**Implements**: [RFC › Specs S8, Proposal (Feedback)](../../RFC.md) · [ARCHITECTURE › Collector API (`POST /api/feedback`, `GET /feedback`, Feedback row), Security](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-20

## Summary

A viewer of the test page can now tell the author where the method itself goes wrong, not only whether one flag is fair. Under the video, the page shows the rules that the models followed; the viewer selects a few words of a rule and writes a comment, and a flag marked unfair also names the rule that produced it. Only the owner reads this feedback, in the review page, with the exact part of the method that it points to, and a daily stop keeps it cheap.

## Acceptance

- [X] A1 · A comment on a selected span of a rule reaches the owner with its anchor
  - **Story:** In a fresh Spanish browser, someone opens the test page of the invented debate, opens the part `parts` of the method under the video, selects the words "without evidence" in the rule `insinuation`, writes "una pregunta no es una acusación" and presses Comentar, then answers Yes. The owner's review page lists one comment of kind `prompt` with the version `0.1.0+5df934af8305`, the part `parts`, the rule `insinuation`, the quote "without evidence", the text and an anonymous id; the owner's token read gives the same row. Nobody else can read it.
  - **Edge case:** WHEN a request quotes words that are not in that rule, or names a version that no approved analysis names THEN the collector refuses it (400) and keeps nothing.
  - **Test:** `tests/web/try-method-comment.test.ts`
- [X] A2 · A flag marked unfair on the page names its rule for the owner
  - **Story:** After Yes, someone marks the flag at 0:45 of the invented debate unfair with the reason "el dato es correcto", and the flag at 1:15 correct. The owner's review page lists one feedback row of kind `flag` for the flag at 0:45, with the rule `false`, the version `0.1.0+5df934af8305` and the reason as its text; the correct mark adds no feedback row.
  - **Test:** `tests/web/try-unfair-rule.test.ts`
- [X] A3 · Feedback stops for the day at 20 per id and 1,000 for all ids
  - **Story:** On one UTC day, 50 web ids send 20 comments each and the collector keeps all 1,000. The next comment, from a new id, is refused, and the page that sent it says that comments are closed for today. One id's 21st comment is refused too. The next UTC day, a comment is kept again.
  - **Test:** `tests/web/try-feedback-daily-stop.test.ts`
- [X] A4 · The owner reads a real comment with its anchor in the review page
  - **Story:** After the deploy, the owner opens the test page of a real approved video, selects a span of the insinuation rule, sends a comment and reads it under Feedback in `/admin`, with its version, part, rule and quote.
  - **Test:** `review: the owner sends one comment from /try/<real id> and reads it in /admin with its anchor; curl shows /api/videos 200, /api/prompts/<unknown> 404, /try/<id> 200, /admin/pending and /admin/feedback 302, GET /feedback 401 and POST /api/feedback with a bad body 400`

## Files

| Path | Change |
|------|--------|
| `src/collector/schema.sql` | edit — table `feedback` and its indexes |
| `src/collector/src/index.ts` | edit — `POST /api/feedback` with its checks and daily stops; `GET /feedback?since=`; `GET /admin/feedback` |
| `src/collector/web/admin/index.html` | edit — a Feedback list under Marks |
| `src/extension/src/try.ts` | edit — the method under the video, the selection and comment form, the feedback of an unfair mark, the closed note |
| `src/collector/web/try/try.js` | edit — rebuilt from `try.ts` |
| `src/collector/README.md` | edit — the feedback routes, stops and deploy check |
| `PRIVACY.md` | edit — what a comment sends |

## Tasks

- [X] T001 Add table `feedback` in `src/collector/schema.sql`; check, anchor and keep feedback at `POST /api/feedback`, serve `GET /feedback` and `/admin/feedback` in `src/collector/src/index.ts` → A1, A2
- [X] T002 Show the method under the video, keep the selection, and send a comment after consent in `src/extension/src/try.ts` → A1
- [X] T003 Send a `flag` feedback row with each unfair mark in `src/extension/src/try.ts` → A2
- [X] T004 Stop feedback at 20 per id and 1,000 for all ids per UTC day in `src/collector/src/index.ts`, and show the closed note in `src/extension/src/try.ts` → A3
- [X] T005 List feedback in `src/collector/web/admin/index.html`; rebuild `src/collector/web/try/try.js`; write `src/collector/README.md` and `PRIVACY.md` → A4
- [X] T006 Apply the schema, deploy, and check the routes with curl → A4

## Decisions

- **(A) rides on the unfair mark of S6: the page sends the mark and a `flag` row with rule = the flag's label, the video's prompts version and the reason as text** (default) — no new button. Rejected: a separate "wrong rule" button.
- **The method shows as one collapsed block per part under the player, plain text; a selection inside a part is kept as the anchor until another one replaces it** (default) — typing in the comment box moves the browser's selection. Design: frontend RFC.
- **A `prompt` row needs a version that an approved analysis names, a part of that file, a rule of that part if given, and a quote found in that rule's or part's text** (default) — no anchor can point to nothing.
- **The stop counts rows of the `feedback` table: 20 per id and 1,000 for all ids per UTC day** (default) — every feedback row comes from the web; no counter table.
- **A comment uses the same consent as marks; after a stored No, the page says it sent nothing** (default) — the contract says "after consent"; the ask text now names comments.
- **`POST /api/feedback` runs in the `PublicApi` entrypoint with the `/api/*` headers** (default) — Cloudflare never caches a POST.
- **The helper's `feedback pull` does not read feedback** (default) — the RFC says "read in `/admin`"; `GET /feedback?since=` serves the owner's curl.
- **`/admin/feedback` lists the latest 200 rows, newest first** (default) — as `/admin/marks`.

## Out of scope

- Linking a flag card to its rule, and the design of the method view: frontend RFC in the brand repo.
- Turning feedback into a golden case: the owner, by hand.
- Feedback from the extension: not in the RFC row.
