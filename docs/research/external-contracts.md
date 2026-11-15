# External contracts (S0)

**Sources**
- yt-dlp 2026.10.26, run by hand on 2026-11-13 against one public Spanish interview (112 min, auto captions only). No transcript text is kept.
- Claude Code 2.1.325, `claude --help` and two headless runs on 2026-11-13.
- Google Fact Check Tools API reference: https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search, https://developers.google.com/fact-check/tools/api, https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims (read 2026-11-13), and three live calls on 2026-11-13.

## Summary

| System | Status | Key finding |
|---|---|---|
| YouTube via yt-dlp | confirmed | Spanish auto captions in `json3` with word timings; `upload_date` as `YYYYMMDD` |
| Claude Code (`claude -p`) | confirmed, except usage limits | `--json-schema` returns `structured_output`; WebSearch works headless with `allowed_domains`; no source date |
| Google Fact Check Tools API | confirmed, except quotas | `GET claims:search` with a header key; ratings are free text |
| Whisper (mlx-whisper) | confirmed | Word timings from audio, about 7× real time on an M3; no auth |
| Headless Chrome | confirmed | HTML page to a PNG of a fixed size in about 1 s |

## YouTube via yt-dlp

| Item | Finding |
|---|---|
| What we call | `yt-dlp --no-simulate --skip-download --write-auto-subs --sub-langs es --sub-format json3 --print upload_date -o <dir>/%(id)s <url>`; metadata with `--dump-json --skip-download` |
| Gotcha | `--print` implies simulation: without `--no-simulate` no caption file is written |
| Auth | None |
| Contract source | yt-dlp output, observed |
| Captions | The test video had no manual Spanish captions, only auto captions. Two tracks: `es-orig` (original speech recognition) and `es`. Prefer `es-orig` |
| Formats | `json3`, `srv1`, `srv2`, `srv3`, `ttml`, `srt`, `vtt` |
| `json3` shape | `{wireMagic, pens, wsWinStyles, wpWinPositions, events[]}`; each event `{tStartMs, dDurationMs, wWinId, aAppend?, segs[]}`; each seg `{utf8, tOffsetMs?, acAsrConf?}`. Word time = `tStartMs + tOffsetMs` |
| Metadata | `upload_date` (`20261113`), `duration` (seconds), `language` (`es`), `live_status` (`not_live`) |
| Size | 112 min → 7,068 events, ~22,000 words, 2.4 MB file (about 12,000 words per hour) |
| No speaker | Captions carry no speaker field |
| Errors | Not observed yet (missing captions, blocks, rate limits). Record them when they happen |

## Claude Code (`claude -p`)

| Item | Finding |
|---|---|
| What we call | `claude -p <prompt> --output-format json --json-schema <schema> [--allowedTools WebSearch]` |
| Auth | The person's Claude Code login (subscription). The helper never reads credentials |
| Output | One JSON object: `type: "result"`, `subtype: "success"`, `is_error`, `result` (string), `structured_output` (object, when `--json-schema` is set), `num_turns`, `duration_ms`, `usage`, `total_cost_usd`, `permission_denials`, `api_error_status` |
| Timing | Plain answer: 1.5 s, 1 turn. Web search with schema: 13.6 s, 4 turns |
| Web search | Works headless with `--allowedTools WebSearch`. Restricting to `ine.es` through `allowed_domains` in the prompt worked |
| Source date | Web search returned the source URL but no publish date (`source_date: null`). A date needs a fetch of the page or comes from the published fact-check |
| Other flags | `--model`, `--fallback-model`, `--max-budget-usd`, `--append-system-prompt`, `--bare` |
| Usage limits | Not documented by `--help`; not hit. Watch `is_error` and `api_error_status` |

## Google Fact Check Tools API

| Item | Finding |
|---|---|
| What we call | `GET https://factchecktools.googleapis.com/v1alpha1/claims:search` |
| Parameters | `query` (required unless `reviewPublisherSiteFilter`), `languageCode` (BCP-47, e.g. `es`), `reviewPublisherSiteFilter`, `maxAgeDays`, `pageSize` (default 10), `pageToken`, `offset` |
| Auth | An API key restricted to this API, in the `X-goog-api-key` header (works, observed). Project `fact-checker-514622`, key `fact-checker-helper`. The helper reads `FACT_CHECK_API_KEY` from the gitignored `.env` |
| Response | `{claims[], nextPageToken}`; claim `{text, claimant, claimDate, claimReview[]}`; review `{publisher{name, site}, url, title, reviewDate, textualRating, languageCode}` (observed matches the docs) |
| Sample | `query=paro juvenil`, `languageCode=es`, `pageSize=20`: 20 claims, 19 reviewed by `newtral.es`; ratings in Spanish free text: `Engañoso` 10, `Verdad a medias` 5, `Falso` 5 |
| Ratings | `textualRating` is free text in the reviewer's language, not an enum. The pipeline must map it to a verdict |
| Dates | `claimDate` and `reviewDate` are RFC 3339 UTC; they give the date that the flag needs |
| Quotas | Not documented; not hit |
| Errors | Google RPC error body `{error: {code, message, status, details[]}}`. Invalid key: HTTP 400, "API key not valid". Missing `query`: HTTP 400 `INVALID_ARGUMENT`, "must have either query or filter" |
| Stability | `v1alpha1`; no statement on stability |

## Chrome extension platform (Manifest V3)

**Sources**: https://developer.chrome.com/docs/extensions/develop/concepts/network-requests, https://developer.chrome.com/blog/local-network-access (2025-06-09, updated 2025-09-29), https://developer.chrome.com/docs/extensions/develop/concepts/messaging, https://developer.chrome.com/docs/extensions/develop/concepts/declare-permissions, https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns (read 2026-11-13).

| Item | Finding |
|---|---|
| Content script fetch to `127.0.0.1` | Runs as the page origin (`https://www.youtube.com`): subject to CORS and to Local Network Access (LNA), and maybe to mixed-content blocking. Avoid it |
| Service worker fetch | Documented: with `"host_permissions": ["http://127.0.0.1/*"]` the extension service worker may fetch servers outside its origin. The pattern matches all ports |
| Pattern | Content script → `chrome.runtime.sendMessage` → service worker `fetch` → reply. Never let the content script choose the URL; validate messages in the worker |
| LNA | The permission prompt launched in Chrome 142. The docs say nothing on extensions: whether a service worker with host permission is exempt is **not documented** |
| Spike (2026-11-13) | A throwaway extension on a real youtube.com video: the service worker GET to `http://127.0.0.1:8765` succeeded with no LNA prompt and no CORS headers on the server |
| Origin header | The service worker GET arrived with **no `Origin` header**: the helper cannot tell the extension apart by Origin on a GET. POST was not tried |
| Status | confirmed for GET from the service worker |

## Voice separation: pyannote (Hugging Face)

**Sources**: https://huggingface.co/pyannote/speaker-diarization-community-1 (model card, read 2026-11-14); one run by hand on 2026-11-14 on the audio of one public 14-minute Spanish interview.

| Item | Finding |
|---|---|
| What we call | `Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=HF_TOKEN)`, then `pipeline("audio.wav").speaker_diarization` → `(turn.start, turn.end, speaker)` |
| Library | `pyannote.audio` 4.0.7 with torch 2.15, Python 3.12, in its own environment |
| Auth | Gated model: the person accepted the conditions (contact shared with pyannote); a read token `fact-checker-helper` in `HF_TOKEN` in `.env` |
| Runs | On the laptop, offline after the first download; Apple M3 with `mps` |
| Speed | 14 minutes of audio: 21 s to load, 82 s to separate (about 10× real time). A 112-minute video: about 11 minutes, estimated |
| Quality | 2 main voices found, as expected, plus one 2-second voice (noise); 2 of 2,990 caption words fell outside any turn; the questions fell on the host's voice; turn edges blur where both talk at once |
| Errors and limits | Not observed yet |

## YouTube audio via yt-dlp

| Item | Finding |
|---|---|
| What we call | `yt-dlp -x --audio-format wav --postprocessor-args "ffmpeg:-ac 1 -ar 16000" -o <dir>/%(id)s.%(ext)s <url>` (needs ffmpeg) |
| Output | 16 kHz mono WAV, 27 MB for 14 minutes; kept in the helper home, never in the repo |

## Speech to text: Whisper on Apple silicon (mlx-whisper)

**Sources**: https://github.com/ml-explore/mlx-examples/tree/main/whisper and https://huggingface.co/mlx-community/whisper-large-v3-turbo (read 2026-11-14); runs by hand on 2026-11-14 on the audio of one public 14-minute Spanish interview. No transcript text is kept.

| Item | Finding |
|---|---|
| What we call | `mlx_whisper.transcribe(wav, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="es", word_timestamps=True)` → `segments[].words[]` with `word`, `start`, `end`, `probability` |
| Library | `mlx-whisper` (latest on PyPI, 2026-11-14), in its own `uv run --script` environment; Apple silicon only |
| Auth | None: the model is public; 1.6 GB downloaded on the first run (55 s) |
| Runs | On the laptop, offline after the first download; Apple M3 |
| Speed | 2 minutes: 15 s; 14 minutes: 118 s (about 7× real time). A 112-minute video: about 16 minutes, estimated |
| Quality | 2,906 words for 14 minutes, against 2,990 caption words; words carry a leading space; low `probability` on the first words |
| Errors and limits | Not observed yet |

## HTML to PNG: headless Chrome

**Sources**: https://developer.chrome.com/docs/chromium/headless (read 2026-11-14); one run by hand on 2026-11-14 with Google Chrome 157 on macOS.

| Item | Finding |
|---|---|
| What we call | `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --hide-scrollbars --screenshot=<out.png> --window-size=1080,1350 file://<page.html>` |
| Output | A PNG of exactly the window size (1080×1350), in about 1 s; Spanish accents, «», ✗ ⚑ ? ⇄ ℹ ≈ render with system fonts |
| Auth | None; the person's installed Chrome |
| Errors and limits | Prints a harmless `CVDisplayLinkCreateWithCGDisplay failed` line on stderr; exit code 0 |
