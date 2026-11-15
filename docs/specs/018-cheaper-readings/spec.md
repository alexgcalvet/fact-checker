# S18 Cheaper readings

**Implements**: [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts), [ARCHITECTURE › One run](../../ARCHITECTURE.md#one-run), [ARCHITECTURE › Decisions](../../ARCHITECTURE.md#decisions)
**Approval**: agent · approved 2026-11-15

## Summary

The 1.5-hour interview still costs 13 dollars to analyse. Two thirds of each part's cost is writing its ten minutes of context into a cache that keeps it for an hour and is almost never read again. This slice makes every reading cheaper (a five-minute cache, less thinking, a search that reads results instead of whole pages). It tries two ways to give a part its context, a short window or one long cached conversation, and keeps the one that costs less and catches more. It also analyses only what the person is about to watch, so a closed tab or an abandoned video stops spending.

## Acceptance

- [X] A1 · Every reading uses the five-minute cache and medium effort
  - **Story:** The helper analyses an invented video with a fake Claude Code that records how it is called. Every reading (part, search, verdict, judge) asks for medium effort and the five-minute cache, and the search reading may use web search but not open pages.
  - **Test:** `tests/acceptance/test_s18_a1_lean_readings.py`
- [X] A2 · A part gets its context as a short window or as one long conversation
  - **Story:** The helper analyses an invented 20-minute interview twice. With the short window, each part reading holds the 3 minutes before it and the list of earlier positions. With the long conversation, the parts are read in order in one Claude Code session that each reading resumes, and each reading sends only its own 2 minutes; a contradiction between minute 1 and minute 18 is flagged in both.
  - **Test:** `tests/acceptance/test_s18_a2_context_modes.py`
- [X] A3 · The analysis follows what the person watches
  - **Story:** On an invented 60-minute video, the person starts at 10:00. The helper analyses from 10:00 up to 10 minutes ahead of the playback second it last heard from the extension, and goes further as playback moves. When the extension stops asking for a minute (the tab closed), the analysis pauses; when it asks again, it goes on. The parts behind the start second are analysed only if the person goes back to them.
  - **Edge case:** WHEN the person jumps from 15:00 to 45:00 THEN the next parts start at 45:00, and 25:00–45:00 stays unanalysed until watched.
  - **Test:** `tests/acceptance/test_s18_a3_follow_viewer.py`
- [ ] A4 · The cheaper context mode wins on the 1.5-hour interview
  - **Story:** The person runs the comparison check. It analyses the 1.5-hour interview from the start, once per context mode, each in a separate helper home, and prints per mode the cost, the high-importance misses caught and the share of flags the judge drops. It exits 0 when the cheaper mode costs at most 6 dollars, catches at least 4 of the 9 misses and the judge drops at most 43 %; it prints which mode won.
  - **Test:** `check: bash tests/acceptance/s18-a4-context-ab.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/adapters/llm_claude_cli.py` | edit — five-minute cache, `--effort medium`, a resumable session |
| `src/helper/fact_checker/core/factcheck.py` | edit — search with results only, at most 2 searches per figure |
| `src/helper/fact_checker/core/scheduler.py`, `pipeline.py` | edit — the two context modes; plan parts up to the playback horizon |
| `src/helper/fact_checker/server.py` | edit — the playback second from the extension; pause and resume |
| `src/extension/src/content.ts`, `sw.ts` | edit — send the playback second with each poll |
| `docs/ARCHITECTURE.md` | edit — One run, the poll request, the context mode |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 [P] Five-minute cache and medium effort in `llm_claude_cli.py`; results-only search, 2 searches per figure in `factcheck.py` → A1
- [X] T002 Add the short-window and long-conversation context modes in `pipeline.py`, `scheduler.py`, `llm_claude_cli.py` → A2
- [X] T003 Send the playback second with each poll and analyse up to 10 minutes ahead, pausing after a minute of silence, in `content.ts`, `sw.ts`, `server.py`, `scheduler.py`; update `docs/ARCHITECTURE.md` → A3
- [ ] T004 Write the A/B check and keep the winning mode as the default → A4

## Requirements

- [X] FR-001 — The analysis MUST plan no part that starts more than 10 minutes after the last playback second heard, and MUST pause after 60 seconds with no poll.
  - WHEN an analysis starts without the extension (from the command line or a check, so no playback second is ever heard) THEN it reads the whole video, as before this slice.
- [X] FR-002 — A long-conversation session MUST start a new session when its context passes 150k tokens, carrying the positions list.

## Decisions

- **Both context modes are built and measured; the loser is removed in the next slice** (person) — the A/B decides; rejected: picking one on estimates.
- **The playback second rides on the existing poll** (default) — no new request; rejected: a separate heartbeat.
- **A jump forward leaves the skipped stretch unanalysed** (default) — spend follows watching.
- **The five-minute cache is asked for through Claude Code's own setting** (default) — the builder confirms the name of that setting in the Claude Code docs before using it.

## Out of scope

- The Batch API and a cache shared between people: Phase 2.
- A cheaper model for the part pass.
