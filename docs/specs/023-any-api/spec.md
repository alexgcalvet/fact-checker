# S23 Any API: any chat API reads a video, and each step can use its own provider

**Implements**: [ARCHITECTURE › Components](../../ARCHITECTURE.md#components), [ARCHITECTURE › External systems](../../ARCHITECTURE.md#external-systems)
**Approval**: agent · approved 2026-11-15

## Summary

Today the fact-checker reads videos only through Claude, ChatGPT, the Anthropic API or an API that speaks the OpenAI Responses format. This slice adds any service that speaks the common chat format, such as Hugging Face, OpenRouter, Groq, Together, DeepSeek, Mistral or a local Ollama or LM Studio, and lets each step use its own provider. A model with no web search of its own checks figures by reading the results of a search service, so a cheap open model can do the whole job.

## Acceptance

- [X] A1 · A chat API reads a video like Claude Code does
  - **Story:** The person sets `provider = "chat"`, a `base_url`, `key_env = "HF_TOKEN"` and a model in the settings file, and puts the search service key in the helper's `.env`. An invented two-part interview with one false figure gives the one "Dato falso" flag that Claude Code gives. Each reading sends the key of `HF_TOKEN` to `<base_url>/chat/completions` and asks for JSON by the schema. The second part sends the first part's messages again. A model with no price shows a null cost.
  - **Test:** `tests/acceptance/test_s23_a1_chat_api.py`
- [X] A2 · A server without JSON schema still works, and a broken answer fails cleanly
  - **Story:** The person points `provider = "chat"` at a local server that rejects the JSON schema format with HTTP 400. The same interview still gives the "Dato falso" flag: each reading asks for a plain JSON object and puts the schema in the rules. When that server then answers text that is not JSON by the schema, the video stops with a reason that says so, and the helper keeps running.
  - **Edge case:** WHEN the base URL is `http://localhost:…` and no key is set THEN the readings run with no key.
  - **Test:** `tests/acceptance/test_s23_a2_json_object_fallback.py`
- [X] A3 · Mixed providers per step, and a search service for a model with no web search
  - **Story:** The person keeps `provider = "anthropic"` and adds a `[roles.parts]` and a `[roles.search]` table on a chat API. The parts are read on the chat API, the verdicts and the judge on Anthropic. The search sends the claim's queries to the search service, the chat model reads its results, and the card says "Dato falso" with the result's source and date. Without the search service key, the video finishes with no fact-check, and the usage log names the missing key.
  - **Test:** `tests/acceptance/test_s23_a3_roles_and_search_api.py`
- [X] A4 · Doctor lists each step's provider and every missing key
  - **Story:** With the A3 settings and no keys, the person runs `fact-checker doctor`. It prints one line per step, such as "role parts: chat · some-model · https://router.huggingface.co/v1", then "HF_TOKEN: missing", "ANTHROPIC_API_KEY: missing" and "TAVILY_API_KEY: missing", each with its fix and never a key value, and exits 1.
  - **Test:** `tests/acceptance/test_s23_a4_doctor_roles.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/adapters/llm_chat_api.py` | new — the Chat Completions adapter of the LLM port, with the json_object fallback and its own schema check |
| `src/helper/fact_checker/adapters/search_tavily.py` | new — the Tavily search adapter: titles, URLs, snippets, dates |
| `src/helper/fact_checker/server.py` | edit — `[roles.<role>]` tables; the `chat` provider; the search service for a search role with no web search; the skipped fact-check |
| `src/helper/fact_checker/core/factcheck.py` | edit — the search reading reads given results instead of searching |
| `src/helper/fact_checker/install.py` | edit — doctor prints each role and checks each key, the search key included |
| `tests/fakes/chat-api/completion.json`, `tests/fakes/tavily/search.json` | new — docs-built answers |
| `tests/acceptance/test_contract_chat_completions.py`, `test_contract_tavily_search.py` | new — contract tests, SKIP without opt-in variables |
| `README.md` | edit — "Any chat API" and "One provider per step" in "Choose a provider" |
| `docs/ARCHITECTURE.md` | edit — External systems rows of the chat API and Tavily |

## Tasks

- [X] T001 Chat adapter with its fake and contract test in `src/helper/fact_checker/adapters/llm_chat_api.py` → A1, A2
- [X] T002 Roles tables and the `chat` provider in `src/helper/fact_checker/server.py` → A1, A3
- [X] T003 Tavily adapter with its fake and contract test in `src/helper/fact_checker/adapters/search_tavily.py` → A3
- [X] T004 Search reading on given results in `core/factcheck.py`; the search service and the skipped fact-check in `server.py` → A3
- [X] T005 Roles and keys in doctor in `src/helper/fact_checker/install.py` → A4
- [X] T006 [P] README and ARCHITECTURE rows in `README.md` and `docs/ARCHITECTURE.md` → A4

## Decisions

- **One `chat` adapter for every Chat Completions API, set by `base_url`, `key_env` and `model`** (lead) — one code path for HF, OpenRouter, Groq, Together, DeepSeek, Mistral, Ollama, LM Studio; rejected: one adapter per vendor.
- **`json_schema` strict first; on an HTTP 400 that names `response_format` or `json_schema`, retry once with `json_object` and the schema in the rules, and keep that mode for the adapter** (lead) — many open servers lack strict schemas; rejected: prompt-only JSON.
- **The adapter checks every answer against the schema with a small checker (types, required, enum, items, properties)** (default) — the helper has no dependency (S22); a broken answer raises `RuntimeError` like the other adapters.
- **No key needed when the base URL host is `localhost`, `127.0.0.1` or `::1`; a set key is still sent** (lead).
- **`chat` defaults: key variable `CHAT_API_KEY`, base URL `http://localhost:11434/v1` (a local Ollama), no model** (default) — the only address that needs no account; no model is the obvious one.
- **Search service: Tavily (`POST https://api.tavily.com/search`, `basic` depth, 5 results, `include_published_date`)** (lead pick; default parameters) — 1,000 free credits a month with no card, JSON body, a published date per result, which a flag needs; rejected: Brave Search API, whose get-started docs show no result date and state no free tier.
- **At most 2 queries per claim through the search service, the claim's own queries** (default) — matches the "at most 2 searches per claim" rule of the search prompt.
- **A failed search request gives no results instead of stopping the video** (default) — the same rule as the published fact-checks.
- **`[roles.<role>]` fields override `[<provider>]`, which overrides the provider's defaults; `FACT_CHECK_PROVIDER` ignores the role tables** (default) — S22 A1's edge case says the variable forces every reading.
- **`[tavily]` takes `base_url` and `key_env` (default `TAVILY_API_KEY`)** (default) — like `[anthropic]` and `[openai]`; the tests point it at a local fake.
- **A missing search key fails doctor (exit 1)** (default) — without it no claim is checked; the Google key stays optional.
- **A missing search key logs one usage line `{"step": "fact_check", "stop_reason": "<variable> is not set"}` per video** (default) — the same words as the adapters' missing-key error.

## Out of scope

- The cost experiment with cheaper models: S24, run by the lead.
- Which Hugging Face model to use, Gemini CLI, Windows.
- `fact-checker eval` and `analyze` with a `chat` search role: they ask the search model to browse, and the chat adapter refuses tools.
