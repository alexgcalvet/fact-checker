# S30 Ready to publish

**Implements**: [ARCHITECTURE › Security](../../../../ARCHITECTURE.md#security), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

Before the repo goes public and strangers install it, four things must hold. A shared analysis reaches other people only after the owner approves it, so nobody can plant fake flags; nothing leaves a person's machine until they say yes once; the player says its flags are signals, not verdicts, and what an analysis spends; and the repo names no real person or real video and carries a licence and a privacy notice.

## Acceptance

- [X] A1 · Only the owner's approved analyses are served
  - **Story:** A stranger uploads an analysis of video "abcdefgh" in Spanish: the collector answers 202 and serves nothing for it. The owner runs `fact-checker shared list` and sees one line: abcdefgh, es, opus, 2 flags, the uploader's install id and the date. `fact-checker shared approve abcdefgh es` makes it served to anyone; `reject` on another one deletes it and it is never served. An upload from the owner's own helper (with the admin token in its `.env`) is served at once. A row shared before this slice is pending until the owner approves it.
  - **Test:** `tests/acceptance/s30-a1-collector-review.test.ts`, `tests/acceptance/test_s30_a1_shared_review.py`
- [X] A2 · Nothing is shared before the person says yes
  - **Story:** A new tester has never answered. They click "✓ De acuerdo" on a card: a box asks "¿Compartir tus marcas y análisis con el autor para mejorar el detector? Se envían el aviso, la frase, tu motivo y el vídeo; nada de tu equipo." with "Sí, compartir", "No" and a link to the privacy notice (in English with an English browser). Until they answer, the collector gets nothing. "Sí, compartir" sends that mark and later whole analyses; "No" keeps them on the laptop. The next mark or analysis asks nothing.
  - **Edge case:** WHEN the person clicks "Analizar este vídeo" before any mark THEN the same box shows first and the analysis starts after the answer.
  - **Test:** `tests/acceptance/test_s30_a2_consent_first.py`, `tests/acceptance/s30-a2-consent-question.test.ts`
- [X] A3 · The player says "signals, not verdicts" and what an analysis spends
  - **Story:** A person with a Spanish browser sees a card with "90%" confidence, and the foot of the side panel reads "Señales automáticas, no veredictos" ("Automatic signals, not verdicts" in English). On a video not analysed yet, under "Analizar este vídeo" a line reads "Usa tu suscripción de Claude: un vídeo de 1 h gasta una parte notable de tu límite"; with Codex it names ChatGPT; with an API provider it reads "Se cobra en tu cuenta de API".
  - **Test:** `tests/acceptance/s30-a3-signals-and-spend.test.ts`, `tests/acceptance/test_s30_a3_provider.py`
- [X] A4 · The repo names no real person or real video, and has a licence and a privacy notice
  - **Story:** A stranger clones the repo. A search of the tracked files for the names and video ids of the real interviews finds nothing outside the cited public sources of the research notes. `LICENSE` is MIT, 2026 Alex G. Calvet; `PRIVACY.md` says what the collector keeps and how to ask for deletion; the README lists the third-party software that the setup downloads.
  - **Test:** `tests/acceptance/s30-a4-public-repo.sh`

## Files

| Path | Change |
|------|--------|
| `src/collector/src/index.ts`, `schema.sql`, `README.md` | edit — pending uploads, owner list/approve/reject, owner upload served at once; existing rows move to pending once |
| `src/helper/fact_checker/analyses.py`, `cli.py` | edit — the upload carries the admin token if set; `fact-checker shared list\|approve\|reject` |
| `src/helper/fact_checker/server.py`, `config.example.toml` | edit — a missing `share_marks` means not asked: nothing shared, `GET /share` answers null; `GET /provider` |
| `src/extension/src/content.ts`, `sw.ts`, `texts.ts`, `panel.ts` | edit — the consent box before the first mark or analysis; the spend line; the panel foot line |
| `src/helper/fact_checker/extension/` | edit — the rebuilt extension |
| `LICENSE`, `PRIVACY.md`, `README.md` | new, new, edit — licence; privacy notice; consent, review, spend and third-party sections |
| `src/helper/fact_checker/core/{judge,languages}.py`, `adapters/llm_claude_cli.py`, `tests/fakes/google-factcheck/claims-search.json`, `docs/` | edit — invented names and no real video ids |
| `tests/acceptance/` | new — the seven S30 tests |

## Tasks

- [X] T001 [P] Pending table, owner token on PUT, `GET /analyses`, approve and reject routes, one-time move of old rows in `src/collector/src/index.ts`, `schema.sql` → A1
- [X] T002 [P] Token on upload, list/approve/reject calls in `analyses.py`; `shared` command in `cli.py` → A1
- [X] T003 [P] Not-asked sharing, `GET /share` null, `GET /provider` in `server.py`; comment in `config.example.toml` → A2, A3
- [X] T004 Consent box, spend line, panel foot line, `provider` request in `content.ts`, `sw.ts`, `texts.ts`, `panel.ts`; rebuild → A2, A3
- [X] T005 [P] Invented names and env video ids in `src/`, `tests/fakes/`, `docs/`; the edit script for approved tests → A4
- [X] T006 [P] `LICENSE`, `PRIVACY.md`, README and collector README sections → A4

## Decisions

- **Two tables: `analyses` holds only approved rows, `pending` one row per video, language and uploader** (default) — a stranger's upload can never hide or replace a served one; rejected: a status column (SQLite has no idempotent `ADD COLUMN`).
- **`approve` serves the pending upload of the best model, newest first, and clears the other pending ones of that video and language; `reject` deletes them all** (default) — rejected: approve by install id (one more argument for a rare case).
- **Old rows move once to `pending`, guarded by a `migrations` row, so `schema.sql` stays safe to apply again** (lead: default pending).
- **The box shows at the first click on a vote or on "Analizar este vídeo" while the helper answers `share: null`; the mark or the analysis goes after the answer** — a mark given before the answer is not lost; rejected: ask at install (the person has not seen a card yet).
- **The spend line follows the provider of the parts role, asked from the helper with `GET /provider`** (default) — the parts are most of the cost; rejected: a field on `GET /share` (it would change its approved answer).
- **Person-run scripts on real interviews read the video id from `REAL_VIDEO` and drop the guest's name from their file names** (default) — the approved hashes and spec links are rewritten by the same edit script.
- **Cited public sources in `docs/research/` keep their URLs** (default) — a public fact needs its source.

## Out of scope

- Rewriting git history: the old text stays in past commits (see the report).
- An admin page for the review; the owner uses the CLI.
- Updating `docs/ARCHITECTURE.md` with `/share`, `/provider` and the review routes: `/rfc sync` after this slice.
