#!/bin/sh
# Installs fact-checker on macOS or Linux: uv, yt-dlp, ffmpeg, the helper, then `fact-checker setup`.
# Each step runs only if its command is missing, so a second run changes nothing. It never calls sudo.
# From a clone: ./install.sh. Without a clone: curl -fsSL <repo>/raw/main/install.sh | sh
set -eu

REPO="${FACT_CHECKER_REPO:-https://github.com/alexgcalvet/fact-checker}"
HERE=$(dirname "$0")
if [ -d "$HERE/src/helper" ]; then
  HELPER=$(cd "$HERE/src/helper" && pwd)
else
  HELPER="fact-checker @ $REPO/archive/refs/heads/main.tar.gz#subdirectory=src/helper"
fi

has() { command -v "$1" >/dev/null 2>&1; }
# The uv installer and uv tools use ~/.local/bin, which a shell opened before them may not have on PATH.
PATH="$HOME/.local/bin:$PATH"

if has uv; then
  echo "uv: already there"
else
  echo "uv: installing"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv tool update-shell >/dev/null 2>&1 || true
BIN=$(uv tool dir --bin)
PATH="$BIN:$PATH"
export PATH

if has yt-dlp; then
  echo "yt-dlp: already there"
else
  echo "yt-dlp: installing"
  uv tool install yt-dlp
fi

if has ffmpeg; then
  echo "ffmpeg: already there"
else
  echo "ffmpeg: installing (a static build from the imageio-ffmpeg wheel)"
  FFMPEG=$(uv run --no-project --quiet --with imageio-ffmpeg python -I -c \
    "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
  mkdir -p "$BIN"
  cp "$FFMPEG" "$BIN/ffmpeg"
  chmod 755 "$BIN/ffmpeg"
fi

if has fact-checker; then
  echo "helper: already there"
else
  echo "helper: installing"
  uv tool install "$HELPER"
fi

fact-checker setup
