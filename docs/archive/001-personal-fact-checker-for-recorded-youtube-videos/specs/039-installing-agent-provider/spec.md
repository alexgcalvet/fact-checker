# S39 The installing agent reads

**Implements**: [ARCHITECTURE · Hosting (Install)](../../../../ARCHITECTURE.md#hosting), [Components · Install, CLI](../../../../ARCHITECTURE.md#components)
**Approval**: agent · approved 2026-11-15

## Summary

A person who installed from Codex got Claude as the reader, because setup picks Claude whenever it is logged in, and the helper could not find the Codex that ships inside the ChatGPT app. After this slice, the agent that installs tells setup which subscription to read with, setup finds Codex inside the ChatGPT app, and one command switches the reader later with no file to edit.

## Acceptance

- [X] A1 · Setup reads with the provider it is given
  - **Story:** On a Mac where Claude and Codex are both logged in, the agent runs `fact-checker setup --provider codex`. The settings file says `provider = "codex"`, the other lines of an existing settings file stay as they were, and doctor's provider line says `codex`. With Codex not logged in, setup stops with "codex: not logged in · fix: codex login" and changes nothing.
  - **Test:** `test_s39_a1_setup_provider.py`
- [X] A2 · Setup finds the Codex of the ChatGPT app
  - **Story:** `codex` is not on the PATH, but the ChatGPT app holds it at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`. The agent runs `fact-checker setup --provider codex`. Doctor says "codex: logged in", and the login helper's PATH holds that folder, so its readings find Codex.
  - **Test:** `test_s39_a2_codex_in_chatgpt_app.py`
- [X] A3 · One command switches the reader
  - **Story:** The person's agent runs `fact-checker provider codex`. The settings file now says `codex`, the login helper restarts, and the analyse button's spend line names Codex. `fact-checker provider` alone prints the provider in use.
  - **Test:** `test_s39_a3_provider_command.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/install.py` | edit — `setup(provider=…)` sets the provider line; agent CLIs found on PATH, then in the ChatGPT app; the found folder joins the login helper's PATH; `set_provider` |
| `src/helper/fact_checker/cli.py` | edit — `setup --provider claude\|codex`; `provider [claude\|codex]` |
| `src/helper/fact_checker/adapters/llm_codex_cli.py` | edit — a reading finds Codex on PATH, then in the ChatGPT app, so `provider codex` works with any login PATH |
| `install.sh` | edit — passes its arguments to `setup` |
| `INSTALL-AGENT.md` | edit — the agent runs setup with `--provider` of itself: Codex → `codex`, Claude → `claude` |
| `docs/ARCHITECTURE.md`, `docs/RFC.md` | edit — Install row, S39 row |

## Tasks

- [X] T001 `setup --provider`, the provider line written into an existing settings file in `install.py`, `cli.py` → A1
- [X] T002 Codex found in the ChatGPT app and its folder on the login helper's PATH in `install.py` → A2
- [X] T003 `fact-checker provider` reads or sets the provider and restarts the login helper in `install.py`, `cli.py` → A3
- [X] T004 [P] `--provider` of the installing agent in `INSTALL-AGENT.md`, passed through by `install.sh` → FR-001
- [X] T005 [P] Install row and S39 row in `docs/ARCHITECTURE.md` and `docs/RFC.md` → A3

## Requirements

- [X] FR-001 — `INSTALL-AGENT.md` MUST tell the agent to run setup with `--provider codex` when the agent is Codex and `--provider claude` when it is Claude, and to switch later with `fact-checker provider`.

## Decisions

- **The agent names itself; setup does not guess from environment variables** — the guide is the one place that knows who installs; beat reading `CODEX_*` or `CLAUDECODE` variables, which change between versions.
- **Only the ChatGPT app's fixed path** (default) — the Claude app keeps its CLI under a versioned folder that moves on each update; Claude's guide installs the standalone `claude`.
- **Without `--provider`, setup keeps today's choice** (default) — Claude first, then Codex; an existing settings file stays byte for byte.

## Out of scope

- A provider switch in the extension's ⚙ settings.
- The Codex app outside ChatGPT, and Windows.
