# S29 Cheaper readings, nothing new for the person

**Implements**: [ARCHITECTURE › One run](../../ARCHITECTURE.md#one-run), [ARCHITECTURE › Components](../../ARCHITECTURE.md#components)
**Approval**: agent · approved 2026-11-15

## Summary

The 1.5-hour interview (1.5 hours) still costs 7.40 dollars to analyse, and almost half of it is the full reading of every part, small talk included. This slice makes the same analysis cheaper with no new account, key, setting or screen for the person: a small model first decides which parts hold anything worth the full reading, the figure search runs on the small model, and a chat API reads each part with its short window instead of resending the whole conversation.

## Acceptance

- [X] A1 · A cheap screen skips the parts with nothing to check
  - **Story:** The helper analyses an invented interview of three parts: a greeting, a false figure and a stated position. The usage log shows one `screen` reading per part, by `haiku`; the greeting is logged as skipped and gets no full reading; the two others get it. The part after the greeting still sees the greeting's words before its own.
  - **Edge case:** WHEN the screen reading fails or does not say "no" THEN the part gets the full reading.
  - **Test:** `tests/acceptance/test_s29_a1_screen_skips_small_talk.py`
- [X] A2 · The figure search runs on the cheap model
  - **Story:** With no settings file, the same interview's false figure is searched by `haiku` with web search, and its verdict is given by `opus`. With `provider = "anthropic"`, the search reading goes to `claude-haiku-5-5` with the web search tool and the verdict to `claude-opus-5-5`.
  - **Test:** `tests/acceptance/test_s29_a2_cheap_search.py`
- [X] A3 · A chat API reads each part with its window
  - **Story:** The person sets `provider = "chat"` with one model. On an invented three-part interview, each part reading sends one system message and one user message that holds the minutes before the part, the positions list and the part; a later part never resends an earlier part's messages.
  - **Test:** `tests/acceptance/test_s29_a3_chat_reads_window.py`
- [X] A4 · Doctor lists the screen, and no settings gives the cheap defaults
  - **Story:** With no settings file, `fact-checker doctor` prints "models: parts opus, verdict opus, judge opus, search haiku, screen haiku". With `provider = "anthropic"` it prints `screen claude-haiku-5-5`; with `provider = "chat"` and `parts = "llama3"` it prints "role screen: chat · llama3 · …".
  - **Test:** `tests/acceptance/test_s29_a4_doctor_screen.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/pipeline.py` | edit — the screen reading (rules, schema); a conversation part takes the unread text as CONTEXT |
| `src/helper/fact_checker/server.py` | edit — role `screen` and its defaults; search on haiku; the screen in `run_analysis`; `chat` parts read in window mode; `screen = false` |
| `src/helper/fact_checker/config.example.toml`, `README.md`, `docs/ARCHITECTURE.md` | edit — the screen role, the new defaults, the chat window |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Screen reading and unread text as CONTEXT in `core/pipeline.py`; screen role, budget, logs and `screen = false` in `server.py` → A1
- [X] T002 [P] Haiku as the default search and screen model in `server.py` → A2, A4
- [X] T003 `chat` parts read in window mode in `server.py` → A3
- [X] T004 Screen role and defaults in `config.example.toml`, `README.md`, `docs/ARCHITECTURE.md` → A4

## Requirements

- [X] FR-001 — The screen readings MUST spend a budget of their own, the size of the part budget, so the hard stop of the parts and verdicts keeps its size.

## Decisions

- **The screen sees only the part and answers `{"read", "reason"}`; it skips a part only on an explicit `read: false`** (default) — a skipped part can never be flagged, so any doubt, error or odd answer reads it; rejected: giving the screen the window (it would cost as much as it saves).
- **Each screen line in the usage log carries `read` and `reason`** (default) — a later measurement lists what was dropped without a new file.
- **A skipped part adds no positions; in a conversation its words go as CONTEXT in the next part's message** (default) — the window mode already reads them from the captions.
- **`screen = false` at the top of `config.toml` turns the screen off, for the measurement only; the example keeps it commented** (lead) — no new setting for the person.
- **A `chat` screen with no model of its own uses the parts model** (lead) — `chat` has no default model.
- **`chat` parts always read in window mode; the other providers keep `conversation`** (lead) — a chat API resends the whole history with no cache.
- **`run_analysis` screens only when given a screen LLM** (default) — tests and commands that call it directly keep their readings.

## Out of scope

- The measurement on the 1.5-hour interview of the new cost: run by the lead later.
- The approved S22, S23 and earlier tests that name `sonnet` for the search or count readings: their edits are listed in the report.
