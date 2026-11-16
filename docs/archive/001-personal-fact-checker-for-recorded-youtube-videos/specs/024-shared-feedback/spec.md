# S24 Shared feedback: testers send their marks to the owner's collector

**Implements**: [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts), [ARCHITECTURE › External systems](../../../../ARCHITECTURE.md#external-systems)
**Approval**: agent · approved 2026-11-15

## Summary

Each beta tester marks flags as correct or unfair, but today those marks stay on the tester's laptop. This slice adds a button in the side panel that sends the tester's new marks, with the flag and its quote, to a small collector that the project owner runs, so the owner can improve the detector from everyone's marks. Nothing leaves the laptop without that click; with no collector, the marks go to a file the tester can mail.

## Acceptance

- [X] A1 · The panel button sends only the marks not sent yet
  - **Story:** A tester has marked 2 flags. The side panel shows "Enviar mis marcas (2)" and the line "Se envían el aviso, la frase, tu motivo y el vídeo. Nada de tu equipo." A click sends both marks in one request to the collector at `feedback_url`, each with its video, second, type, label, quote, confidence, verdict, reason, provider and model, plus the helper version and an anonymous install id. The button then says "Enviar mis marcas (0)". The tester marks one more flag; the next click sends only that mark.
  - **Edge case:** WHEN the tester changes the verdict of a sent mark THEN it counts as unsent and goes out again.
  - **Test:** `tests/acceptance/test_s24_a1_send_marks.py`, `tests/acceptance/s24-a1-send-button.test.ts`
- [X] A2 · With no collector, the marks land in a dated file and the panel shows its path
  - **Story:** A tester with no `feedback_url` clicks "Enviar mis marcas (2)". The helper writes both marks to `~/.fact-checker/feedback-2026-11-15.json` and the panel says "Guardado en " with the full path of that file, then " — envíaselo al autor". With `feedback_url` set and the collector down, the same happens. The helper keeps answering, and the count stays 2.
  - **Test:** `tests/acceptance/test_s24_a2_saved_file.py`, `tests/acceptance/s24-a2-saved-path.test.ts`
- [X] A3 · The collector keeps valid marks and refuses bad requests
  - **Story:** The owner's collector gets 2 valid marks from one tester and stores 2 rows. The same mark sent again with another verdict replaces its row. A request with a verdict "maybe", one with 501 marks, one over 256 KB, and the 21st accepted request of one tester in one day are each refused (400, 413, 413, 429) and store nothing.
  - **Test:** `tests/acceptance/s24-a3-collector-stores.test.ts`
- [X] A4 · The owner pulls the new rows with the admin token
  - **Story:** The owner sets `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env` and runs `fact-checker feedback pull`. It prints "3 new marks" and writes them to a file in `~/.fact-checker/feedback/`. A second pull prints "0 new marks". The collector answers 401 to a read without the token or with a wrong one, and the pull then names the token and exits 1.
  - **Test:** `tests/acceptance/test_s24_a4_feedback_pull.py`, `tests/acceptance/s24-a4-collector-read.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/feedback.py` | new — unsent marks joined with their flags, send in batches, the dated file, the pull |
| `src/helper/fact_checker/server.py` | edit — `GET /feedback` (count) and `POST /feedback` (send); `readers` in a new flag file |
| `src/helper/fact_checker/cli.py` | edit — `fact-checker feedback pull` |
| `src/helper/fact_checker/config.example.toml`, `env.example` | edit — commented `feedback_url` and `FEEDBACK_ADMIN_TOKEN` |
| `src/extension/src/sw.ts`, `content.ts`, `panel.ts` | edit — the two feedback requests; the button, its line and its result in the panel |
| `src/collector/src/index.ts`, `schema.sql`, `wrangler.toml`, `tsconfig.json` | new — the Worker: `POST /marks`, `GET /marks?since=`, D1 tables |
| `src/collector/README.md`, `README.md` | new / edit — the owner's one-time deploy; "Share your marks" for testers |
| `tests/acceptance/s24_fakes.py`, `tests/fakes/collector/marks.json`, `tests/acceptance/test_contract_collector_marks.py` | new — a fake collector; the contract test, SKIP without opt-in variables |
| `.claude/mini-spec.yml` | edit — `verify` also type-checks the collector |

## Tasks

- [X] T001 Unsent marks, batches, sent record and dated file in `src/helper/fact_checker/feedback.py` → A1, A2
- [X] T002 Feedback routes and `readers` in `src/helper/fact_checker/server.py` → A1, A2
- [X] T003 [P] Requests, button, result, and a recount on the layer event `fc-marked` after each mark in `src/extension/src/sw.ts`, `content.ts`, `panel.ts` → A1, A2
- [X] T004 [P] Worker, schema, config and contract test in `src/collector/` → A3, A4
- [X] T005 Pull command in `src/helper/fact_checker/cli.py` and `feedback.py` → A4
- [X] T006 [P] Docs, examples and verify key in `README.md`, `src/collector/README.md`, the examples, `.claude/mini-spec.yml` → A4

## Decisions

- **Opt-in per click, a button with the count and one line on what goes out** (lead) — rejected: send on every mark.
- **One sent mark: video id, second, type, label, quote, confidence, verdict, reason, provider, model, helper version, install id; no name, email, path or IP** (lead).
- **Own collector: Cloudflare Worker + D1, deployed once by the owner** (lead) — rejected: a hosted form or a shared sheet.
- **Install id: a random UUID in `<helper home>/install-id`, made at the first send** (default).
- **Sent record: `<helper home>/feedback-sent.json`, the sent verdict and reason per video and flag; a changed mark is unsent again** (default).
- **Provider and model: a new flag file gets `readers`, the provider and model of each role; `parts` for most types, `verdict` for inaccuracies. An older file sends the model of the video's latest usage line of that step and a null provider** (default).
- **The helper sends 50 marks per request; the collector caps a request at 500 marks and 256 KB** (default / lead) — 50 marks of the longest fields stay under 256 KB.
- **Field limits: quote ≤ 1,000 characters (the helper cuts it), reason ≤ 500, label, provider ≤ 40, model, flag id ≤ 100; unknown fields refused** (default).
- **Hard stop: 20 accepted requests per install id per UTC day, then 429** (lead asked for N) — 1,000 marks a day per tester, far under D1's free writes.
- **A repeated mark replaces its row: unique install id + video + flag id, `INSERT … ON CONFLICT DO UPDATE` in one `batch`** (lead).
- **Any failure (no answer, HTTP error, no `feedback_url`) writes every unsent mark to `feedback-<local date>.json`; they stay unsent** (default) — the next send still reaches the collector.
- **`GET /marks?since=<iso>` returns every row received after it, no pages; the pull keeps the last `received_at` in `<helper home>/feedback/since` and writes `<UTC time>.jsonl`** (default).
- **The collector has no dependency: its own small D1 types; the tests use Node's built-in SQLite as the D1 binding** (default) — rejected: wrangler dev or Miniflare in tests.
- **Every new panel string (button, the line on what goes out, the result) lives in one exported const object of `panel.ts`, Spanish for now** (person) — S25 adds the language switch; no i18n mechanism here.
- **`wrangler.toml`** (lead) — Cloudflare recommends `wrangler.jsonc` for new projects; TOML works.

## Out of scope

- Analysing the feedback or changing prompts from it: the lead does it by hand.
- Automatic thresholds from shared marks, a public dashboard.
