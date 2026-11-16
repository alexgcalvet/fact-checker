# S28 Shared analyses

**Implements**: [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts), [ARCHITECTURE › External systems](../../../../ARCHITECTURE.md#external-systems)
**Approval**: agent · approved 2026-11-15

## Summary

Today each person pays the analysis of a video again: about 8 dollars for an hour and a half. After this slice, the first person who analyses a whole video shares its flags through the author's collector, and everyone who opens that video later in the same language sees the flags at once and for free. Only the flags travel, never the transcript, the person's marks or anything about their machine, and the one sharing switch in ⚙ turns the upload off.

## Acceptance

- [X] A1 · A whole analysis uploads its flags; a partial one does not
  - **Story:** A tester with sharing on clicks "Analizar este vídeo" at 0:00 on an invented 23-second interview. When the analysis ends, the collector gets one upload for that video and language "es": the flags, the judge's verdicts, the readers (claude, opus), `lang`, `spoken`, the cost and the helper version, and no mark, stop reason or other field. The tester starts another video at 0:15: its analysis ends with the first 15 seconds unread, and nothing is uploaded.
  - **Test:** `tests/acceptance/test_s28_a1_whole_analysis_uploads.py`
- [X] A2 · A second viewer gets the shared flags at once and for free
  - **Story:** The collector holds a Spanish analysis of a video with 2 flags. A second tester with a Spanish browser opens that video: the 2 flags show at once, with no LLM reading, no "Analizar este vídeo" button and the note "Análisis compartido · gratis" ("Shared analysis · free" in English); the helper keeps the file with `"source": "shared"`. A tester with an English browser opens the same video, gets no shared flags and sees "Analyze this video".
  - **Test:** `tests/acceptance/test_s28_a2_shared_flags_at_once.py`, `tests/acceptance/s28-a2-shared-note.test.ts`
- [X] A3 · The collector keeps the first whole analysis and guards it
  - **Story:** The collector stores a first upload of a video in Spanish (201) and serves it to anyone. A later upload read by Sonnet is refused (409) and the Opus one stays; an Opus upload over a Sonnet one replaces it (200). An unfinished analysis, a source link that is not http(s), an unknown field (400), a body over 1 MB or with over 1,000 flags (413), and the 11th accepted upload of one tester in a UTC day (429) store nothing. The owner deletes the row with the admin token (200); a delete without it gets 401.
  - **Test:** `tests/acceptance/s28-a3-collector-analyses.test.ts`
- [X] A4 · With sharing off nothing is uploaded, and downloading still works
  - **Story:** A tester unticks "Compartir mis marcas y análisis" in ⚙ and analyses a whole video: the collector gets no upload. The same tester opens a video that the collector holds in Spanish and sees its flags at once.
  - **Test:** `tests/acceptance/test_s28_a4_sharing_off.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/analyses.py` | new — strip a flag file, upload it, download one |
| `src/helper/fact_checker/server.py` | edit — `run_analysis` says if every caption second was read; upload after a whole analysis; download on `GET /videos/<id>?lang=` with no local file |
| `src/collector/src/index.ts`, `schema.sql`, `README.md` | edit — `PUT`/`GET`/`DELETE /analyses/<id>?lang=`; the `analyses` and `uploads` tables |
| `src/extension/src/content.ts`, `sw.ts`, `texts.ts`, `flags.ts` | edit — `lang` on the poll; the shared note; the toggle text |
| `tests/extension/poll-playback.test.ts` | edit — the poll also carries `lang` |
| `src/helper/fact_checker/extension/`, `README.md`, `docs/ARCHITECTURE.md` | edit — the rebuilt extension; "Shared analyses"; the contracts |
| `tests/acceptance/` | new — the five tests and `s28_fakes.py` |

## Tasks

- [X] T001 [P] Routes, checks, rank list, hard stops and tables in `src/collector/src/index.ts`, `schema.sql` → A3
- [X] T002 [P] Strip, upload and download in `src/helper/fact_checker/analyses.py` → A1, A2
- [X] T003 Whole-video check in `run_analysis`, upload in `Helper._run`, download in `do_GET` of `server.py` → A1, A2, A4
- [X] T004 [P] `lang` on the poll, the shared note and the toggle text in `content.ts`, `sw.ts`, `texts.ts`, `flags.ts`, `poll-playback.test.ts` → A2, A4
- [X] T005 Rebuild the extension; update `README.md`, `src/collector/README.md`, `docs/ARCHITECTURE.md` → A2, A3

## Requirements

- [X] FR-001 — A shared analysis MUST hold only `video_id, lang, spoken, status, published_at, title, channel, duration, speakers, readers, cost_usd, analysed_until, helper_version, flags`: no transcript, mark, stop reason or path.
- [X] FR-002 — The download MUST send no install id and wait at most 5 seconds; the upload waits at most 15.

## Decisions

- **D1, not R2: one row per video and language, the file as TEXT** — D1 allows 2,000,000 bytes per row ([D1 limits](https://developers.cloudflare.com/d1/platform/limits/)); the largest real flag file is 158 KB for 184 flags (1.5 h), so a 1 MB / 1,000-flag cap leaves 6× room and fits a row; rejected: R2 or gzip (a second binding or a codec for no need).
- **"Whole" means status done and every caption second inside a part that was read** (default) — the flag file gets no new field; `run_analysis` returns it.
- **Rank of the parts model: a name holding `opus` > `sonnet` > `haiku` > any other; replace only when strictly higher** (default) — the list lives in the Worker; an equal rank keeps the first.
- **Hard stop: 10 accepted uploads per install id per UTC day, in its own `uploads` table** (default) — far over what one person analyses.
- **The collector refuses a source link that is not `http(s)://`, a body whose video or language differs from the address, a flag confidence outside 0–1, and an install id that is not a UUID; other flag fields pass within the size cap** (default) — a shared file becomes links inside the YouTube page.
- **The switch keeps the key `share_marks`, no migration; its text becomes "Compartir mis marcas y análisis" / "Share my marks and analyses"; the foot lines stay** (default).
- **The extension sends `lang` with every poll; the helper downloads only with `lang`, no local file and a `feedback_url`** (default) — a viewer whose language has no shared file gets the analyse button, even if the other language exists.
- **A shared file is never uploaded again** (default) — no analysis runs for it.

## Out of scope

- Translating a shared analysis, merging partial analyses of several people, a public site of analyses.
- Changing the approved S27 A3 test for the new toggle text: the lead applies the listed edit.
