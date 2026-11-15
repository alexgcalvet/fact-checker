# Configuration

Everything here is optional. With no change, fact-checker reads with the Claude or ChatGPT subscription you are logged in to. Back to the [README](../README.md).

## Install by hand

| Step | Command |
|---|---|
| 1. Have an agent CLI logged in | [Claude Code](https://code.claude.com/docs/en/setup) (`claude auth login`) or [Codex](https://learn.chatgpt.com/docs/codex/cli) (`codex login`), and Google Chrome or Chromium |
| 2. Get the code | `git clone https://github.com/alexgcalvet/fact-checker && cd fact-checker` |
| 3. Install | `./install.sh`: uv, yt-dlp, ffmpeg (a static build, no Homebrew) and the helper, then `fact-checker setup` |
| 4. Load the extension | Chrome → `chrome://extensions` → Developer mode → Load unpacked → the folder that the installer names, `~/.fact-checker/extension` |
| 5. Check | `fact-checker doctor` (`--json` for an agent) |

- `./install.sh` skips each tool that is already there. A second run changes nothing.
- `fact-checker setup` checks the tools first. If one is missing, it prints the fix and installs nothing.
- `fact-checker setup` picks the logged-in subscription, Claude Code first, then Codex, and writes it in a new `~/.fact-checker/config.toml`. It never changes an existing one. See [Settings](#settings).
- `fact-checker setup` copies the built extension to `~/.fact-checker/extension`. You need no Node.js.
- On macOS, the helper runs as a launchd agent (`~/Library/LaunchAgents/com.fact-checker.helper.plist`, logs in `~/.fact-checker/server.log`). On Linux, it runs as a systemd user service (`systemctl --user status fact-checker`).
- After a change of PATH or a new tool, run `fact-checker setup` again.
- To update: `git pull`, then `uv tool install --reinstall ./src/helper` and `fact-checker setup`. Then click the reload icon of fact-checker in `chrome://extensions`.
- Developers: `cd src/extension && npm ci && npm run build` builds the extension into `src/helper/fact_checker/extension/`. Commit the result: the helper package ships it.


## Settings

Your settings live in the helper home, `~/.fact-checker/`, never in the repo:

| File | Holds | Example in the repo |
|---|---|---|
| `~/.fact-checker/config.toml` | the provider and the model of each step | [`src/helper/fact_checker/config.example.toml`](../src/helper/fact_checker/config.example.toml) |
| `~/.fact-checker/.env` | your keys, one `KEY=value` per line. Add one with `fact-checker key set <NAME>`: you type the key in a hidden prompt | [`src/helper/fact_checker/env.example`](../src/helper/fact_checker/env.example) |

1. Run `fact-checker setup`. It copies each example that you do not have yet. The settings file names the agent CLI you are logged in to and the author's feedback collector; every other line is a comment.
2. With those defaults, the helper reads with your Claude or ChatGPT subscription, and shares nothing until you say yes once (see [Share your marks](#share-your-marks)).
3. To change something, remove the `#` of its line and set your value.
4. Run `fact-checker setup` again to restart the helper.
5. Run `fact-checker doctor`. It prints the provider, model and address of each step, and names each missing key.


## Choose a provider

By default the helper reads with Claude Code on your Claude subscription. To use another provider, edit `~/.fact-checker/config.toml`. Every line is optional.

```toml
provider = "anthropic"     # claude | codex | anthropic | openai | chat
[models]                   # each missing step takes the provider's default
parts = "claude-sonnet-5-5"    # reads each part of the video
verdict = "claude-opus-5-5"    # turns the search evidence into verdicts
judge = "claude-opus-5-5"      # the whole-video judge pass
search = "claude-haiku-5-5"    # web search for figures
screen = "claude-haiku-5-5"    # decides which parts get the full reading
[openai]                   # only for an OpenAI-compatible API, such as xAI Grok
base_url = "https://api.x.ai/v1"
key_env = "XAI_API_KEY"
```

| Provider | Pays with | Needs | Default models (parts, verdict, judge / search, screen) |
|---|---|---|---|
| `claude` | Claude subscription | `claude auth login` | `opus` / `haiku` |
| `codex` | ChatGPT subscription | `codex login` | your plan's default model. Run `codex debug models` to see the models your plan allows |
| `anthropic` | Anthropic API key | `ANTHROPIC_API_KEY` in `~/.fact-checker/.env` | `claude-opus-5-5` / `claude-haiku-5-5` |
| `openai` | OpenAI or xAI API key | `OPENAI_API_KEY` (or the variable in `key_env`) in `~/.fact-checker/.env` | `gpt-6-astra` / `gpt-6-luna` |
| `chat` | any Chat Completions API: Hugging Face, OpenRouter, Groq, Together, DeepSeek, Mistral, or a local Ollama or LM Studio | its key in the variable of `key_env` (none on `localhost`), and `TAVILY_API_KEY` for the figure search | none: set each model; the screen uses the parts model |

- After a change, restart the helper with `fact-checker setup`. `fact-checker doctor` prints the provider, model and address of each step, and each missing key.
- A cheap model first screens each part, and only a part that may hold something worth a flag gets the full reading. Each screen reading is a `screen` line in the usage log, with `read` and its `reason`.
- With an API key, the usage log and the flag file show the real dollar cost. A model with no known price shows no cost.

### Any chat API

`chat` reads through `<base_url>/chat/completions` (default `http://localhost:11434/v1`, a local Ollama). It asks for JSON by a schema, and falls back to a plain JSON object on a server that does not support schemas. Each part is read with the 3 minutes before it and the positions list, not as one conversation, because a chat API resends the whole conversation every time. Such a model has no web search: to check a figure, the helper searches with [Tavily](https://tavily.com) (1,000 free searches a month) and the model reads the results. Without `TAVILY_API_KEY`, no figure is checked. `HF_TOKEN` in `.env` also turns on speaker separation.

```toml
provider = "chat"
[chat]
base_url = "https://router.huggingface.co/v1"
key_env = "HF_TOKEN"
[models]
parts = "<a model id>"
verdict = "<a model id>"
judge = "<a model id>"
search = "<a model id>"
```

### One provider per step

A `[roles.<step>]` table (`parts`, `verdict`, `judge`, `search` or `screen`) gives that step its own `provider`, `model`, `base_url` and `key_env`. A step without a table uses `provider` and `[models]`. `FACT_CHECK_PROVIDER` ignores the tables.

```toml
provider = "anthropic"
[roles.parts]
provider = "chat"
base_url = "https://router.huggingface.co/v1"
key_env = "HF_TOKEN"
model = "<a model id>"
```


## Optional keys

Put them in `~/.fact-checker/.env` (see [Settings](#settings)). The helper reads the file when it starts.

| Key | What it adds | Without it |
|---|---|---|
| `HF_TOKEN` | Speaker separation from the voices (pyannote). Accept the terms of `pyannote/speaker-diarization-community-1` on Hugging Face first | Claude tells the speakers apart from the text. On a measured one-hour interview, 88 % of flags named the speaker heard at that second, against 98 % with voices |
| `FACT_CHECK_API_KEY` | Published fact-checks (Google Fact Check Tools API) | Only web search |


## Videos without captions

The helper transcribes the audio on your machine: mlx-whisper on Apple silicon, faster-whisper on the CPU elsewhere (about 35 minutes for a one-hour video). The first run downloads a model of about 1.6 GB.


## Shared analyses

If you agreed to share, a whole analysis of a video goes to the author's collector. Once the author approves it, anyone who opens that video later with the interface in the same language sees the flags at once, for free, with the note **Análisis compartido · gratis** (**Shared analysis · free**). No transcript, mark, path or key travels: only the flags, the judge's verdicts, the provider and model, the languages, the cost and the helper version, with your random install id.

- An analysis is shared only when it read every second of the video. One that followed you past skipped stretches stays on your machine.
- An upload waits for the author's review, so nobody can plant fake flags for everyone. The author runs `fact-checker shared list`, then `fact-checker shared approve <video_id> <es|en>` or `reject`. The author's own uploads (with `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env`) are served at once.
- The ⚙ box **Compartir mis marcas y análisis** turns off both uploads: your marks and your analyses. Shared analyses still reach you with it off.
- A shared analysis in the other language is not used: click **Analizar este vídeo** to get one in yours.


## Share your marks

Your marks (correct or unfair) help the author make the detector better. Each card asks **¿Es justo este aviso?** (**Is this flag fair?**). Click **✓ De acuerdo** or **✗ No**. Nothing is shared by default: the first time you mark a card or click **Analizar este vídeo**, the player asks once whether to share your marks and analyses with the author, with a link to [PRIVACY.md](../PRIVACY.md). **Sí, compartir** sends that mark a moment later, and the next ones; **No** keeps everything on your machine. The foot of the side panel says which applies.

- To change your answer, open ⚙ in the side panel and tick or untick **Compartir mis marcas y análisis**. This writes `share_marks = false` in `~/.fact-checker/config.toml`. A mark that you give while sharing is off is never sent, even after you turn sharing on again.
- Only new or changed marks go out.

| Sent | Never sent |
|---|---|
| For each mark: the video id, the second, the flag type and label, the quote, the confidence, your verdict and reason, and the provider and model that made the flag | Your name, email, IP address, file paths or keys |
| The helper version and a random install id (`~/.fact-checker/install-id`), so the author can group the marks of one tester | |

- The marks go to `feedback_url` in `~/.fact-checker/config.toml`, set to the author's collector by `fact-checker setup`.
- If `feedback_url` is not set, nothing is sent. If the collector does not answer, the marks wait and go with your next mark or the next start of the helper.
- With no connection, run `fact-checker feedback send`. It sends your pending marks now, or writes them to `~/.fact-checker/feedback-<date>.json` and prints the path. Send that file to the author.
- `~/.fact-checker/feedback-sent.json` records what was sent. Delete it to send everything again.

For the author: the collector and its one-time deploy are in [`src/collector/README.md`](../src/collector/README.md). `fact-checker feedback pull` downloads the new marks to `~/.fact-checker/feedback/`, with `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env`.

