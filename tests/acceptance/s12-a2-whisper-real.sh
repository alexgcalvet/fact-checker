#!/usr/bin/env bash
# S12 A2 · Whisper turns real audio into timed words
#
# Story: The person runs the check on the 14-minute interview used in S1, through the audio path. It
# prints the number of words, at least 2,000, with times that only go up and end before the video ends.
#
# Setup: Apple silicon, a temporary helper home, the real YouTube audio through the YouTube adapter and
# the real Whisper adapter. Usage: s12-a2-whisper-real.sh <youtube-url>
set -u
url="${1:?usage: $0 <youtube-url>}"
root=$(cd "$(dirname "$0")/../.." && pwd)
id=$(printf '%s' "$url" | sed -E 's/.*[?&]v=([^&]+).*/\1/')
home=$(mktemp -d)
trap 'rm -rf "$home"' EXIT

# Case 1 · the audio of the video is transcribed → at least 2,000 words
# Case 2 · the words in order → their seconds only go up, from 0, and the last one is before the video ends
# Case 3 · the audio and the transcript → kept in the helper home, not in the repo
PYTHONPATH="$root/src/helper" python3 - "$id" "$home" "$root" <<'PY'
import re, subprocess, sys, wave
from pathlib import Path
from fact_checker.adapters.whisper import Whisper
from fact_checker.adapters.youtube import YouTube
video, home, root = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
audio = YouTube(home / "audio")
segments = Whisper(home / "speech", audio).segments(video)
with wave.open(str(audio.audio(video))) as w:
    duration = w.getnframes() / w.getframerate()
times = [s.t for s in segments]
print(f"{len(segments)} words, {times[0]:.1f}-{times[-1]:.1f} s of {duration:.0f} s")
assert len(segments) >= 2000, f"only {len(segments)} words"
assert all(s.text.strip() for s in segments), "empty word"
assert times == sorted(times) and times[0] >= 0, "times go down"
assert times[-1] < duration, f"last word at {times[-1]} after the end {duration}"
assert list(home.rglob("*.wav")) and list((home / "speech").glob("*")), "audio or transcript not in the helper home"
dirty = subprocess.run(["git", "-C", root, "status", "--porcelain", "--untracked-files=all"],
                       capture_output=True, text=True).stdout
assert not re.search(r"\.wav$|words\.json$", dirty, re.M), f"audio or transcript in the repo:\n{dirty}"
PY
rc=$?
[ $rc = 0 ] && echo "PASS S12 A2 · Whisper turns real audio into timed words" || echo "FAIL S12 A2 · see above"
exit $rc
