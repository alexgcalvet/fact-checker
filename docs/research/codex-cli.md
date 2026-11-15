# Codex CLI headless contract

## Sources

- `codex --help`, `codex exec --help`, `codex exec resume --help`, `codex login --help`, `codex features list`: Codex CLI 0.142.5 (`/Applications/Codex.app/Contents/Resources/codex`), read 2026-11-15.
- [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) (was `developers.openai.com/codex/noninteractive`), read 2026-11-15.
- [Config reference](https://learn.chatgpt.com/docs/config-file/config-reference) (was `developers.openai.com/codex/config-reference`), read 2026-11-15.
- The model list of the person's account in `~/.codex/models_cache.json` (model slugs and effort levels only), read 2026-11-15.
- One live `codex exec --json` tool call on 2026-11-15: it started a thread, then failed with an auth error (below).

## Conclusion

Codex CLI can stand in for `claude -p` in every reading. Every capability is documented, but no answer has been observed yet: the login on this laptop cannot refresh its token. The person must run `codex login` once, then run the S20 contract test to record the fake.

| Capability | Codex CLI | Status |
|---|---|---|
| Non-interactive run | `codex exec [OPTIONS] -` reads the prompt from stdin | observed (thread started) |
| Schema-constrained JSON | `--output-schema <file>`; the final agent message conforms to it | docs |
| System prompt | `-c model_instructions_file=<path>` replaces the built-in instructions | docs |
| Web search | `-c web_search="live"` (`disabled`, `cached`, `indexed`, `live`; default `cached`, an OpenAI index with no live web). `--search` exists only on the interactive command | docs |
| Model | `-m <model>`; the account lists `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini` | account list |
| Effort | `-c model_reasoning_effort=<low\|medium\|high\|xhigh>` | docs, account list |
| Session resume | `codex exec resume <thread_id> -`; the id comes from the `thread.started` event, it cannot be chosen | docs |
| No session on disk | `--ephemeral` | help |
| Usage | `turn.completed.usage`: `input_tokens` (includes cached), `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` | docs |
| Cost | none: a ChatGPT subscription reports tokens, never dollars | docs |
| Auth status | `codex login status` exits 0 and prints `Logged in using ChatGPT` | observed |
| Isolation | `--ignore-user-config` (no user config, plugins or MCP; auth still read), `--ignore-rules`, `--skip-git-repo-check`, `-c project_doc_max_bytes=0` (no `AGENTS.md`), `-c sandbox_mode="read-only"`, `-c approval_policy="never"` | help, docs |

## Event stream (`--json`)

One JSON object per line on stdout. Progress and logs go to stderr.

```json
{"type":"thread.started","thread_id":"0199a213-81c0-7800-8aa1-bbab2a035a53"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_3","type":"agent_message","text":"{\"ok\":true}"}}
{"type":"turn.completed","usage":{"input_tokens":24763,"cached_input_tokens":24448,"output_tokens":122,"reasoning_output_tokens":0}}
```

- Failure (observed): `{"type":"error","message":…}` then `{"type":"turn.failed","error":{"message":…}}`, exit code 1.
- Other items (docs): reasoning, command executions, file changes, MCP tool calls, web searches and plan updates.

## Observed failure

- `codex login status` said `Logged in using ChatGPT`, but `codex exec` failed with `Your access token could not be refreshed. Please log out and sign in again.` (HTTP 401 `invalid_jwt`).
- So `login status` alone does not prove that a tool call works. The contract test also skips on this error.
- The `codex` on PATH (npm `@openai/codex` 0.125.0) has no native binary and fails with `ENOENT`. The desktop app bundles a working CLI. The adapter takes the command from `CODEX_BIN`, else `codex`.

## Gaps

| Gap | Effect | Design |
|---|---|---|
| No dollar cost | The flag file's `cost_usd` stays 0 | Log tokens; compare providers by tokens and by quota use |
| No chosen session id | The first reading of a conversation learns the id from `thread.started` | The adapter writes it into the session |
| Schema rules | Structured output needs every property in `required` and `additionalProperties: false` | The pipeline's schemas already follow this (checked 2026-11-15) |
| A resumed turn's usage | Not documented whether it is per turn or per thread | Read it from the recorded fake after login |
| Usage limits | ChatGPT plan limits per 5 hours and per week; not documented for exec | No retry: a limit lasts hours, so the reading fails |
| Sessions of the conversation mode | Kept in `~/.codex/sessions/`, in the person's Codex history | Only the `conversation` context mode keeps them; `window` (the default) runs `--ephemeral` |
