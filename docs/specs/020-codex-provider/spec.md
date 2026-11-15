# S20 Codex as a provider: read with a ChatGPT subscription

**Implements**: [ARCHITECTURE › Components](../../ARCHITECTURE.md#components), [ARCHITECTURE › External systems](../../ARCHITECTURE.md#external-systems), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

Today the fact-checker only works for people who pay for Claude. This slice lets a person with a ChatGPT subscription and no Claude subscription use it: one setting makes every reading go through Codex instead of Claude Code. Since the confidence bars were tuned on Claude, Codex flags get their own bars, so a weaker or differently calibrated model does not crowd the player.

## Acceptance

- [X] A1 · One setting routes every reading through Codex
  - **Story:** The person starts the helper with `FACT_CHECK_PROVIDER=codex` and analyses an invented 30-second interview with one false figure. Every reading (part, search, verdict, judge) runs Codex, never Claude Code: the search with live web search, the others with no web search, all by the account's default model (S22: no `-m` when no model is set). The false figure shows as "Dato falso", and the usage log names the model of each reading, `codex-default`, with its tokens.
  - **Test:** `tests/acceptance/test_s20_a1_codex_provider.py`
- [X] A2 · The real Codex CLI answers as the adapter expects
  - **Story:** The person, logged in to Codex, runs the contract test. One real Codex reading returns a thread id, an answer that follows the schema and its token usage, with the same fields as the recorded fake. Without a working login it says SKIP and passes.
  - **Test:** `tests/acceptance/test_contract_codex_cli_exec.py`
- [ ] A3 · Codex on the 1.5-hour interview, beside Claude
  - **Story:** The person runs the Codex check. It analyses the 1.5-hour interview with Codex in a separate helper home and prints the precision on the person's marks (of the Codex flags that match a marked card, the share marked correct), the precision of those marks on Claude, and how many of the 9 known misses Codex catches. It exits 0 when the analysis ends done and every reading ran Codex.
  - **Test:** `check: bash tests/acceptance/s20-a3-codex-real.sh`
- [X] A4 · Codex flags meet Codex bars
  - **Story:** With Codex as the provider and no Codex bars yet, a fallacy at confidence 0.6 goes to the side panel, not on the player, though the Claude bar is 0.4. Once a Codex bars file sets the fallacy bar at 0.5, the same flag goes on the player. With Claude as the provider, the Claude bars apply as before.
  - **Test:** `tests/acceptance/test_s20_a4_bars_per_provider.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/adapters/llm_codex_cli.py` | new — the Codex adapter of the LLM port |
| `src/helper/fact_checker/server.py` | edit — pick the provider and its models; read the provider's bars |
| `src/helper/fact_checker/cli.py` | edit — `analyze`, `eval` and `judge` use the chosen provider; `eval --save` writes its bars |
| `tests/fakes/codex-cli/exec.jsonl` | new — the event stream of one reading |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Write the Codex adapter in `llm_codex_cli.py` and the event fake in `tests/fakes/codex-cli/` → A1, A2
- [X] T002 Pick the provider and its models from `FACT_CHECK_PROVIDER` in `server.py` and `cli.py` → A1
- [X] T003 Read and save the bars of the provider in use in `server.py` and `cli.py` → A4
- [X] T004 Write the check on the 1.5-hour interview with Codex → A3

## Requirements

- [X] FR-001 — `fact-checker eval --save` MUST write the bars of the provider in use to that provider's file, never to the Claude file for Codex.

## Decisions

- **Codex for every reading, the search included, with `web_search="live"`** — the docs list live search in exec; rejected: Claude Code for the search, which needs a Claude subscription.
- **`gpt-5.5` for parts, verdicts and the judge; `gpt-5.4-mini` for the search** (default) — mirrors Opus and Sonnet.
- **No dollar cost for Codex; tokens only** — a ChatGPT plan has no price per reading; rejected: an API price table that drifts.
- **No retry on a Codex limit** — a ChatGPT limit lasts hours; rejected: the 30 s and 60 s retries of Claude.
- **A provider with no bars file uses 0.8 for every type** (default) — the ARCHITECTURE default bar; precision first.
- **The command comes from `CODEX_BIN`, else `codex`** — the npm `codex` on this laptop has no binary; the desktop app bundles one.

## Out of scope

- Other agent CLIs (Gemini CLI and others): one adapter file each, later slices.
- Tuning the Codex bars on the golden dataset: the person runs `fact-checker eval --save` with Codex.
