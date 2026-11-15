# Feedback collector

A Cloudflare Worker with a D1 database. It keeps the marks that beta testers give on the cards (their helper sends each one a moment after it is given) and the shared analyses of whole videos. Only the project owner deploys it, once.

| Request | Who | Does |
|---|---|---|
| `POST /marks` | the tester's helper | Stores up to 500 marks (256 KB) of one tester. A mark sent again replaces its row. 20 accepted requests per tester per UTC day, then 429 |
| `GET /marks?since=<ISO time>` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | Returns the rows received after that time. 401 without the token |
| `PUT /analyses/<video_id>?lang=<es\|en>` | the tester's helper, after a whole analysis | Body `{install_id, analysis}`: the stripped flag file, status `done`, at most 1 MB and 1,000 flags, http(s) source links only (else 400/413). Without the admin token: kept as pending (202), one row per video, language and tester, never served until the owner approves it. With `Authorization: Bearer <ADMIN_TOKEN>` (the owner's helper): served at once, 201 when new. Either is refused (409) when the served analysis's parts model ranks equal or higher on `RANK` in `src/index.ts` (opus > sonnet > haiku > any other); a higher one replaces it (200). 10 uploads per tester per UTC day, then 429 |
| `GET /analyses/<video_id>?lang=<es\|en>` | anyone's helper, no install id | The approved analysis, or 404 |
| `GET /analyses` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | The pending uploads: video, lang, model, flag count, install id, date. 401 without the token |
| `POST /analyses/<video_id>/approve?lang=<es\|en>` | the owner | Serves the pending upload of the best model (newest first) and clears the other pending ones of that video and language. 404 when none |
| `POST /analyses/<video_id>/reject?lang=<es\|en>` | the owner | Deletes the pending uploads of that video and language. 404 when none |
| `DELETE /analyses/<video_id>?lang=<es\|en>` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | Removes a shared analysis. 401 without the token |

Rows hold no name, email, IP address or path. See `schema.sql`.

## Deploy once

Run these steps in `src/collector/`. You need a Cloudflare account and Node.js. The free plan is enough.

1. Log in: `npx wrangler login`.
2. Create the database: `npx wrangler d1 create fact-checker-feedback`.
3. Copy the `database_id` that the command prints into `wrangler.toml`.
4. Create the tables: `npx wrangler d1 execute fact-checker-feedback --remote --file=schema.sql`.
5. Deploy the Worker: `npx wrangler deploy`. Note the `https://….workers.dev` address that it prints.
6. Make a long random token, for example with `openssl rand -hex 32`.
7. Store it as a secret: `npx wrangler secret put ADMIN_TOKEN`, then paste the token.
8. Put the address in `src/helper/fact_checker/config.example.toml` as `feedback_url`, and commit it. New testers get it with `fact-checker setup`. Give it to the current testers, for their `~/.fact-checker/config.toml`.
9. Put the token in your own `~/.fact-checker/.env` as `FEEDBACK_ADMIN_TOKEN=<token>`. Never commit it.

## Update an existing deploy

`schema.sql` only adds tables (`IF NOT EXISTS`) and runs each one-time step once (the `migrations` table), so it is safe to apply again: `npx wrangler d1 execute fact-checker-feedback --remote --file=schema.sql`, then `npx wrangler deploy`.

S30 moved the analyses served before the review into `pending`, once: run `fact-checker shared list`, then `fact-checker shared approve <video_id> <es|en>` for each one you keep.

To remove a bad shared analysis: `curl -X DELETE -H "Authorization: Bearer $FEEDBACK_ADMIN_TOKEN" "<feedback_url>/analyses/<video_id>?lang=es"`.

## Review the shared analyses

- Run `fact-checker shared list`. It prints one line per pending upload: video, language, model, flags, install id and date.
- Run `fact-checker shared approve <video_id> <es|en>` to serve it to everyone, or `fact-checker shared reject <video_id> <es|en>` to delete it.
- Both need `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env`.

## Read the marks

- Run `fact-checker feedback pull`. It writes the new rows to `~/.fact-checker/feedback/<time>.jsonl` and prints how many.
- A row is one tester's latest mark on one flag. Group by `install_id` to see one tester.

## Change and test

- Tests: `tests/acceptance/s24-a3-collector-stores.test.ts`, `s24-a4-collector-read.test.ts`, `s28-a3-collector-analyses.test.ts` and `s30-a1-collector-review.test.ts`, run by the extension's `npx vitest run`. They use Node's built-in SQLite as the D1 database.
- Type check: `cd src/extension && npx tsc -p ../collector --noEmit`.
- Contract test against the deployed collector: set `S24_COLLECTOR_URL` and `FEEDBACK_ADMIN_TOKEN`, then run `tests/acceptance/test_contract_collector_marks.py`. It stores one invented mark under a new random install id.
- After a change, run `npx wrangler deploy` again.
