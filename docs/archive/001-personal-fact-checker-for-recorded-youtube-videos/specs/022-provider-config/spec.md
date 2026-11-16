# S22 Provider config: pick the provider and the model of each role

**Implements**: [ARCHITECTURE › Components](../../../../ARCHITECTURE.md#components), [ARCHITECTURE › External systems](../../../../ARCHITECTURE.md#external-systems), [ARCHITECTURE › Hosting](../../../../ARCHITECTURE.md#hosting)
**Approval**: agent · approved 2026-11-15

## Summary

Today the fact-checker reads videos only through a Claude or a ChatGPT subscription, with fixed models. This slice adds a small settings file in the helper folder that picks the provider and the model of each step, and two new providers that bill an API key: Anthropic, and any service that speaks the OpenAI Responses API (OpenAI itself, or xAI Grok through its address). So other people can use the tool with the key they have, and a cheap model can read the parts while an expensive one gives the verdicts.

## Acceptance

- [X] A1 · The settings file picks the provider and a model per step
  - **Story:** The person writes `parts = "sonnet"` and `verdict = "opus"` under `[models]` in the settings file and analyses an invented interview with one false figure. The usage log shows each part read by `sonnet`, each verdict by `opus`, the search by `sonnet` and the judge by `opus`. With no settings file, the same video shows today's models: `opus` for parts, verdicts and judge, `sonnet` for the search.
  - **Edge case:** WHEN the file says `provider = "codex"` and `FACT_CHECK_PROVIDER=claude` is set THEN every reading runs Claude Code.
  - **Test:** `tests/acceptance/test_s22_a1_models_per_role.py`
- [X] A2 · The Anthropic API reads a video like Claude Code does
  - **Story:** The person sets `provider = "anthropic"` and puts `ANTHROPIC_API_KEY` in the helper's `.env`. An invented two-part interview with one false figure gives the same flags as with Claude Code. The search reading carries the web search tool and no other reading does. The second part continues the first part's conversation. Each usage line has its dollar cost, such as 0.0246 for an Opus reading with 1,000 new, 2,000 cache-written, 3,000 cached and 500 output tokens, and the flag file sums them.
  - **Test:** `tests/acceptance/test_s22_a2_anthropic_api.py`
- [X] A3 · An OpenAI-compatible API set by its address reads a video
  - **Story:** The person sets `provider = "openai"`, `base_url = "https://api.x.ai/v1"`, `key_env = "XAI_API_KEY"` and the Grok models in the settings file. The same invented interview gives the same flags. Each reading sends the key of `XAI_API_KEY` to that address, asks for JSON by the schema, the search adds web search, and the second part continues the first by its response id. A Grok model has no price in the table, so its usage lines show a null cost.
  - **Test:** `tests/acceptance/test_s22_a3_openai_compatible.py`
- [X] A4 · Doctor names the provider, the models and a missing key
  - **Story:** The person sets `provider = "anthropic"` and `parts = "claude-sonnet-5-5"`, with no API key, and runs `fact-checker doctor`. It prints "provider: anthropic", the model of each step ("parts claude-sonnet-5-5, verdict claude-opus-5-5, …"), and "ANTHROPIC_API_KEY: missing" with its fix, never a key value, and exits 1. It does not ask for Claude Code.
  - **Edge case:** WHEN the provider is `codex` and no model is set THEN the models line says "account default" for each step, and a line says "Run `codex debug models` to see the models your plan allows."
  - **Test:** `tests/acceptance/test_s22_a4_doctor_provider.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/server.py` | edit — read `config.toml`; four roles per provider; build the adapter of the provider; a verdict LLM apart from the part LLM; a null cost adds nothing |
| `src/helper/fact_checker/core/scheduler.py` | edit — a second LLM can spend the same budget |
| `src/helper/fact_checker/cli.py` | edit — the commands use the new roles and the bars of the home's provider |
| `src/helper/fact_checker/core/prices.py` | new — dollar prices per model and the cost of one reading |
| `src/helper/fact_checker/adapters/llm_anthropic_api.py` | new — the Messages API adapter of the LLM port |
| `src/helper/fact_checker/adapters/llm_openai_api.py` | new — the Responses API adapter of the LLM port |
| `src/helper/fact_checker/adapters/llm_codex_cli.py` | edit — no `-m` when the role has no model; log `codex-default` |
| `tests/acceptance/test_s20_a1_codex_provider.py`, `test_contract_codex_cli_exec.py`, `s20-a3-codex-real.sh` | edit — no hard-coded GPT model; re-approved, `docs/specs/020-codex-provider/approved.sha256` rehashed |
| `src/helper/fact_checker/install.py` | edit — doctor and setup check the provider's tool or key and print the models |
| `tests/fakes/anthropic-api/messages.json`, `tests/fakes/openai-api/responses.json` | new — docs-built answers |
| `tests/acceptance/test_contract_anthropic_messages.py`, `test_contract_openai_responses.py` | new — contract tests, SKIP without a key |
| `README.md` | edit — "Choose a provider" section |

## Tasks

- [X] T001 Read `config.toml`, four roles, the verdict LLM and a shared budget in `src/helper/fact_checker/server.py`, `core/scheduler.py` and `cli.py` → A1
- [X] T006 Codex with no model in `adapters/llm_codex_cli.py` and the S20 tests → A1
- [X] T002 [P] Messages API adapter and price table in `src/helper/fact_checker/adapters/llm_anthropic_api.py` and `core/prices.py`, with its fake and contract test → A2
- [X] T003 Responses API adapter in `src/helper/fact_checker/adapters/llm_openai_api.py`, with its fake and contract test → A3
- [X] T004 Provider, models and key checks in `src/helper/fact_checker/install.py` → A4
- [X] T005 [P] "Choose a provider" section in `README.md` → A4

## Decisions

- **Four roles `parts`, `verdict`, `judge`, `search` replace `main` and `light`** (lead) — a cheap part model with an expensive verdict model; rejected: two tiers.
- **The settings file is `<helper home>/config.toml`, read with `tomllib`; `FACT_CHECK_PROVIDER` still overrides `provider`** (lead) — no new dependency; existing tests set the variable.
- **Both API adapters use plain HTTPS from the standard library, not the vendor SDKs** (lead) — the helper has no dependency today and the tests run without installing it; rejected: `anthropic` and `openai` packages.
- **`[anthropic]` takes `base_url` and `key_env` like `[openai]`** (default) — one code path, and the tests point it at a local fake.
- **Default models: `claude-opus-5-5` ×3 and `claude-sonnet-5-5`; `gpt-6-astra` ×3 and `gpt-6-luna`** (lead; OpenAI from its models page, 2026-11-15) — the flagship and the cheap model of each.
- **Codex has no default model: a role with no model passes no `-m`, and its usage lines say `codex-default`** (lead, 2026-11-15) — Codex 0.169.0 on a ChatGPT account rejects `gpt-5.5` and `gpt-5.4-mini`, and each plan allows other models; rejected: a fixed GPT pair.
- **Effort medium on both APIs; Anthropic web search `web_search_20260209` with at most 5 searches** (default) — matches the CLIs' medium effort and the docs' 1–3 searches per fact.
- **The parts and verdicts share one budget; the eval and `analyze` use the `search` model as they used `light`** (default) — the hard stop counts every call as before.
- **A model with no price logs a null cost; the flag file sums the known costs** (default) — no guessed price; rejected: 0, which reads as free.
- **No refusal fallback model** (default) — a refusal stops that reading with its reason; a fallback would bill another model.

## Out of scope

- The cost experiment with cheaper part models: the next slice, run by the lead.
- Gemini CLI and Windows: later slices.
- Bars tuned per model: S20's `thresholds.<provider>.json` rule stays.
