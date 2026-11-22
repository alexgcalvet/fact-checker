# S1 Review uploads on the web

**Implements**: [RFC › Specs S1](../../RFC.md) · [ARCHITECTURE › Contracts (collector routes), External systems › Cloudflare Access](../../../../ARCHITECTURE.md)
**Approval**: person · approved 2026-11-20

## Summary

The owner reviews the analyses that testers upload in a web page instead of the command line. The page lists each pending upload with what the command line does not show: the model of each reading role, the cost, whether it is an interview or a debate, and how many flags are serious. The owner opens one to read its flags, then approves or rejects it; only the owner's Cloudflare login reaches the page.

## Acceptance

- [X] A1 · Only a valid Cloudflare Access login reaches the review page and its calls
  - **Story:** A request to the review page or to one of its calls carries the token that Cloudflare Access adds after the owner's login: it gets the page or the list. The same request with no token, an expired token, a token for another application, or a token signed by another key gets 401.
  - **Edge case:** WHEN a request to the review page carries only the owner's admin token THEN 401; WHEN the owner's helper lists `/analyses` with the admin token THEN it works as before.
  - **Test:** `tests/collector/admin-access.test.ts`
- [X] A2 · The review list shows models per role, cost, type, flags and serious flags
  - **Story:** A tester uploads a debate whose parts were read by Opus and verdicts by Sonnet, cost 0.84 $, with 12 flags of which 3 are serious; another tester uploads an interview. The owner opens the review page and sees two rows: "debate · parts opus, verdict sonnet · 0.84 $ · 12 flags · 3 serious" and the interview with its own numbers. The owner's helper gets the same fields from `/analyses`.
  - **Test:** `tests/collector/admin-list.test.ts`
- [X] A3 · The owner opens an upload, reads its flags, and approves or rejects it from the page
  - **Story:** The owner opens the debate's row and reads its 12 flags: second, type, label, quote, reason and severity. They press Approve: the debate leaves the list, and anyone who asks the collector for it gets it. Reject on the interview deletes it and serves nothing.
  - **Test:** `tests/collector/admin-review.test.ts`
- [X] A4 · A real upload approved in the page reaches another machine
  - **Story:** After the deploy, the owner opens the review page in a browser, logs in with Cloudflare, sees a real pending upload with its models, cost and serious count, opens it and approves it. A helper on another machine then downloads that analysis for the video.
  - **Test:** `review: the owner approves one real pending upload in /admin, and another machine's helper downloads it`

## Files

| Path | Change |
|------|--------|
| `src/collector/src/index.ts` | edit — Access JWT check; `/admin`, `/admin/pending`, `/admin/pending/<video_id>[/approve\|reject]`; list fields `readers`, `cost_usd`, `type`, `flags`, `serious` |
| `src/collector/web/admin/index.html` | new — the review page: list, one upload's flags, approve and reject; plain HTML and script, no build |
| `src/collector/wrangler.toml` | edit — `[assets]` from `web/`, binding `ASSETS`, `run_worker_first = ["/admin*"]` |
| `src/collector/package.json` | new — `jose`, with its lock file |
| `.github/workflows/checks.yml` | edit — `npm ci` in `src/collector` before the tests |
| `src/collector/README.md` | edit — `npm ci`; `wrangler secret put TEAM_DOMAIN` and `POLICY_AUD`; the review page and its routes |
| `tests/support/access_fake.ts` | new — a key pair, its key set and signed tokens, served to the Worker in place of the team's key URL |

## Tasks

- [X] T001 Add `jose` in `src/collector/package.json` and the `npm ci` step in `.github/workflows/checks.yml` → A1
- [X] T002 Check the Access JWT on `/admin*` and route `/admin/pending` to the existing list in `src/collector/src/index.ts`, with `tests/support/access_fake.ts` → A1
- [X] T003 Add `readers`, `cost_usd`, `type` and `serious` to the pending list in `src/collector/src/index.ts` → A2
- [X] T004 Add `/admin/pending/<video_id>` (the upload that approve would serve) and its approve and reject in `src/collector/src/index.ts` → A3
- [X] T005 Write the review page in `src/collector/web/admin/index.html` and serve it through `ASSETS` after the check, set in `src/collector/wrangler.toml` → A3
- [X] T006 Write the deploy and secret steps in `src/collector/README.md`, deploy, and approve a real upload → A4

## Requirements

- [X] FR-001 — The Worker MUST take the key URL and the issuer from its `TEAM_DOMAIN` setting, never from the token.

## Decisions

- **`type` is `debate` with two or more guests** (default) — guests are the speakers with role `guest` in `people`, else every speaker, as the helper's summary counts them.
- **A serious flag is `judge.severity == "serious"` and not a nitpick** (default) — the same rule as the extension's card title.
- **The page's calls live under `/admin/*`, checked by the JWT, not `ADMIN_TOKEN`** (default) — Access covers only `/admin*`; the browser never holds the admin token.
- **`jose` for the JWT, not WebCrypto by hand** (default) — Cloudflare's documented check; it costs a `package.json` in the collector.
- **Opening an upload shows the one that approve would serve** (default) — the best model's, newest first; the other testers' uploads of the same video stay in the count only.

## Out of scope

- Hiding single flags: S5. Marks and feedback in the page: S6 and S8.
- The CLI `shared list` printing the new fields: it keeps its line; the page is the place to read them.
- Static files of the test page: S3.
