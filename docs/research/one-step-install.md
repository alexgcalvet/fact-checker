# One-step install: research

Sources (read 2026-11-15):
- uv installation: https://docs.astral.sh/uv/getting-started/installation/
- uv installer reference: https://docs.astral.sh/uv/reference/installer/
- uv tools: https://docs.astral.sh/uv/concepts/tools/
- imageio-ffmpeg on PyPI: https://pypi.org/project/imageio-ffmpeg/ and https://github.com/imageio/imageio-ffmpeg
- Chrome, load an unpacked extension: https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world
- Claude Code setup: https://code.claude.com/docs/en/setup
- Codex CLI: https://learn.chatgpt.com/docs/codex/cli
- yt-dlp source, `yt_dlp/postprocessor/ffmpeg.py` (`get_audio_codec`), version 2026.10.26

## Findings

| Topic | Finding | Used for |
|---|---|---|
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` installs uv in the user executable directory (`~/.local/bin`) and may add it to the shell profiles. `UV_NO_MODIFY_PATH` turns that off | The installer installs uv only if `uv` is missing |
| uv tools | Tool executables are linked into the executable directory; `uv tool update-shell` adds it to PATH in the shell files; `uv tool dir --bin` prints it | yt-dlp, ffmpeg and `fact-checker` go there |
| uv archive source | Measured: `uv tool install "fact-checker @ <http url of a .tar.gz>#subdirectory=src/helper"` installs from an archive with no git. A `file://` archive does not work | The installer without a clone installs the helper from the GitHub archive of `main` |
| ffmpeg without Homebrew | imageio-ffmpeg 0.8.1 wheels hold an ffmpeg binary for macOS arm64 and x86-64, and Linux x86-64 and arm64 (glibc 2.28+). `imageio_ffmpeg.get_ffmpeg_exe()` returns its path. Measured on macOS arm64: ffmpeg 9.0, linked only to system frameworks. No ffprobe | The installer copies that binary to the tool executable directory as `ffmpeg` |
| yt-dlp without ffprobe | `get_audio_codec` runs `ffmpeg -i` when ffprobe is missing | `yt-dlp -x` works with this ffmpeg alone |
| Chrome | `chrome://extensions` → turn on "Developer mode" → "Load unpacked" → choose the folder. A change to the content scripts needs the reload icon. `chrome://` URLs are not linkable | The words that the agent tells the person |
| Claude Code | `curl -fsSL https://claude.ai/install.sh \| bash`; log in in the browser | The agent guide, when no agent CLI is there |
| Codex CLI | `curl -fsSL https://chatgpt.com/codex/install.sh \| sh`; first run offers "Sign in with ChatGPT" | The agent guide, for a ChatGPT subscription |
