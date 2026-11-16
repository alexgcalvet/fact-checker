#!/usr/bin/env bash
# S5 A1 · The voices of a real video are separated and named
#
# Story: The person asks the helper for the 14-minute interview used in S1. When it ends, the flag file
# names two voices, the host and the guest, by name or role, and every card names one of them.
#
# Setup: HF_TOKEN in the environment, a temporary helper home, the helper on a free local port, the real
# YouTube, pyannote and Claude Code. Usage: s5-a1-voices-named.sh <youtube-url>
set -u
url="${1:?usage: $0 <youtube-url>}"
[ -n "${HF_TOKEN:-}" ] || { echo "FAIL S5 A1 · HF_TOKEN is not set"; exit 1; }
root=$(cd "$(dirname "$0")/.." && pwd)
id=$(printf '%s' "$url" | sed -E 's/.*[?&]v=([^&]+).*/\1/')
home=$(mktemp -d)
port=8797
trap 'kill $pid 2>/dev/null; rm -rf "$home"' EXIT

FACT_CHECKER_HOME="$home" PYTHONPATH="$root/src/helper" python3 -m fact_checker.server --port $port >"$home/server.out" 2>&1 &
pid=$!
for _ in $(seq 1 50); do curl -s "http://127.0.0.1:$port/videos/$id" >/dev/null && break; sleep 0.2; done

# Case 1 · the video is analysed to the end → status done
curl -sf -X POST "http://127.0.0.1:$port/videos/$id?from=0" >/dev/null || { echo "FAIL S5 A1 · POST rejected"; exit 1; }
for _ in $(seq 1 480); do
  status=$(curl -sf "http://127.0.0.1:$port/videos/$id" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' 2>/dev/null)
  [ "$status" = "running" ] || break
  sleep 5
done
curl -sf "http://127.0.0.1:$port/videos/$id" > "$home/flags.json"

# Case 2 · the flag file names two voices → each by a name or a role, not a voice id
# Case 3 · the analysis made cards → every card names one of the two voices
# Case 4 · the audio and the voice turns → kept in the helper home, not in the repo
python3 - "$home/flags.json" "$home" "$root" <<'PY'
import json, re, subprocess, sys
from pathlib import Path
d = json.load(open(sys.argv[1]))
assert d["status"] == "done", f"status {d['status']} ({d['stop_reason']})"
names = d.get("speakers") or {}
assert len(names) == 2 and len(set(names.values())) == 2, f"voices named: {names}"
for voice, name in names.items():
    assert name.strip() and not re.fullmatch(r"SPEAKER_\d+", name), f"voice {voice} not named: {name!r}"
assert d["flags"], "no card in a 14-minute interview"
for f in d["flags"]:
    assert f["speaker"] in names.values(), f"card speaker {f['speaker']!r} is not one of {list(names.values())}"
home = Path(sys.argv[2])
assert list(home.rglob("*.wav")), "no audio in the helper home"
dirty = subprocess.run(["git", "-C", sys.argv[3], "status", "--porcelain", "--untracked-files=all"],
                       capture_output=True, text=True).stdout
assert not re.search(r"\.(wav|json3)$|turns", dirty, re.M), f"audio or turns in the repo:\n{dirty}"
print(f"voices: {names}; {len(d['flags'])} cards")
PY
rc=$?
[ $rc = 0 ] && echo "PASS S5 A1 · The voices of a real video are separated and named" || echo "FAIL S5 A1 · see above"
exit $rc
