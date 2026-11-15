#!/usr/bin/env bash
# S5 A4 · The unfair cards of the person's marks are gone on a new analysis
#
# Story: The person's marks on the 112-minute interview hold 6 cards marked unfair (wrong speaker,
# a described hoax, another event) and 5 marked correct. After a new analysis of that interview, none of
# the 6 comes back, and at least 4 of the 5 do.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) with marks.jsonl; HF_TOKEN in the
# environment. With no argument, the script backs up the flag file of the video, starts a helper on a free
# local port and analyses the video again with the real YouTube, pyannote, Claude Code and Fact Check Tools
# API. With a flag file as argument, it only compares that file with the marks.
# A card comes back when a card of the new analysis has the same type, the same label for a fallacy, and
# at least half of the marked quote's words (as core/score.py matches).
# An evasion mark matches a question card (S7 moved evasion out of the fallacies).
# Usage: s5-a4-marks-regression.sh [flag-file]
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 112-minute interview in your helper home}"
root=$(cd "$(dirname "$0")/../.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
flags="${1:-}"

if [ -z "$flags" ]; then
  [ -n "${HF_TOKEN:-}" ] || { echo "FAIL S5 A4 · HF_TOKEN is not set"; exit 1; }
  file="$home/videos/$video.json"
  [ -f "$file" ] && mv "$file" "$home/videos/$video.$(date +%Y%m%d%H%M%S).json.bak"
  port=8796
  FACT_CHECKER_HOME="$home" PYTHONPATH="$root/src/helper" python3 -m fact_checker.server --port $port >/dev/null 2>&1 &
  pid=$!
  trap 'kill $pid 2>/dev/null' EXIT
  for _ in $(seq 1 50); do curl -s "http://127.0.0.1:$port/videos/$video" >/dev/null && break; sleep 0.2; done

  # Case 1 · the interview is analysed again to the end → status done
  curl -sf -X POST "http://127.0.0.1:$port/videos/$video?from=0" >/dev/null || { echo "FAIL S5 A4 · POST rejected"; exit 1; }
  for _ in $(seq 1 720); do
    status=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$file" 2>/dev/null)
    [ -n "$status" ] && [ "$status" != "running" ] && break
    sleep 10
  done
  flags="$file"
fi

# Case 2 · each of the 6 cards marked unfair → no card of the new analysis matches it
# Case 3 · the 5 cards marked correct → at least 4 come back
PYTHONPATH="$root/src/helper" python3 - "$flags" "$home/marks.jsonl" "$video" <<'PY'
import json, sys
from fact_checker.core.score import _matches
d = json.load(open(sys.argv[1]))
assert d["status"] == "done", f"status {d['status']} ({d['stop_reason']})"
cards = [f for f in d["flags"] if f.get("on_player")]
marks = {}
for line in open(sys.argv[2]):
    m = json.loads(line)
    if m["video_id"] == sys.argv[3]:
        marks[m["flag_id"]] = m
unfair = [m for m in marks.values() if m["verdict"] == "unfair"]
correct = [m for m in marks.values() if m["verdict"] == "correct"]
assert (len(unfair), len(correct)) == (6, 5), f"marks: {len(unfair)} unfair, {len(correct)} correct"
# Since S7 a dodged question is its own type: an evasion mark comes back as a question card.
as_flag = lambda m: m | {"type": "question"} if m["label"] == "evasion" else m
back = lambda m: [c for c in cards if _matches(c, as_flag(m))]
ok = True
for m in unfair:
    for c in back(m):
        ok = False
        print(f"FAIL S5 A4 · unfair card is back: {m['flag_id']} → {c['id']} [{c['speaker']}] {c['quote'][:80]}")
kept = [m for m in correct if back(m)]
for m in correct:
    if not back(m):
        print(f"lost correct card: {m['flag_id']} {m['quote'][:80]}")
if len(kept) < 4:
    ok = False
    print(f"FAIL S5 A4 · only {len(kept)} of 5 correct cards are back")
print(f"{len(cards)} cards; unfair back: {sum(bool(back(m)) for m in unfair)} of 6; correct back: {len(kept)} of 5")
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S5 A4 · The unfair cards of the person's marks are gone on a new analysis" || echo "FAIL S5 A4 · see above"
exit $rc
