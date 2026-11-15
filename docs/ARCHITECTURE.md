# Architecture

**RFC**: [RFC.md](RFC.md) · **Target**: [TARGET.md](TARGET.md) · **Synced**: 2026-11-15 · `cb2e89f`
**Pending changes**: 28 new · 15 changed (S5–S37)

Marks: `🟢 **NEW · S5**` and `🟡 **CHANGED · S5**` at the start of a row show what a spec proposes. A row without a mark describes the code today. `/rfc sync` removes the marks of a spec when it is done.

A Chrome extension shows flags on the YouTube player. A Python helper on the person's machine turns a video into flags and caches them per video. The person's state lives in the helper home, outside the repo. With the person's consent, marks and whole analyses go to the owner's collector, a Cloudflare Worker with a D1 database.

## Components

| Component | Job | Path | State |
|---|---|---|---|
| Extension | Reads the video id and playback second on youtube.com; polls the helper; draws flags on the player, the side panel and the strip under the video; asks for consent once, takes votes on cards, and holds the ⚙ settings (language, sharing, quiet mode); texts in Spanish and English | `src/extension/` (texts in `src/texts.ts`, `_locales/`); built copy in `src/helper/fact_checker/extension/` | `chrome.storage`: viewer settings |
| Helper server | Localhost HTTP API: starts and follows an analysis, serves the flag file and the summary, keeps marks, reads and writes the sharing answer; picks the provider of each role from `config.toml`; after a whole analysis or a mark, sends it to the collector if sharing is on | `src/helper/fact_checker/server.py` | none |
| CLI | `serve`, `analyze <url>`, `eval [--save\|--marks]`, `judge <id> [--against-marks]`, `setup`, `doctor [--json]`, `key set <NAME>`, `feedback send\|pull`, `shared list\|approve\|reject` | `src/helper/fact_checker/cli.py` | none |
| Pipeline | A stream of caption chunks in, flags out. Each chunk is analysed with the text before it as context, so a recorded video and a live stream use the same code. A scheduler orders the chunks and guards the budget of each role. Prompts follow the spoken and the reader language (`core/languages.py`). Prices per model in `core/prices.py`. No I/O | `src/helper/fact_checker/core/` | none |
| Transcript adapter | Captions and publish date through yt-dlp; audio + local Whisper when captions are missing | `src/helper/fact_checker/adapters/youtube.py`, `whisper.py` | none |
| 🟢 **NEW · S5** Speaker adapter | Separates the voices of the audio on the laptop and gives each caption word its voice | `src/helper/fact_checker/adapters/diarization.py` | none |
| 🟡 **CHANGED · S20** LLM adapter | Runs a prompt with a JSON schema through `claude -p` on the subscription; 🟢 S20 or through `codex exec` on a ChatGPT subscription, chosen by `FACT_CHECK_PROVIDER` (`claude` by default, or `codex`); or through the Anthropic Messages API, an OpenAI-compatible Responses API, or any Chat Completions API (`chat`) on an API key. `<helper home>/config.toml` picks the provider and the model of each role (`parts`, `verdict`, `judge`, `search`, `screen`), with `[roles.<role>]` for one role on its own provider; `FACT_CHECK_PROVIDER` overrides the provider of every role | `src/helper/fact_checker/adapters/llm_claude_cli.py`, `llm_codex_cli.py`, `llm_anthropic_api.py`, `llm_openai_api.py`, `llm_chat_api.py`; prices in `core/prices.py` | none |
| Fact-check adapter | Searches published fact-checks (Google Fact Check Tools API) | `src/helper/fact_checker/adapters/factcheck_google.py` | none |
| Flag store | One flag file per video | `src/helper/fact_checker/store.py` | `~/.fact-checker/videos/<video_id>.json` |
| Golden dataset | Synthetic Spanish dialogues with planted errors and expected flags | `tests/golden/` | versioned |
| Screen | A cheap reading that says whether a part gets the full reading | `src/helper/fact_checker/core/pipeline.py` (`screen`) | none |
| Judge | One reading of the whole transcript that rules on every non-context flag before the file says done | `src/helper/fact_checker/core/judge.py` | none |
| Search adapter | Web search results for a search role with no web search of its own (Tavily) | `src/helper/fact_checker/adapters/search_tavily.py` | none |
| 🟡 **CHANGED · S35 S36** Summary | Builds the profile card of each guest of a video and the comparison card of up to three people, and renders each as a PNG with its alt text | `src/helper/fact_checker/core/summary.py`, `summary.html`, `adapters/screenshot.py`, `adapters/thumbnail.py`, `cli.py` | `~/.fact-checker/thumbnails/` |
| Feedback | Sends each mark to the collector after consent; keeps the sent record and the install id; `feedback send` and `feedback pull` | `src/helper/fact_checker/feedback.py` | `~/.fact-checker/install-id`, `feedback-sent.json`, `feedback/` |
| Shared analyses | Uploads a whole analysis stripped to the shared fields; downloads an approved one; the owner's list, approve and reject | `src/helper/fact_checker/analyses.py` | none |
| Install | `setup`, `doctor`, `key set`, `provider`: checks the tools, writes `config.toml` and `.env`, copies the extension, starts the helper at login, switches the provider | `src/helper/fact_checker/install.py`, `install.sh`, `INSTALL-AGENT.md` | `~/.fact-checker/config.toml`, `.env`, `extension/` |
| Collector | Cloudflare Worker: keeps testers' marks and shared analyses, serves only approved analyses, hard stops per tester | `src/collector/` | D1 database `fact-checker-feedback` (`schema.sql`) |

- The helper home is `~/.fact-checker/`, or the folder in `FACT_CHECKER_HOME` (tests use a temporary one). It holds `videos/`, `captions/`, `thumbnails/`, the logs, `marks.jsonl`, `config.toml`, `.env` (keys, mode 600), `extension/`, `install-id`, `feedback-sent.json` and `feedback/`.
- Flag files hold quotes from real videos: they stay in the helper home, never in the repo.
- The helper logs each Claude tool call to `~/.fact-checker/usage.log`: date, video id, step, duration, and the lead: how many seconds the chunk was ready before playback reached it. One JSON line each: `ts`, `video_id`, `step`, `chunk_start`, `duration_s`, `lead_s`. 🟢 **NEW · S17** One line per Claude reading, with `step` `speakers`, `analyze_chunk`, `search`, `fact_check` or `judge` (`chunk_start` and `lead_s` null outside a part), plus `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`, `cost_usd` (the API-equivalent `total_cost_usd` of `claude -p`) and `model`. 🟢 **NEW · S18** A part reading of the `conversation` mode also has `session`, the id of the Claude Code session it continues. A resumed session reports the cost of the whole conversation, so such a reading logs the difference from the previous one.
- A fallacy outside the closed list is never shown; the helper writes it to `~/.fact-checker/candidates.log` for the person to review.
- 🟢 **NEW · S16** The helper logs each claim taken from a part to `~/.fact-checker/claims.jsonl`, one JSON line each: `video_id`, `t`, `speaker`, `outcome` (`flagged`, `ok`: a verdict and no flag, `unchecked`: no verdict, no fact-check or refused by the budget; 🟢 **NEW · S17** `skipped`: not central to the speaker's argument, never checked; `repeated`: the same figure as a claim checked earlier in the video, whose second is in `repeats`). No quote, so it holds no transcript. It tells whether a missed figure was never extracted or was checked.
- The person's marks go to `~/.fact-checker/marks.jsonl`, one JSON line each: `video_id`, `flag_id`, `quote`, `type`, `label`, `confidence`, `verdict`, `reason`, and `shared: false` when given with sharing off (such a mark never leaves the machine); never in the repo.

## Dependencies

| From | To | Kind |
|---|---|---|
| Extension | Helper server | HTTP on localhost |
| Helper server, CLI | Pipeline, Flag store | calls |
| Pipeline | LLM port, Transcript port, Fact-check port | calls through ports |
| Adapters | Pipeline types | implements ports |
| Helper server | Feedback, Shared analyses | calls |
| CLI | Install, Feedback, Shared analyses | calls |
| Feedback, Shared analyses | Collector | HTTPS, JSON |
| Pipeline | Search port | calls through ports |

## One run

```mermaid
flowchart LR
  S([video id + playback second]) --> K{flag file<br/>exists and done?}
  K -- yes --> R([serve flags])
  K -- no --> T[fetch captions<br/>+ publish date]
  T --> P[plan chunks from<br/>the playback second]
  P --> C[next chunk,<br/>up to 3 at once]
  C --> Q{screen:<br/>worth a full reading?}
  Q -- no --> B
  Q -- yes --> A[detect claims<br/>attribute speaker]
  A --> X[classify: fallacy, contradiction,<br/>inaccuracy, question, context]
  X --> F[fact check:<br/>published checks,<br/>search, verdict]
  F --> W[append flags<br/>to the flag file]
  W --> B{budget left<br/>and chunks left?}
  B -- yes --> C
  B -- no budget --> Z([status stopped + reason])
  B -- no chunks --> J[judge every flag<br/>over the whole transcript]
  J --> D([status done])
```

- Chunks start at the playback second and run forward, then the earlier part. The first chunk is 30 seconds, the others 2 minutes, so the first flags arrive within seconds.
- 🟡 **CHANGED · S18** Started from the extension, the analysis follows the playback second that each poll carries. No chunk starts more than 10 minutes after the last second heard. After 60 s with no poll (the tab closed) the analysis pauses, and the next poll resumes it. A jump plans again from the new second with a 30-second chunk; the skipped stretch and the part before the start second are analysed only once watched. The analysis is done once every chunk from the playback second to the end is done. Started without the extension (command line, a check), it reads the whole video as before.
- Up to 3 chunks run at once.
- With `HF_TOKEN`, the voices are separated and named in the background: the chunks never wait for them (at most 1 s after the captions, so voices ready at once name the first chunk). Until they come, a chunk names the speakers from the text; the chunks read after use the voices, and every flag already in the file takes the name of the voice heard at its second (id unchanged). The file says `done` only once the voices are known. A failed separation writes a `speakers` usage line with its reason and keeps the text names. The first chunk keeps the screen.
- `POST /videos/<id>` starts again an analysis whose `stop_reason` starts with `error`; a `budget` stop stays. The panel tab says "Preparando el análisis…" until `first_flags_s` is in the file, and a stopped analysis shows its reason in one line on the player.
- 🟢 **NEW · S18** A chunk gets what was said before it in one of two context modes (`CONTEXT_MODE` in `server.py`). 🟡 **CHANGED · S19** `conversation` is the default. A `chat` parts provider always reads `window`: a chat API resends the whole conversation, mostly with no cache:
  - `window`: the 3 minutes before it and the positions list, in its own reading.
  - `conversation`: one Claude Code session reads the chunks in plan order, one at a time; each reading resumes it and sends only its chunk. Over 150k tokens of context, a new session starts and its first reading gets the positions list.
  - An earlier quote of a contradiction or a question is found anywhere in the transcript before the chunk.
- Before its full reading, a cheap model (role `screen`: `haiku`, `claude-haiku-5-5`, `gpt-6-luna`; Codex the account default; `chat` the parts model) reads the chunk alone and answers `read` and a `reason`. Only an explicit `read: false` skips the chunk; an error or another answer reads it. A skipped chunk adds no position; in a conversation its words go as CONTEXT in the next chunk's message. Each screen reading is a `screen` usage line with `read` and `reason`. The screen spends a budget of its own, the size of the part budget. `screen = false` in `config.toml` turns it off, for a measurement.
- 🟢 **NEW · S18** Every reading asks for medium effort and the five-minute cache (`FORCE_PROMPT_CACHING_5M=1`). The search reading may use WebSearch, at most 2 searches per claim, and never opens a page. A reading outside a conversation keeps no session on disk.
- 🟢 **NEW · S16** Each chunk also gets the positions list: what each speaker stated in the chunks done before it starts, earlier in the video, one line each (`Invitado (3:00): summary «quote»`). The same part tool call returns the new positions, so the list adds no tool call. Over 60 lines, the oldest line of a speaker takes in their next one, without quotes. A contradiction can quote an earlier position from anywhere in the video.
- A contradiction flag carries the time of the second utterance.
- 🟢 **NEW · S17** The part tool call marks each claim `central` or not, and names a claim that repeats one already checked in the video (the list of checked claims is in its prompt). Only central, new claims go to the fact-check, so each figure is checked once per video. With 3 parts at once, a repeat of a claim still in flight is checked again.
- 🟡 **CHANGED · S17 S18** The fact-check is two readings: Haiku with WebSearch (S18: no WebFetch) gathers the evidence of the part's claims, then Opus with no tools turns it into verdicts. A verdict cites only urls of the evidence or of the published fact-checks. Without a search LLM (`run_analysis` without `searcher`, `fact-checker eval`), one reading searches and judges.
- 🟢 **NEW · S17** The fixed rules of the part and fact-check tool calls go in the system prompt, the same text in every reading, so they are read from cache; the part data goes in the prompt. The part tool call returns at most 2 context cards.

## Contracts

**Flag file** (`~/.fact-checker/videos/<video_id>.json`, served by `GET /videos/<id>` with the latest `mark` added to each flag)

```json
{
  "video_id": "abc123",
  "published_at": "2026-11-13",
  "status": "running",
  "stop_reason": null,
  "analysed_until": 270.0,
  "flags": [
    {
      "id": "f1",
      "t": 754.2,
      "speaker": "guest",
      "quote": "exact words of the utterance",
      "type": "fallacy",
      "label": "ad_hominem",
      "reason": "one short sentence",
      "confidence": 0.86,
      "related": { "t": 120.5, "quote": "earlier words" },
      "sources": [{ "publisher": "INE", "url": "https://…", "date": "2026-10-01" }],
      "note": null
    }
  ]
}
```

| Field | Values |
|---|---|
| `status` | `running`, `done`, `stopped` |
| `title`, `channel`, `duration` | from yt-dlp with the publish date; `duration` in seconds, null for a live stream |
| 🟢 **NEW · S17** `cost_usd` | the sum of `cost_usd` of every Claude reading of the video so far, as in the usage log |
| `spoken`, `lang` | `spoken`: the video's language, `es` or `en`, from the caption track read (`es-orig`, `en-orig`, `es`, `en`) or the speech engine; `lang`: the language of every `reason`, `note`, judge reason and of the shareable summary, from the analyze request, else `spoken`. Quotes stay in `spoken`; label ids are the same in both languages |
| 🟡 **CHANGED · S18** `analysed_until` | the end of the parts done without a gap from the start second (S18: from the playback second last heard); a stretch with no caption is no gap; starts at that second |
| `type` | `fallacy`, `bias`, `contradiction`, `inaccuracy`, `question`, `context` |
| 🟡 **CHANGED · S16** `label` | fallacy: `ad_hominem`, `tu_quoque`, `false_dilemma`, `straw_man`, `false_cause`, `hasty_generalization`, `vague_authority`, 🟢 S16 `insinuation`, `double_standard`, `cherry_picking`, `appeal_to_fear`; inaccuracy: `false`, `misleading`, `disputed`, `definition_swap`, `plan_as_fact`; contradiction: `self`, `record` (the speaker's earlier public statement), `promise` |
| `measures` | inaccuracy: each credible measure of the figure, `{name, value, source, tier, supports}`; required for `disputed` |
| `controversy` | inaccuracy: one sentence on a documented controversy about the metric, with its source, else null |
| `answer` | question only: `answered`, `partial` or `dodged`; `t` is the end of the answer, `related` holds the question |
| `related` | contradiction, straw man and question: the earlier utterance; for a contradiction with the record, also its `date` and `source` |
| `sources` | inaccuracy and contradiction `record` or `promise`: required; others: empty |
| `promise` | contradiction `promise` only: `{made, figure, deadline, status}`; `made` is `YYYY-MM`, `status` is `met`, `partly met`, `not met` or `in progress`; only `partly met` and `not met` make a flag |
| `note` | inaccuracy: the updated value when the data changed after `published_at` |
| `on_player` | `true` when the confidence reaches the bar of the flag's type |
| `judge` | non-context flags, once every part is done and before `status` says `done` (on in the helper and in `fact-checker judge <id>`, off by default in `run_analysis`): `{verdict: keep\|nitpick\|drop, reason, speaker?}` from one Opus reading per started 2 video-hours of the whole transcript with speakers. 🟡 **CHANGED · S32** The judge rules only `keep` or `nitpick` (a "puntualización", for a small slip of any flag type), and any other answer is `keep`; `drop` remains only in files judged before S32. `speaker` only when the line belongs to someone else. The found flag stays, so the judge is reversible. Absent when the judge fails. A `mark` wins: a flag marked `correct` shows as found, under the judge's speaker The verdict carries `severity?`: `minor`, `moderate` or `serious` by a published rubric (materiality, centrality, magnitude; never intent), only on a `keep`; a file judged before S34 has none |
| `first_flags_s` | seconds from the start of the analysis to the first chunk written; absent until then; not in a shared copy |
| `source` | `shared` when the file came from the author's collector (another person's whole analysis in the viewer's language); absent for an analysis made here |
| `speakers` | the name of each voice of the transcript |
| `people` | per speaker name `{role: host\|guest, person, spoken_s, set_by: llm\|person}`: `person` is the canonical name that matches one person across videos; `spoken_s` the seconds of speech |
| `readers` | the provider and model of each role that read the video, `{parts: {provider, model}, …}`; absent in older files |
| `mark` | on `GET` only, never in the file: the person's latest verdict on the flag, `correct` or `unfair`; absent with no mark |

**Helper HTTP API** (localhost only)

| Request | Purpose |
|---|---|
| `POST /videos/<id>?from=<seconds>&lang=<es\|en>` | Start an analysis at the playback second if no flag file exists; `lang`, the extension's interface language, goes into the flag file (any other value: 400) |
| 🟡 **CHANGED · S18** `GET /videos/<id>?at=<seconds>` | Return the flag file so far, each flag with its latest `mark` from `marks.jsonl`. 🟢 S18: `at`, the playback second, moves and resumes a running analysis; the extension sends it on every poll. With `lang` and no local file, the helper first asks the collector `GET /analyses/<id>?lang=` (no install id, 5 s) and keeps what it gets with `source: "shared"`; else 404 |
| `POST /videos/<id>/marks` | Keep the person's mark on one flag: `{flag_id, verdict: correct\|unfair, reason}`; with sharing on, the helper sends it to the collector in the background |
| `POST /videos/<id>/people` | The person sets the role of one speaker: `{name, role}`; `set_by` becomes `person` |
| 🟡 **CHANGED · S35** `GET /videos/<id>/summary.png?person=<name>` | The profile card of one guest: 1080×1350, only flags marked `correct`, rendered by headless Chrome in the layout of the CALVET board `InterviewCard`; all text ≥ 30 px |
| `GET /videos/<id>/summary.txt` | The alt text of the image, at most 1000 characters |
| `GET /videos/<id>/summary` | A page with the image and its alt text ready to copy; the extension opens it in a new tab |
| `GET /share` | The sharing answer: `{share: true\|false\|null}`; null until the person answers |
| `POST /share` | `{share: bool}`: writes `share_marks` into `config.toml` (any other body: 400) |
| `GET /provider` | The provider of the parts role, `{provider}`, for the spend line under the analyse button |
| 🟢 **NEW · S38** `GET /health` | `{app: "fact-checker", version, pid, home, writable}`: doctor, setup and the extension tell the helper from another program on the port; `writable` is false when the helper cannot write its home (a start inside an agent's sandbox) |

**Collector API** (`src/collector/src/index.ts`; tables in `schema.sql`)

| Request | Caller | Purpose |
|---|---|---|
| `POST /marks` | a tester's helper | Keeps up to 500 marks (256 KB) of one install id; a mark sent again replaces its row; 20 accepted requests per install id per UTC day, then 429 |
| `GET /marks?since=<ISO time>` | the owner, `Authorization: Bearer <ADMIN_TOKEN>` | The rows received after that time; 401 without the token |
| `PUT /analyses/<video_id>?lang=<es\|en>` | a helper, after a whole analysis | `{install_id, analysis}`: status `done`, ≤ 1 MB, ≤ 1,000 flags, http(s) links only. Without the token: pending (202); with it: served (201, or 200 when it replaces). 409 when the served analysis's parts model ranks equal or higher (opus > sonnet > haiku > other); 10 uploads per install id per UTC day |
| `GET /analyses/<video_id>?lang=` | any helper, no install id | The approved analysis, or 404 |
| `GET /analyses` | the owner | The pending uploads |
| `POST /analyses/<video_id>/approve\|reject?lang=` | the owner | Serve the best pending upload, or delete the pending ones |
| `DELETE /analyses/<video_id>?lang=` | the owner | Remove a served analysis |
| 🟢 **NEW · S37** `GET /a/<video_id>?lang=` | anyone, no install id | A read-only HTML page of the approved analysis: each flag with its verdict, severity and sources, and the severity rubric; 404 when none is approved |

- A sent mark holds: video, second, type, label, quote (≤ 1,000 characters), confidence, verdict, reason (≤ 500), provider, model, helper version, install id. Rows hold no name, email, IP or path.
- A shared analysis holds only `video_id`, `lang`, `spoken`, `status`, `published_at`, `title`, `channel`, `duration`, `speakers`, `people`, `readers`, `cost_usd`, `analysed_until`, `flags`.
- 🟡 **CHANGED · S35** A shared analysis also holds `claims`: per speaker name `{checked, correct}`, the tally of `claims.jsonl`, numbers only.

**Settings file** (`<helper home>/config.toml`; `fact-checker setup` writes it from `config.example.toml`)

| Key | Values |
|---|---|
| `provider` | `claude` (default), `codex`, `anthropic`, `openai`, `chat` |
| `feedback_url` | the collector address; none: nothing is sent |
| `share_marks` | `true`, `false`; absent: not asked yet, nothing is shared |
| `screen` | `false` turns the screen off, for a measurement |
| `[models]` | `parts`, `verdict`, `judge`, `search`, `screen`: a model per role |
| `[anthropic]`, `[openai]`, `[chat]`, `[tavily]` | `base_url`, `key_env` |
| `[roles.<role>]` | `provider`, `base_url`, `key_env`, `model` for one role |

**Ports** (Pipeline)

| Port | Function |
|---|---|
| LLM | `complete(prompt, schema, tools=()) -> dict` |
| Transcript | `fetch(video_id) -> Transcript(segments[t, text], published_at, language, speakers)` |
| Search | `search(query) -> list[{title, url, content, published_date}]` |

**Pipeline interface**

| Function | Purpose |
|---|---|
| `plan(transcript, from_t) -> list[Chunk]` | Orders the chunks from the playback second |
| 🟡 **CHANGED · S16 S18** `analyze_chunk(chunk, context, ports, positions, checked, session, said) -> ChunkResult` | Flags, claims and new positions of one chunk; `context` is the text before it, `positions` what the speakers stated earlier in the video. 🟢 S18: with a `session`, the chunk is the next message of that conversation; `said` is all text before the chunk, where earlier quotes are found. A live stream calls it with a rolling window |
| `screen(chunk, llm, …) -> {read, reason}` | Whether a part gets the full reading; only an explicit `read: false` skips it |
| `judge(flags, transcript, llm, reader) -> {flag_id: {verdict, reason, speaker?}}` | The judge's verdict on every non-context flag |
| Fact-check | `search(claim, language) -> list[PublishedCheck]` |

**Display rule**: a flag goes on the player when its confidence reaches the bar of its type in `src/helper/fact_checker/thresholds.json` (🟢 **NEW · S20** for another provider, `thresholds.<provider>.json`; with no such file, every bar is 0.8); the helper writes the result in `on_player`. `fact-checker eval --save` sets the bars of the provider in use from the golden dataset: the lowest confidence with precision ≥ 0.80, or `null` (never) with fewer than 5 flags. Flags under the bar go to the side panel. The viewer can narrow the rule with quiet mode (serious flags only; a flag not yet judged shows at confidence ≥ 0.9) and pin a card past its 8 seconds; both live in the extension only.

## Seams

| Component | Public interface | Test through |
|---|---|---|
| Pipeline | `plan`, `analyze_chunk` | Golden dataset with a fake LLM for unit cases; the real LLM in `eval` |
| Helper server | HTTP API above | An integration test with fake ports |
| Adapters | Their port | A recorded, sanitized response of each system |
| Extension | Flag file in, DOM out | A test page that mimics the player with a fixed flag file |
| Collector | Its HTTP routes | vitest with Node's built-in SQLite as the D1 binding (`tests/acceptance/s24_d1_fake.ts`); a contract test against the deployed Worker |
| Feedback, Shared analyses | `feedback.py`, `analyses.py` functions | a fake collector (`tests/acceptance/s24_fakes.py`, `s28_fakes.py`) |
| Install | `install.sh`, `setup`, `doctor --json` | fake commands on PATH and a temporary HOME |

## External systems

| System | Used for | Interface | Auth | Contract source | Owner | Status | Test double |
|---|---|---|---|---|---|---|---|
| YouTube via yt-dlp | Captions, publish date, audio (16 kHz mono WAV) | CLI / Python library | none | [external-contracts.md](research/external-contracts.md) | yt-dlp project / YouTube | confirmed | invented captions: `tests/fakes/youtube/` |
| Claude Code (`claude -p`) | LLM calls and web search | CLI, headless | the person's subscription login | [external-contracts.md](research/external-contracts.md) | Anthropic | confirmed | recorded fake: `tests/fakes/claude-code/` |
| Google Fact Check Tools API | Published fact-checks (ClaimReview) | REST | API key in header `X-goog-api-key`, from `FACT_CHECK_API_KEY` | [external-contracts.md](research/external-contracts.md), [API reference](https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search) | Google | confirmed | recorded fake: `tests/fakes/google-factcheck/` |
| 🟢 **NEW · S5** pyannote (Hugging Face) | Separates the voices of the audio | Python library, model `pyannote/speaker-diarization-community-1` | read token in `HF_TOKEN` | [external-contracts.md](research/external-contracts.md) | pyannote / Hugging Face | confirmed | fake: `tests/fakes/pyannote/` |
| Whisper (mlx-whisper) | Speech to text when a video has no usable captions | Python library, model `mlx-community/whisper-large-v3-turbo`, Apple silicon | none | [external-contracts.md](research/external-contracts.md) | ml-explore / OpenAI (model) | confirmed | fake: `tests/fakes/whisper/` |
| Whisper (faster-whisper) | Speech to text when a video has no usable captions, on an Intel Mac or Linux | Python library, model `large-v3-turbo` (`mobiuslabsgmbh/faster-whisper-large-v3-turbo`), CPU int8 | none | [faster-whisper.md](research/faster-whisper.md) | SYSTRAN / OpenAI (model) | confirmed | the Whisper fake: `tests/fakes/whisper/` (same words) |
| YouTube thumbnail (`i.ytimg.com/vi/<id>/maxresdefault.jpg`, then `hqdefault.jpg`) | The hero image of the summary, embedded as a data URI; kept in `~/.fact-checker/thumbnails/`; a gradient when missing | HTTPS GET | none | public URL | YouTube | confirmed | none (the S14 A2 test runs without it) |
| Headless Chrome | Turns the summary page of a video into a PNG | CLI, `--headless --screenshot` | none | [external-contracts.md](research/external-contracts.md) | Google | confirmed | fake: `tests/fakes/headless-chrome/` |
| 🟢 **NEW · S20** Codex CLI (`codex exec`) | LLM calls and web search when `FACT_CHECK_PROVIDER=codex` | CLI, headless, JSON Lines events | the person's ChatGPT login (`codex login`) | [codex-cli.md](research/codex-cli.md) | OpenAI | confirmed (docs; no answer observed yet: the login on the laptop has expired) | docs-built fake: `tests/fakes/codex-cli/`, to re-record |
| Anthropic Messages API (`POST /v1/messages`) | LLM calls and web search when `provider = "anthropic"` | REST, JSON | API key in header `x-api-key`, from `ANTHROPIC_API_KEY` (or `key_env`) in the environment or `<helper home>/.env` | [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool), [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Pricing](https://platform.claude.com/docs/en/about-claude/pricing), read 2026-11-15 | Anthropic | confirmed (docs; no answer observed: no key in the build session) | docs-built fake: `tests/fakes/anthropic-api/`, to re-record |
| OpenAI Responses API (`POST <base_url>/responses`) | LLM calls and web search when `provider = "openai"`: OpenAI, or xAI Grok with `base_url = "https://api.x.ai/v1"` | REST, JSON | `Authorization: Bearer <key>`, the key from `key_env` (`OPENAI_API_KEY` by default) in the environment or `<helper home>/.env` | [Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create), [Web search](https://developers.openai.com/api/docs/guides/tools-web-search), [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [Pricing](https://developers.openai.com/api/docs/pricing), [xAI Responses](https://docs.x.ai/developers/rest-api-reference/inference/responses), read 2026-11-15 | OpenAI / xAI | confirmed (docs; no answer observed: no key in the build session) | docs-built fake: `tests/fakes/openai-api/`, to re-record |
| Chat Completions API (`POST <base_url>/chat/completions`) | LLM calls with no web search when a role's provider is `chat`: Hugging Face (`https://router.huggingface.co/v1`), OpenRouter, Groq, Together, DeepSeek, Mistral, or a local Ollama (`http://localhost:11434/v1`) or LM Studio | REST, JSON | `Authorization: Bearer <key>`, the key from `key_env` (`CHAT_API_KEY` by default) in the environment or `<helper home>/.env`; no key on a `localhost` address | [Chat create](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [HF Inference Providers](https://huggingface.co/docs/inference-providers/index), [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility), read 2026-11-15 | OpenAI (format) / each vendor | confirmed (docs; no answer observed: no key in the build session) | docs-built fake: `tests/fakes/chat-api/`, to re-record |
| Tavily search API (`POST https://api.tavily.com/search`) | Web search results for a `search` role with no web search of its own | REST, JSON | `Authorization: Bearer <key>`, the key from `TAVILY_API_KEY` (or `[tavily] key_env`) in the environment or `<helper home>/.env` | [Search](https://docs.tavily.com/documentation/api-reference/endpoint/search), [Credits](https://docs.tavily.com/documentation/api-credits), read 2026-11-15 | Tavily | confirmed (docs; no answer observed: no key in the build session) | docs-built fake: `tests/fakes/tavily/`, to re-record |
| Cloudflare Workers + D1 | Hosts the collector and its database | Workers runtime with a D1 binding `DB`; deploy with wrangler | `ADMIN_TOKEN` Worker secret for the owner's routes; the owner's Cloudflare login to deploy | [D1 limits](https://developers.cloudflare.com/d1/platform/limits/) (docs/specs/028-shared-analyses/spec.md), docs/specs/024-shared-feedback/spec.md, [collector README](../src/collector/README.md); `tests/acceptance/test_contract_collector_marks.py` passed against the deployed Worker (2026-11-15) | Cloudflare | confirmed | Node SQLite as D1: `tests/acceptance/s24_d1_fake.ts` |
| uv installer, PyPI, GitHub archive | `install.sh` installs uv, yt-dlp, ffmpeg (imageio-ffmpeg wheel) and the helper | HTTPS, shell | none | [one-step-install.md](research/one-step-install.md) | Astral, PyPI, GitHub | confirmed | fake `curl` and `uv` in `tests/acceptance/test_s25_a1_installer.py` |
| Chrome extension platform | Content script, background worker | Manifest V3 APIs; content script → message → service worker fetch to `127.0.0.1` | `host_permissions: http://127.0.0.1/*`; `storage` for the viewer settings | [external-contracts.md](research/external-contracts.md), spike 2026-11-13 | Google | confirmed | none yet |

| Status | Set by | Effect |
|---|---|---|
| unknown | default | goes to Open questions with an owner; blocks dependent slices |
| assumed | a guess written down | same as unknown |
| confirmed | vendor docs, an API description, a cleaned real response, the person's answer, or a passing contract test | slices may depend on it |

**YouTube via yt-dlp**

- Call: `yt-dlp --no-simulate --skip-download --write-auto-subs --sub-langs es-orig,es --sub-format json3 --print upload_date -o <dir>/%(id)s <url>`. `--print` alone simulates and writes no file.
- Captions: often only automatic ones. Prefer track `es-orig` over `es`. `json3` events carry `tStartMs`, and segments carry `utf8` and `tOffsetMs`. No speaker field.
- Size: about 12,000 words per hour of speech.
- Errors and limits: not observed yet.
- Environments: production only; no sandbox.

**Claude Code (`claude -p`)**

- Call: `claude -p <prompt> --output-format json --json-schema <schema> [--allowedTools WebSearch]`. The answer is in `structured_output`; check `is_error` and `api_error_status`.
- Web search: works headless and honours `allowed_domains`; it returns no source date.
- Limits: subscription usage limits per hour are not documented.
- Environments: the person's own account; no sandbox.

**🟢 NEW · S20 Codex CLI (`codex exec`)**

- Call: `codex exec --json --ephemeral --skip-git-repo-check --ignore-user-config --ignore-rules -m <model> -c model_reasoning_effort="medium" -c model_instructions_file=<rules file> -c web_search="disabled"|"live" -c project_doc_max_bytes=0 -c sandbox_mode="read-only" -c approval_policy="never" --output-schema <schema file> -`, the prompt on stdin. A conversation drops `--ephemeral`; its next reading is `codex exec resume <thread_id> … -`.
- Answer: the `text` of the last `item.completed` event whose item type is `agent_message`, JSON by the schema. Usage: `turn.completed.usage` (`input_tokens` includes `cached_input_tokens`). Thread id: `thread.started.thread_id`. Failure: an `error` or `turn.failed` event, exit code 1.
- Models: `gpt-5.5` reads, judges and gives verdicts; `gpt-5.4-mini` searches. No default model: a role with no model in `config.toml` passes no `-m`, so Codex uses the account's own default, and its usage lines say `codex-default`. Codex 0.169.0 on a ChatGPT account rejects `gpt-5.5` and `gpt-5.4-mini`; `codex debug models` lists the models of the plan.
- No dollar cost: a reading logs tokens and `cost_usd` 0.
- Limits: ChatGPT plan limits; not documented for exec.
- Command: `CODEX_BIN`, else `codex` on PATH, else 🟢 **NEW · S39** the one inside the ChatGPT app (`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`); `setup` adds its folder to the login helper's PATH when Codex reads.
- Environments: the person's own account; no sandbox.

**Anthropic Messages API**

- Call: `POST https://api.anthropic.com/v1/messages` (or `[anthropic] base_url`), headers `x-api-key`, `anthropic-version: 2026-10-21`. Body: `model`, `max_tokens`, `system` as one text block with `cache_control: {type: "ephemeral"}` (the fixed rules), top-level `cache_control` (moves the breakpoint to the last block of a conversation), `messages`, `output_config: {effort: "medium", format: {type: "json_schema", schema}}`. The search adds `tools: [{type: "web_search_20260209", name: "web_search", max_uses: 5}]`.
- Schema limits: every object `additionalProperties: false`; no `minimum`, `maximum`, `maxItems` (the adapter drops them); at most 16 union types and 24 optional fields per request.
- Answer: the last `text` block of `content`, JSON by the schema. `stop_reason` `pause_turn`: send the assistant content back and ask again; `refusal` or `max_tokens`: the reading fails. Errors: HTTP 4xx/5xx with `{type: "error", error: {type, message}}`; 429 and 529 are retried after 30 s and 60 s.
- Usage: `input_tokens` (after the last breakpoint), `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`, `server_tool_use.web_search_requests`.
- Conversation: the adapter keeps the message list of a session and sends the assistant `content` back unchanged.
- Prices per million tokens (input, 5-minute cache write, cache read, output): `claude-opus-5-5` 4, 5, 0.20, 20; `claude-sonnet-5-5` 2, 2.50, 0.10, 10. Web search: $10 per 1,000 searches.
- Environments: production only; no sandbox.

**OpenAI Responses API**

- Call: `POST <base_url>/responses` (`https://api.openai.com/v1` by default), header `Authorization: Bearer <key>`. Body: `model`, `instructions` (the fixed rules; never carried over by `previous_response_id`, so sent each time), `input`, `reasoning: {effort: "medium"}`, `text: {format: {type: "json_schema", name, schema, strict: true}}`, `store`. The search adds `tools: [{type: "web_search"}]`. A conversation sends `previous_response_id` and only the new input; every earlier input token is billed again.
- Answer: the `output_text` content of the last `message` item of `output`; `refusal` content, `status` other than `completed`, or `error` fails the reading. `incomplete_details.reason` says why it stopped.
- Usage: `input_tokens` (includes `input_tokens_details.cached_tokens`), `output_tokens`; each `web_search_call` item is one search.
- Prices per million tokens (input, cached input, output): `gpt-6-astra` 10, 1, 50; `gpt-6-luna` 0.10, 0.01, 0.50; `gpt-5.5` 5, 0.50, 30; `gpt-5.4-mini` 0.75, 0.075, 4.50. Web search: $10 per 1,000 calls. Grok models: no price, null cost.
- xAI: the same endpoint at `https://api.x.ai/v1/responses`, with `previous_response_id`, `text.format` json_schema and the `web_search` tool.
- Environments: production only; no sandbox.

**Chat Completions API**

- Call: `POST <base_url>/chat/completions`, header `Authorization: Bearer <key>` when a key is set. Body: `model`, `messages` (a `system` message with the fixed rules, then `user` and `assistant` turns), `response_format: {type: "json_schema", json_schema: {name, schema, strict: true}}`.
- Fallback: a server that answers HTTP 400 naming `response_format` or `json_schema` gets `response_format: {type: "json_object"}` with the schema in the system message, from then on. The adapter checks every answer against the schema.
- Answer: `choices[0].message.content`, JSON by the schema; a `refusal`, or a `finish_reason` other than `stop`, fails the reading.
- Usage: `prompt_tokens` (includes `prompt_tokens_details.cached_tokens`, which some servers leave out), `completion_tokens`.
- Conversation: the adapter keeps the message list of a session and sends it again with the new part.
- Prices: a model missing from `core/prices.py` logs a null cost.
- Hugging Face: one HF token routes to many providers; a model id may end in `:fastest`, `:cheapest` or `:<provider>`.
- Environments: production only; no sandbox.

**Tavily search API**

- Call: `POST https://api.tavily.com/search`, header `Authorization: Bearer <key>`. Body: `query`, `search_depth: "basic"` (1 credit), `max_results: 5`, `include_published_date: true`.
- Answer: `results[]` with `title`, `url`, `content` (a snippet), `score`, `published_date` (null when no date is found).
- Errors: 400, 401 (bad key), 422, 429 (with `Retry-After`), 432 (plan limit), 433 (pay-as-you-go limit). A failed search gives no results.
- Limits: 1,000 free credits a month, no card.
- Environments: production only; no sandbox.

**Google Fact Check Tools API**

- Call: `GET https://factchecktools.googleapis.com/v1alpha1/claims:search?query=…&languageCode=es`.
- Response: `claims[]` with `text`, `claimant`, `claimDate`, `claimReview[]` (`publisher.site`, `url`, `title`, `reviewDate`, `textualRating`, `languageCode`). `textualRating` is free text, such as `Engañoso` or `Verdad a medias`.
- Errors: HTTP 400 with `{error: {code, message, status}}` for a bad key or a missing query.
- Limits: quotas not documented.
- Environments: production only; no sandbox.

## Hosting

The helper and the extension run on each person's macOS (Apple silicon or Intel) or Linux machine, with their own subscription or API key; Windows later. The owner deploys one collector on Cloudflare.

| Piece | Used for |
|---|---|
| Helper process | `fact-checker serve` on `127.0.0.1:8765` (`--port` to change), started after loading `.env` so that `FACT_CHECK_API_KEY` is set; without it the fact-check step is skipped. 🟢 **NEW · S20** `FACT_CHECK_PROVIDER=codex` reads with Codex CLI instead of Claude Code. `~/.fact-checker/config.toml` picks the provider (`claude`, `codex`, `anthropic`, `openai`) and the model of each role; `fact-checker doctor` prints them and names a missing API key variable |
| 🟢 **NEW · S38** Helper ports | `fact-checker serve` without `--port` takes the first free port of 8765–8769 (`FACT_CHECKER_PORT` moves the range, for tests); with all five taken it logs one line and exits 0, and the login agent restarts it only after a failure. The extension finds the helper over the five ports by `/health` and keeps the port. `setup` stops the fact-checker helpers of its home in the range, then waits for `/health`; `doctor` names another program on a port and an agent's sandbox |
| Install | `uv tool install ./src/helper`; `fact-checker setup` checks claude (logged in), uv, yt-dlp, ffmpeg and Chrome or Chromium, then starts the helper at login: a launchd agent `com.fact-checker.helper` on macOS, a systemd user service `fact-checker.service` on Linux, with the PATH of the setup shell. `fact-checker doctor` prints one line per check with its fix. The helper reads optional keys (`HF_TOKEN`, `FACT_CHECK_API_KEY`) from `~/.fact-checker/.env`. `install.sh` installs uv, yt-dlp, ffmpeg (imageio-ffmpeg static build) and the helper, each only if missing, then runs `setup`; `INSTALL-AGENT.md` leads an AI agent through it. `setup` writes the logged-in agent CLI (`claude`, then `codex`) into a new `config.toml` and copies the built extension to `~/.fact-checker/extension`. 🟢 **NEW · S39** `setup --provider claude|codex` writes the provider the installing agent names (only if it is logged in; the other lines of `config.toml` stay); `fact-checker provider [claude|codex]` prints the provider, or writes it and restarts the login helper (`launchctl kickstart -k`, `systemctl --user restart`). `fact-checker key set <NAME>` stores a key from a hidden prompt; `doctor --json` gives the checks to an agent |
| Speech engine | mlx-whisper on Apple silicon, faster-whisper on other machines, both through `uv run --script`; with no uv, a video without captions stops with a reason that names the doctor |
| Chrome, unpacked extension | The display; it says when the helper does not answer. `npm run build` writes it into the helper package (`src/helper/fact_checker/extension/`, committed), so a person needs no Node.js. Its texts follow the browser language (Spanish for `es*`, else English), with an ES/EN choice in ⚙ |
| `~/.fact-checker/` | The helper home: see Components |
| Collector | Cloudflare Worker `fact-checker-feedback` + D1, on the free plan, deployed once by the owner (`src/collector/README.md`); its address is `feedback_url` in `src/helper/fact_checker/config.example.toml` |

## Repo layout

Goal: a new adapter, flag type or provider is one new file, with no edit elsewhere.

```
src/helper/fact_checker/core/       pipeline, flag types, budget   no I/O
src/helper/fact_checker/adapters/   one file per external system
src/helper/fact_checker/server.py   HTTP entry point
src/helper/fact_checker/cli.py      CLI entry point
src/extension/                      TypeScript, Manifest V3
tests/golden/                       synthetic dialogues + expected flags
tests/acceptance/                   approved acceptance tests
tests/fakes/                        one folder per external system
src/helper/fact_checker/feedback.py, analyses.py   collector client
src/helper/fact_checker/install.py  setup, doctor, key set
src/helper/fact_checker/extension/  built extension, committed
src/collector/                      Cloudflare Worker + D1 schema
install.sh, INSTALL-AGENT.md        one-step install
.github/workflows/checks.yml        CI
```

| Layer | May import | May not import |
|---|---|---|
| `core/` | nothing else in the repo | adapters, entry points |
| adapters | `core` types | each other, entry points |
| entry points | `core/`, adapters, store | business logic |
| collector clients, install (`feedback.py`, `analyses.py`, `install.py`) | `core` types, `store` | entry points |

## Verify

The `verify` key in `.claude/mini-spec.yml` holds the command. `/mini-implement` runs it after the hash check of approved tests, before it proposes commits.

| Checks | Tool |
|---|---|
| Helper tests | pytest, run with `uvx` from `src/helper/` |
| Extension and collector types and tests | `tsc --noEmit` (extension and `src/collector`), vitest; esbuild builds into `src/helper/fact_checker/extension/` |
| CI | GitHub Actions, `.github/workflows/checks.yml`: the same checks on each pull request and push to main, and the shipped extension matches a fresh build |
| Layer rules of Repo layout | none yet |

## Scaling to more users

Each person runs their own helper and pays their own readings. The collector shares a whole analysis per video and language, once the owner approves it, so a later viewer pays nothing. A new LLM provider is one adapter file plus a `provider` value. TARGET.md Step 2 moves the pipeline to a backend; not built until Step 1 meets its precision target. The first limits: the collector's hard stops (20 mark requests and 10 uploads per install id per day) and the owner's review of each upload.

## Decisions

| Decision | Why | Beat |
|---|---|---|
| A local helper on the person's own subscription by default (Claude Code, else Codex); an API key is an option (chat, S20, S22) | No extra cost to the person or the owner | A paid backend |
| Captions through yt-dlp; Whisper only as fallback (chat) | Free and fast | Audio transcription for every video |
| 🟡 **CHANGED · S5** Voices come from the audio; the LLM only names them from the whole interview (chat, 2026-11-14) | The person's marks: 4 of 6 unfair cards had a wrong speaker | The LLM guessing speakers from 2 minutes of captions |
| A bar per flag type from measured precision, per provider; the side panel lists every flag (S3, S11, S20) | Precision on the player, nothing lost | Fixed levels at 0.80 and 0.50; a user slider |
| Published fact-checks before web search (docs/research/interview-youtube-fact-checker.md) | High confidence, cites accredited checkers, free | Web search only |
| Official and primary sources first; others lower confidence (docs/research/interview-youtube-fact-checker.md) | Credibility of each flag | Any web source |
| An official figure is not the truth by itself: "false" needs every credible measure against the claim; one supporting measure gives "disputed"; sources weigh by tier of independence (docs/research/official-data-controversies.md) | Statistics can be defined or framed to fit a side; a fact-checker that trusts one figure takes a side | Treating official data as ground truth |
| Claims checked against data at the publish date (docs/research/interview-youtube-fact-checker.md) | Fair to older videos | Latest data |
| 🟢 **NEW · S17** A cheaper model searches, Opus judges; only central claims are checked, once per video; the cost is the API-equivalent `total_cost_usd` of `claude -p` (S17) | About 70 % of the cost of a video was Opus fact-checks that resend every search result each turn | Opus for search and verdict; checking every figure |
| Hard stop at 60 Claude tool calls per started video-hour, counting every call (docs/research/interview-youtube-fact-checker.md, S2); 🟢 S17 the search model has its own budget of the same size | A failure cannot exhaust the subscription; a short video still gets room for analysis and checks | No limit; a budget pro rata to the duration |
| An inaccuracy is shown only when a dated source contradicts it; a published fact-check gives its review date (S2) | Precision first; every factual flag names its source and date | Showing confirmed or unverifiable claims |
| The pipeline is a stream of chunks with context, not a batch (docs/research/interview-youtube-fact-checker.md) | Live streams in Step 3 reuse it; only the text source and the LLM provider change | A whole-transcript batch |
| Start at the playback second, first chunk 30 s, up to 3 chunks at once (docs/research/interview-youtube-fact-checker.md) | Flags are ready before playback reaches them, without hitting subscription limits | Playback order from second 0, one call at a time |
| Python helper, TypeScript extension (docs/research/interview-youtube-fact-checker.md) | yt-dlp, Whisper, pyannote are Python | All TypeScript |
| 🟡 **CHANGED · S16** A closed list of fallacy labels (7 after S7, plus 4 in S16); a straw man only when the distorted statement is in the same video (docs/research/interview-youtube-fact-checker.md) | Each is visible in the words, frequent in political talk and has few false positives | An open-ended list |
| Fallacies outside the list go to a review log, never to the screen (docs/research/interview-youtube-fact-checker.md) | New types enter with data | Discard them; an "other" type in the side panel |
| Every speaker is analysed alike, the interviewer included (docs/research/interview-youtube-fact-checker.md) | A flag is about what is said, not who says it | Only the interviewee |
| An unanswered question is its own flag type with a status, not a fallacy label (docs/research/interview-youtube-fact-checker.md) | In an interview, a dodged question matters most and needs the question beside it | `evasion` as one of the fallacies |
| The judge writes a `judge` field and keeps the found flag; the file says done only after it (S15) | Reversible; the person's mark wins | Rewriting the flag; a `judging` status |
| Providers and models per role in `config.toml`; API adapters on the standard library (S22, S23) | A cheap model for the parts, a strong one for verdicts; the helper has no dependency | Two tiers; vendor SDKs |
| A model with no price logs a null cost (S22) | No guessed price | A cost of 0, which reads as free |
| A cheap screen skips a part only on an explicit `read: false`; `chat` parts read in window mode (S29) | A skipped part can never be flagged; a chat API resends the whole history with no cache | No screen; conversation mode for every provider |
| Interface language from the browser (`es*` Spanish, else English); the flag file keeps `lang` and `spoken`; `-orig` caption tracks first (S26) | Works in tests; a translated track never wins | `chrome.i18n`; yt-dlp's `language` field |
| The owner's collector on Cloudflare Workers + D1, with hard stops per install id (S24, S28) | Free plan, one deploy, a D1 row holds a whole flag file | A hosted form or shared sheet; R2 |
| Nothing is shared before the person says yes once; each mark then sends itself; a mark given with sharing off never leaves (S27, S30) | Consent first; testers missed the send button | A send button; asking at install |
| A shared analysis is whole, served only after the owner approves it, and replaced only by a higher-ranked parts model (S28, S30) | Nobody can plant flags; the best reading wins | Serving every upload |
| The built extension ships in the helper package; ffmpeg comes from the imageio-ffmpeg wheel (S25) | A person needs no Node.js and no Homebrew | A committed `dist/`; Homebrew or apt |
| Only guests go on a card; the role comes from the speaker reading and the person corrects it (chat) | The card profiles the interviewee, not host against guest | Every speaker on the card |
| Severity in three levels by a rubric (materiality, centrality, magnitude; never intent) on each kept flag; a "Puntualización" stays its own verdict, apart from severity (chat) | Some misleading claims matter little, others a lot; the player and the card share one field | Confidence as a stand-in for severity |
| 🟢 **NEW · S35** The card follows the author's CALVET brand; its fonts ship in the helper, with no external font request (chat) | One look across the author's channels; the image renders offline | The S14 infographic |
| 🟢 **NEW · S37** The card links to the page of its approved analysis on the collector (chat) | The sources and the rubric behind each number are one click away | A per-video page in the helper, which nobody else can open |
| 🟢 **NEW · S35** No topic per claim; the card has no weakest topic (chat) | A topic field costs every part reading for one line of the card | A topic per claim in the part reading |
| 🟢 **NEW · S36** A comparison needs every flag of each person marked; rates per hour of speech; no score or ranking (chat) | A partial review would compare the reviewer's effort, not the speakers | A single score per person |

## Security

- The helper listens on `127.0.0.1` only. Only the extension service worker calls it, never a content script. A GET from the worker carries no `Origin` header, so the helper cannot identify the extension by origin.
- Keys (`FACT_CHECK_API_KEY`, `HF_TOKEN`, API keys) live in `~/.fact-checker/.env`, mode 600, written by `fact-checker key set` from a hidden prompt; never in code, committed config or chat. `doctor` names a missing key, never its value. The Google key is restricted to the Fact Check Tools API.
- Claude Code uses the person's own login; the helper never reads its credentials. 🟢 **NEW · S20** The same holds for Codex CLI and `~/.codex/auth.json`. An API key lives in the environment or `~/.fact-checker/.env`; the helper sends it only to its provider and never logs or prints it.
- Flag files and logs hold quotes from real videos: they stay in `~/.fact-checker/`, ignored by git.
- Nothing goes to the collector before the person says yes once (`share_marks`); see `PRIVACY.md`.
- The owner's routes of the collector need `ADMIN_TOKEN` (a Worker secret); the owner's helper keeps it as `FEEDBACK_ADMIN_TOKEN` in its `.env`. A stranger's upload stays pending until the owner approves it.
- The collector keeps no name, email, IP or path; an install id is a random UUID.
- `SECURITY.md` says how to report a problem.
