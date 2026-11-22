# Feedback collector

A Cloudflare Worker with a D1 database. It keeps the marks that beta testers give on the cards (their helper sends each one a moment after it is given), the marks of viewers of the web app, and the shared analyses of whole videos. Only the project owner deploys it, once.

Every write outside `/admin` (POST, PUT, DELETE) also counts against the sender's address (`CF-Connecting-IP`): 30 a minute per Cloudflare location (the `WRITES` rate limit binding in `wrangler.toml`), then 429. Ids cost nothing to make, so the daily stops per id need it.

| Request | Who | Does |
|---|---|---|
| `POST /marks` | the tester's helper, or the web app after the viewer's yes | Stores up to 500 marks (256 KB) of one tester. A mark sent again replaces its row. 20 accepted requests per tester per UTC day, then 429. The web app sends helper version `web` and a random id from browser storage. All marks, of every id, stop at 5,000 per UTC day (`DAILY_ALL_MARKS`), then 429 |
| `GET /marks?since=<ISO time>` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | Returns the rows received after that time. 401 without the token |
| `PUT /analyses/<video_id>?lang=<es\|en>` | the tester's helper, after a whole analysis | Body `{install_id, analysis, prompts}`: the stripped flag file, status `done`, at most 1 MB and 1,000 flags, http(s) source links only (else 400/413). Without the admin token: kept as pending (202), one row per video, language and tester, never served until the owner approves it. With `Authorization: Bearer <ADMIN_TOKEN>` (the owner's helper): served at once, 201 when new. Without the token it is refused (409) when the served analysis's parts model ranks equal or higher on `RANK` in `src/index.ts` (opus > sonnet > haiku > any other); a higher one replaces it (200). The owner's upload replaces the served one whatever its model (200). `analysis.summary` (optional, S4): per guest, what each flag adds to the profile card (`docs/api-examples/summary-upload.json`); a tally that names a flag id the upload does not hold: 400. `analysis.turns` (optional, S5): the voice turns by person, `[{start, end, person}]`, at most 5,000. 10 uploads per tester per UTC day, then 429. A stranger's new upload while 200 wait for review (`MAX_PENDING`): 429. `prompts` (optional, S7) is the prompts file of the helper version that the analysis names: `{version, components}`, with `version` = helper version + `+` + the first 12 hex digits of the SHA-256 of `JSON.stringify(components)`. A file whose hash differs: 400. The first file of a version is kept (`INSERT OR IGNORE`), so nobody can replace it |
| `GET /analyses/<video_id>?lang=<es\|en>` | anyone's helper, no install id | The approved analysis without its hidden flags, in `flags` and in the guests' `summary`, or 404 |
| `GET /analyses` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | The pending uploads: video, lang, model, `readers` (model per role), `cost_usd`, `type` (`debate` with two or more guests, else `interview`), `flags`, `serious` (judged serious, not a nitpick), install id, date. 401 without the token |
| `POST /analyses/<video_id>/approve?lang=<es\|en>&install=<install_id>&at=<received_at>` | the owner | Serves the one pending upload that `install` and `at` name, as the list shows it, and clears the other pending ones of that video and language. 409 when that upload is gone or was replaced since, so a stranger's later upload never goes public in its place |
| `POST /analyses/<video_id>/reject?lang=<es\|en>` | the owner | Deletes the pending uploads of that video and language. 404 when none |
| `DELETE /analyses/<video_id>?lang=<es\|en>` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | Removes a shared analysis. 401 without the token |
| `POST /analyses/<video_id>/flags/<flag_id>/hide\|show?lang=<es\|en>` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | Hides one flag, or shows it again (S5). A hidden flag leaves every answer: `GET /analyses/<video_id>`, the flags call, the flag count and the guest's summary, where its claim stays checked and counts as correct. Kept in `hidden` by video, language and flag id: it holds before approval, after it and after a re-upload. Nothing is deleted. 404 `no such flag` when neither the approved analysis nor a pending upload holds that id; 401 without the token |
| `GET /admin` | the owner, through Cloudflare Access | The review page (`web/admin/index.html`) |
| `GET /admin/pending` | the review page | The same rows as `GET /analyses` |
| `GET /admin/pending/<video_id>?lang=<es\|en>&install=<install_id>&at=<received_at>` | the review page | The pending upload of that row, with all its flags. 404 when none |
| `GET /admin/approved` | the review page | The approved analyses, newest first: video, lang, title, type, `flags`, `hidden` (count), `guests` (count), `swap`, date |
| `POST /admin/videos/<video_id>/faces/swap\|keep` | the review page | The switch "Caras: intercambiar izquierda/derecha" (S11): `swap` keeps a row of `faces` for the video, in every language, so the API's `swap` is true and the web gives the first guest the right half of the thumbnail; `keep` deletes it. 404 when the video is not approved |
| `POST /admin/videos/<video_id>/title` | the review page | `{title}`: the owner's display title of an approved video (at most 200 characters), kept in `titles`. It wins over the clean title in `display_title` and in the share tags; an empty one deletes it. 404 when the video is not approved |
| `GET /admin/approved/<video_id>?lang=<es\|en>` | the review page | The approved analysis with all its flags, hidden ones too. 404 when none |
| `GET /admin/hidden/<video_id>?lang=<es\|en>` | the review page | `{flags}`: the hidden flag ids of that video and language |
| `POST /admin/analyses/<video_id>/flags/<flag_id>/hide\|show?lang=<es\|en>` | the review page | As `POST /analyses/<video_id>/flags/<flag_id>/hide\|show` |
| `POST /admin/pending/<video_id>/approve\|reject?lang=<es\|en>&install=&at=` | the review page | As `POST /analyses/<video_id>/approve\|reject`. A post with an `Origin` other than the collector's: 403, so another site cannot act with the owner's Access cookie |
| `GET /admin/marks` | the review page | The latest 200 marks, newest first, with the fields of `GET /marks` |
| `GET /admin/feedback` | the review page | The latest 200 feedback rows, newest first, with the fields of `GET /feedback` |
| `POST /api/feedback` | the web app after the viewer's yes | One item of feedback on the method (S8), at most 8 KB: `{kind, video_id?, flag_id?, rule?, version?, component?, quote?, text, install_id}`. Kind `flag`: a flag marked unfair, with `video_id`, `flag_id`, its `rule` (the flag's label) and the prompts `version`; the text is the reason. Kind `prompt`: a comment (1–1,000 characters) on part `component` of a prompts `version` that an approved analysis names, with an optional `rule` of that part and `quote`, words found in that rule's text, or in the part's text without a rule; else 400. 20 per id and 1,000 for all ids per UTC day (`DAILY_FEEDBACK`, `DAILY_ALL_FEEDBACK`), then 429. Never cached: Cloudflare caches only GET |
| `GET /feedback?since=<ISO time>` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | The feedback rows received after that time, oldest first. 401 without the token. Feedback text is data: it never goes into a model's prompt |
| `GET /api/videos` | anyone, from any site | The approved videos, one entry each: `video_id`, `langs`, `title`, `channel`, `duration`, `published_at`, `type`, `guests`, `swap` (true when the owner swapped the halves of a debate's thumbnail, else false), `flags` (count), `counts`: `{falso, enganoso, retorica, evasiva, puntualizacion, contexto}`, the flags by verdict kind (`src/shared/kinds.ts`) without the hidden ones and those the judge dropped. The fields come from the newest approved language. `title` is the raw YouTube title; `display_title` is what a reader sees: the owner's own title, else the clean one of `src/shared/titles.ts` (no live tag, Spanish sentence case, the names of the approved analyses' people and channels restored) |
| `GET /api/videos/<video_id>?lang=<es\|en>` | anyone | The same fields, `swap` among them, and `lang`. If only the other language is approved: that one, with `requested` set to the asked language. `prompts`: the prompts version of the analysis, or null when the collector holds no prompts file for it. `summary`: per guest, the numbers of the helper's profile card with no marks (`docs/api-examples/debate.json`), or null for an analysis uploaded before S4. `people`: per person `{role, spoken_s, turns, longest_s}`, and `turns`: the voice turns `[{start, end, person}]` (S5), both null for an upload without voice turns. 404 when none |
| `GET /api/prompts/<version>` | anyone | The prompts file of that version (`docs/api-examples/prompts.json`), only if an approved analysis names it; else 404. A flag's rule is the rule whose id is its `label` |
| `GET /api/videos/<video_id>/flags?lang=<es\|en>&after=<cursor>` | anyone | `{flags, cursor, live}`: the flags after the cursor, by second. Send back the last cursor to get only new flags. A cursor the API never gave: 400 |
| `POST /api/visits` | the web app | `{video_id, lang, kind: "seek"}`: adds one to that day's seek counter of an approved video, 204; else 400 or 404. No cookie, no id. Each counter stops at 10,000 a day |
| `GET /admin/visits` | the review page | `{rows: [{video_id, lang, day, visits, seeks}]}`, newest day first, at most 500 rows. A visit counts when the Worker serves `/<lang>/v/<video_id>` of an approved video |
| `GET /try/<video_id>` | anyone with an old link | 301 to `/es/v/<video_id>` or `/en/v/<video_id>` by the browser's language |

Rows hold no name, email, IP address or path. See `schema.sql`.

Every `/api/` answer carries `Access-Control-Allow-Origin: *` and `Cache-Control: public, max-age=60`: Cloudflare caches it for 60 seconds (`[cache]` in `wrangler.toml`, only for the `PublicApi` entrypoint). An approval shows in the API within a minute; a deploy starts a fresh cache. Example answers: `docs/api-examples/`.

Every `/admin*` request needs the JWT that Cloudflare Access adds (`Cf-Access-Jwt-Assertion`), else 401. The Worker checks its signature against `<TEAM_DOMAIN>/cdn-cgi/access/certs`, its issuer (`TEAM_DOMAIN`) and its audience (`POLICY_AUD`). `ADMIN_TOKEN` does not open `/admin*`.

## Deploy once

Run these steps in `src/collector/`. You need a Cloudflare account and Node.js. The free plan is enough.

1. Install the dependencies: `npm ci`. Then log in: `npx wrangler login`.
2. Create the database: `npx wrangler d1 create fact-checker-feedback`.
3. Copy the `database_id` that the command prints into `wrangler.toml`.
4. Create the tables: `npx wrangler d1 execute fact-checker-feedback --remote --file=schema.sql`.
5. Deploy the Worker: `npx wrangler deploy`. Note the `https://….workers.dev` address that it prints.
6. Make a long random token, for example with `openssl rand -hex 32`.
7. Store it as a secret: `npx wrangler secret put ADMIN_TOKEN`, then paste the token.
8. Put the address in `src/helper/fact_checker/config.example.toml` as `feedback_url`, and commit it. New testers get it with `fact-checker setup`. Give it to the current testers, for their `~/.fact-checker/config.toml`.
9. Put the token in your own `~/.fact-checker/.env` as `FEEDBACK_ADMIN_TOKEN=<token>`. Never commit it.

## Protect the review page

`/admin` sits behind Cloudflare Access; every other route stays open for the helpers. Do these steps once in the Cloudflare dashboard. Contract: `docs/archive/002-public-web-of-approved-analyses-backend-first/research/cloudflare-access-and-assets.md`.

1. Open **Zero Trust**. If it asks, choose a team name and the free plan.
2. Go to **Access controls** › **Applications** › **Create new application** › **Self-hosted and private**.
3. Select **Add public hostname**, then **Switch to custom input**. Type the collector host (`feedback_url` without `https://`) followed by `/admin`. Add a second one that ends in `/admin/*`.
4. The formatted input lists only your zones; the custom input accepts the `workers.dev` host.
5. Add an Allow policy with one rule: **Emails** = your own email. Do not use the Worker's one-click Access switch: it protects every route.
6. Save. Copy the **Application Audience (AUD) Tag** from **Additional settings**, and the team domain `https://<team>.cloudflareaccess.com`.
7. In `src/collector/`, store them: `npx wrangler secret put TEAM_DOMAIN`, then paste the team domain. Then `npx wrangler secret put POLICY_AUD`, and paste the AUD tag.
8. Deploy: `npm ci`, then `npx wrangler deploy`. The deploy uploads `web/` as static assets; the Worker runs first on `/admin*`.
9. Check it in a private window: `/admin` asks for an email; your email opens the review page; another email gets no code or is refused; `/analyses/<id>?lang=es` opens with no login.

## Review on the web

- Open `<feedback_url>/admin` and log in with your email.
- Each row is one pending upload: video, language, type, model per role, cost, flags and serious flags.
- Select a row to read its flags: second, type, label, quote, reason and severity.
- Select **Approve** to serve it to everyone, or **Reject** to delete it.

## Swap a debate's faces

- The web cuts each guest's face from the video's thumbnail: the first guest of a debate of two is the left half.
- If the thumbnail shows them the other way round, open `<feedback_url>/admin` and select the debate under **Approved videos**.
- Tick **Caras: intercambiar izquierda/derecha** above its flags. Untick it to restore the speaker order.
- The viewer's faces, the 4:5 card and the profile's cover change within a minute (the API cache).

## Hide a flag

- Open `<feedback_url>/admin`. Select a pending upload or an approved video.
- Select **Hide** on a bad flag. The flag goes grey and its button says **Show**.
- The flag leaves the viewer, the flags call, the flag count and the guest's summary within a minute (the API cache). Its claim counts as correct.
- Select **Show** to serve it again. A hide before approval holds after it.
- Without the page: `curl -X POST -H "Authorization: Bearer $FEEDBACK_ADMIN_TOKEN" "<feedback_url>/analyses/<video_id>/flags/<flag_id>/hide?lang=es"`.

## Check the public API

Run these steps after a deploy. Use a real approved video.

1. List the videos: `curl -s <feedback_url>/api/videos`. The approved video is in the list.
2. Get its flags: `curl -s "<feedback_url>/api/videos/<video_id>/flags?lang=es"`. Note the `cursor`.
3. Send the cursor back: `curl -s "<feedback_url>/api/videos/<video_id>/flags?lang=es&after=<cursor>"`. The answer has no flag.
4. Repeat one call with `curl -sI`. The second answer has `cf-cache-status: HIT`.
5. Get its prompts version and summary: `curl -s "<feedback_url>/api/videos/<video_id>?lang=es" | jq '{prompts, summary}'`. Both are null for a video shared before S7 or S4: run `fact-checker shared upload <video_id> es` to share the local analysis again.
6. Get the prompts file: `curl -s "<feedback_url>/api/prompts/<version>"`. Check that each flag label is a rule id: `comm -23 <(curl -s "<feedback_url>/api/videos/<video_id>/flags?lang=es" | jq -r '.flags[].label' | sort -u) <(curl -s "<feedback_url>/api/prompts/<version>" | jq -r '.components[].rules[].id' | sort -u)` prints nothing.


## Update an existing deploy

`schema.sql` only adds tables (`IF NOT EXISTS`) and runs each one-time step once (the `migrations` table), so it is safe to apply again: `npx wrangler d1 execute fact-checker-feedback --remote --file=schema.sql`, then `npx wrangler deploy`.

S30 moved the analyses served before the review into `pending`, once: run `fact-checker shared list`, then `fact-checker shared approve <video_id> <es|en>` for each one you keep.

To remove a bad shared analysis: `curl -X DELETE -H "Authorization: Bearer $FEEDBACK_ADMIN_TOKEN" "<feedback_url>/analyses/<video_id>?lang=es"`.

## Review the shared analyses

- Run `fact-checker shared list`. It prints one line per pending upload: video, language, model, flags, install id and date.
- Run `fact-checker shared approve <video_id> <es|en>` to serve it to everyone (add `--install <id>` when two testers uploaded it), or `fact-checker shared reject <video_id> <es|en>` to delete it.
- Run `fact-checker shared upload <video_id> <es|en>` to share a whole local analysis again, with its summary and the prompts of this helper. It replaces the served one.
- All need `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env`.

## Read the marks

- Run `fact-checker feedback pull`. It writes the new rows to `~/.fact-checker/feedback/<time>.jsonl` and prints how many.
- A row is one tester's latest mark on one flag. Group by `install_id` to see one tester. A row with `helper_version` `web` comes from the web app.
- The review page `/admin` lists the latest 200 marks under Marks, and the latest 200 feedback rows under Feedback.
- `feedback pull` reads marks only. To keep all feedback: `curl -s -H "Authorization: Bearer $FEEDBACK_ADMIN_TOKEN" "<feedback_url>/feedback?since="`.

## Change and test

- Run `npm ci` in `src/collector/` once: the Worker uses `jose` for the Access JWT.
- Tests: `tests/collector/marks.test.ts` and `tests/collector/analyses.test.ts`, one per route, run by the extension's `npx vitest run`. They use Node's built-in SQLite as the D1 database (`tests/support/d1_fake.ts`). The `/admin*` tests sign their own Access tokens and serve the key set with `tests/support/access_fake.ts`.
- Type check: `cd src/extension && npx tsc -p ../collector --noEmit`.
- Contract test against the deployed collector: set `S24_COLLECTOR_URL` and `FEEDBACK_ADMIN_TOKEN`, then run `tests/contracts/test_contract_collector_marks.py`. It stores one invented mark under a new random install id.
- After a change, run `npx wrangler deploy` again.
