#!/usr/bin/env bash
# S34 A4 · The judge spreads the 1.5-hour interview over the three levels
#
# Story: The person runs the severity check. It judges a copy of the 1.5-hour interview again in a separate helper
# home and prints how many kept flags fall in each level, and the minute, label and reason of each serious one. It
# exits 0 when each level holds at least one flag and serious ones are at most a third of the kept flags.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) holds the analysed flag file of REAL_VIDEO,
# its cached captions (or Whisper words) and voice turns, and config.toml. The script copies them into JUDGE_HOME (else a new temporary
# folder), so the person's verdicts stay untouched, and runs `fact-checker judge <REAL_VIDEO>` there: one real Opus
# reading per started two video-hours. The key comes from the person's environment or the .env of the helper home.
# With --no-run, it scores the verdicts already in JUDGE_HOME. A kept flag is one with the verdict "keep". The script
# prints reasons but never a quote of the interview.
# Usage: REAL_VIDEO=<id> [JUDGE_HOME=<dir>] s34-a4-real-severity.sh [--no-run]
set -u
video="${REAL_VIDEO:-}"
if [ -z "$video" ]; then
  echo "usage: REAL_VIDEO=<id> [JUDGE_HOME=<dir>] $0 [--no-run]"
  echo "FAIL S34 A4 · set REAL_VIDEO to the id of the 1.5-hour interview in your helper home"
  exit 1
fi
root=$(cd "$(dirname "$0")/.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
export PYTHONPATH="$root/src/helper"

# Case 1 · a copy of the interview in its own helper home → the judge rules on it again with the severity rubric
if [ "${1:-}" != "--no-run" ]; then
  scored="${JUDGE_HOME:-$(mktemp -d)}"
  [ -e "$home/captions/$video" ] || [ -e "$home/speech/$video.words.json" ] \
    || { echo "FAIL S34 A4 · no captions/$video or speech/$video.words.json in $home"; exit 1; }
  for path in videos/$video.json captions/$video speech/$video.words.json speech/$video.words.lang \
      voices/$video.turns.json config.toml .env; do
    [ -e "$home/$path" ] || case "$path" in
      videos/*) echo "FAIL S34 A4 · no $path in $home"; exit 1 ;;
      *) continue ;;
    esac
    mkdir -p "$scored/$(dirname "$path")"
    rm -rf "${scored:?}/$path"
    cp -R "$home/$path" "$scored/$path"
  done
  echo "judging $video in $scored"
  FACT_CHECKER_HOME="$scored" python3 -m fact_checker.cli judge "$video" \
    || { echo "FAIL S34 A4 · fact-checker judge exited non-zero"; exit 1; }
else
  scored="${JUDGE_HOME:?with --no-run, set JUDGE_HOME to the copy that was judged}"
fi

# Case 2 · the kept flags → at least one in each level
# Case 3 · the serious flags → at most a third of the kept flags, each printed with its minute, label and reason
python3 - "$scored/videos/$video.json" <<'PY'
import json, sys
flags = json.load(open(sys.argv[1]))["flags"]
kept = [f for f in flags if f.get("judge", {}).get("verdict") == "keep"]
levels = {level: [f for f in kept if f["judge"].get("severity") == level] for level in ("minor", "moderate", "serious")}
unrated = len(kept) - sum(len(fs) for fs in levels.values())
print(f"kept {len(kept)}: " + ", ".join(f"{len(fs)} {level}" for level, fs in levels.items()) + f", {unrated} with no severity")
for f in levels["serious"]:
    print(f"  serious {int(f['t'] // 60)}:{int(f['t'] % 60):02d} {f['label']}: {f['judge']['reason']}")
ok = True
empty = [level for level, fs in levels.items() if not fs]
if empty:
    ok = False
    print(f"FAIL S34 A4 · no kept flag is {', '.join(empty)}")
if len(levels["serious"]) * 3 > len(kept):
    ok = False
    print(f"FAIL S34 A4 · {len(levels['serious'])} serious of {len(kept)} kept is more than a third")
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S34 A4 · The judge spreads the 1.5-hour interview over the three levels" \
  || echo "FAIL S34 A4 · see above"
exit $rc
