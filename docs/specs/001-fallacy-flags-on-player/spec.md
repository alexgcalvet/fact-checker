# S1 Fallacy flags on the player

**Implements**: [RFC › Specs S1](../../RFC.md#specs), [ARCHITECTURE › One run](../../ARCHITECTURE.md#one-run), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: person · approved 2026-11-14

## Summary

The person opens a recorded Spanish video on YouTube and, while it plays, sees short cards on the player that name a fallacy at the second it is said, with the exact words and a reason. A helper on the laptop fetches the captions, asks Claude on the person's own subscription, and keeps the result per video, so a second viewing is instant and free. This is the first version that a person can use from end to end; contradictions and fact checks come later.

## Acceptance

- [X] A1 · Opening a video makes the helper analyse it and serve its flags
  - **Story:** The person starts the helper and asks it for a short public Spanish video (about 15 minutes). After a few minutes the helper answers with the flag file of that video: status "done", its publish date, and fallacy flags, each with a second, the exact words, one of the 8 fallacy names, a reason and a confidence.
  - **Edge case:** WHEN the same video is asked again after it is done THEN the helper serves the saved file and calls Claude zero times.
  - **Test:** `check: bash tests/acceptance/s1-a1-helper-serves-flags.sh "$S1_VIDEO_URL"`
- [X] A2 · Flags quote the exact words, at their second, from the closed list only
  - **Story:** From an invented 4-minute dialogue with 3 planted fallacies, the analysis returns flags whose words appear word for word in the captions, whose second is when those words start, and whose name is one of the 8 in the list.
  - **Edge case:** WHEN Claude names a fallacy outside the list, or quotes words that are not in the captions THEN no flag is written; an out-of-list name goes to the candidates log with its words.
  - **Test:** `tests/acceptance/test_s1_a2_flags_from_captions.py`
- [X] A3 · The analysis starts where the person is watching and runs ahead
  - **Story:** The person opens a 60-minute video at minute 50. The first part analysed is the 30 seconds from minute 50, then 2-minute parts forward to the end, then the first 50 minutes; never more than 3 parts at once. The usage log shows, for each part, how many seconds before playback it was ready.
  - **Test:** `tests/acceptance/test_s1_a3_ahead_of_playback.py`
- [X] A4 · A card shows on the player at the flag's second
  - **Story:** On a page that mimics the YouTube player, with a flag file that holds one flag at second 42 with confidence 0.9 and one at second 50 with confidence 0.6, the person plays to second 42 and sees one card with the name, the words and "90%"; no card appears for the 0.6 flag.
  - **Test:** `tests/acceptance/s1-a4-card-on-player.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/pyproject.toml` | new — package `fact_checker`, command `fact-checker serve`, pytest config |
| `src/helper/fact_checker/core/flags.py` | new — flag and flag-file types, the 8 fallacy labels |
| `src/helper/fact_checker/core/pipeline.py` | new — `analyze_chunk`: prompt with context, label and quote checks |
| `src/helper/fact_checker/core/scheduler.py` | new — `plan` from the playback second, 3 parts at once, budget guard, lead |
| `src/helper/fact_checker/adapters/youtube.py` | new — captions (`es-orig`, then `es`) and publish date through yt-dlp |
| `src/helper/fact_checker/adapters/llm_claude_cli.py` | new — `claude -p` with a JSON schema |
| `src/helper/fact_checker/store.py` | new — flag file, candidates log, usage log under `~/.fact-checker/` |
| `src/helper/fact_checker/server.py` | new — `POST /videos/<id>?from=` and `GET /videos/<id>` on 127.0.0.1, analysis in a background thread |
| `src/extension/` | new — manifest, service worker, content script, overlay, build and tests config |
| `tests/fakes/youtube/invented-dialogue.json3` | new — invented captions with the planted fallacies |
| `tests/acceptance/` | new — the four acceptance tests |
| `.claude/mini-spec.yml` | edit — `verify` key runs pytest and the extension checks |

## Tasks

- [X] T001 Create the package and the flag types with the 8 labels in `src/helper/fact_checker/core/flags.py` → A2
- [X] T002 [P] Fetch captions and publish date in `src/helper/fact_checker/adapters/youtube.py` → A1
- [X] T003 [P] Call `claude -p` with a schema and return `structured_output` in `src/helper/fact_checker/adapters/llm_claude_cli.py` → A1
- [X] T004 Build `analyze_chunk` with context, label and quote checks in `src/helper/fact_checker/core/pipeline.py` → A2
- [X] T005 Write flag files, candidates log and usage log with the lead in `src/helper/fact_checker/store.py` → A1, A2, A3
- [X] T006 Serve and cache analyses in `src/helper/fact_checker/server.py` → A1
- [X] T007 [P] Build the extension: start at page load with the playback second, polling, cards at their second in `src/extension/` → A4
- [X] T008 Set the `verify` key in `.claude/mini-spec.yml` → A2, A3, A4
- [X] T009 Plan parts from the playback second, run up to 3 at once, stop at the budget in `src/helper/fact_checker/core/scheduler.py` → A3, FR-003

## Requirements

- [X] FR-001 — The helper MUST listen on 127.0.0.1 only, and only the extension service worker calls it.
- [X] FR-002 — Captions, flag files and logs MUST stay under `~/.fact-checker/`; the repo holds only invented captions.
- [X] FR-003 — The analysis MUST stop after 60 Claude tool calls per video-hour, keep its flags, and write status `stopped` with reason `budget`.

## Decisions

- **Parts of 2 minutes after a first part of 30 seconds, one Claude tool call each, with the previous 2 minutes as context** (default) — about 30 calls per hour leaves half the budget for S3 and S4.
- **Claude Sonnet for the chunk analysis** (default) — faster and lighter on the subscription limits; Opus if S2 shows a precision gap.
- **A card stays 8 seconds after its second** (default) — long enough to read the words; it hides earlier on a seek.
- **esbuild bundles the extension** (default) — content scripts cannot import modules; one small tool beats hand-merged files.

## Out of scope

- Side panel and progress-bar marks for 0.50–0.79 flags: S5.
- Contradictions and speaker checks: S3. Fact checks: S4. The `eval` command: S2.
- Videos with no captions: S6. A token between extension and helper: RFC open question 11.
