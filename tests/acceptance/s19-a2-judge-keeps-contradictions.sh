#!/usr/bin/env bash
# S19 A2 · The judge keeps a contradiction that it excused on the speaker's behalf
#
# Story: The person runs the judge check on the two analyses of the 1.5-hour interview of the S18 comparison. The judge reads each one
# again with the new rules. Each self-contradiction near 18:40, 55:05 or 39:40 that the analysis found is kept, not
# dropped, and the check prints the judge's verdict on each one.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) holds recall/<REAL_VIDEO>.json, the misses of a
# whole-video reading as minutes and kind only. RECALL_HOME holds the helper homes of the S18 comparison,
# RECALL_HOME/window and RECALL_HOME/conversation, each with the flag file, captions and voice turns of the video. The
# script copies each one into JUDGE_HOME/<mode> (else a new temporary folder), so the S18 verdicts stay untouched, and
# runs `fact-checker judge <REAL_VIDEO>` there: one Opus reading per mode. With --no-run, it scores the verdicts already
# in RECALL_HOME/<mode>. A contradiction is near a miss when it lies within 60 s of a minute of a contradiction miss.
# The script never prints a quote of the interview.
# Usage: RECALL_HOME=<dir> s19-a2-judge-keeps-contradictions.sh [--no-run]
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 1.5-hour interview in your helper home}"
modes="window conversation"
root=$(cd "$(dirname "$0")/../.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
misses="$home/recall/$video.json"
export PYTHONPATH="$root/src/helper"
[ -f "$misses" ] || { echo "FAIL S19 A2 · no misses list at $misses"; exit 1; }
[ -n "${RECALL_HOME:-}" ] && [ -d "$RECALL_HOME" ] || { echo "FAIL S19 A2 · set RECALL_HOME to the S18 comparison"; exit 1; }
scored="$RECALL_HOME"

# Case 1 · each S18 analysis, copied to its own helper home → the judge rules on it again with the current rules
if [ "${1:-}" != "--no-run" ]; then
  scored="${JUDGE_HOME:-$(mktemp -d)}"
  for mode in $modes; do
    for dir in videos/$video.json captions/$video voices/$video.turns.json; do
      [ -e "$RECALL_HOME/$mode/$dir" ] || { echo "FAIL S19 A2 · no $dir in $RECALL_HOME/$mode"; exit 1; }
      mkdir -p "$scored/$mode/$(dirname "$dir")"
      rm -rf "${scored:?}/$mode/$dir"
      cp -R "$RECALL_HOME/$mode/$dir" "$scored/$mode/$dir"
    done
    echo "judging $video in $scored/$mode"
    FACT_CHECKER_HOME="$scored/$mode" python3 -m fact_checker.cli judge "$video" \
      || { echo "FAIL S19 A2 · fact-checker judge exited non-zero for $mode"; exit 1; }
  done
fi

# Case 2 · every self-contradiction near a contradiction miss → the judge keeps it
python3 - "$scored" "$misses" "$video" $modes <<'PY'
import json, os, sys
scored, misses_path, video, *modes = sys.argv[1:]
second = lambda m: int(m.split(":")[0]) * 60 + int(m.split(":")[1])
minutes = [m for miss in json.load(open(misses_path)) if miss["kind"] == "contradiction" for m in miss["minutes"]]
near, kept = 0, 0
for mode in modes:
    flags = json.load(open(os.path.join(scored, mode, "videos", f"{video}.json")))["flags"]
    for f in flags:
        if f["type"] != "contradiction" or f["label"] != "self":
            continue
        miss = next((m for m in minutes if abs(f["t"] - second(m)) <= 60), None)
        verdict = f.get("judge", {}).get("verdict")
        print(f"{mode} {int(f['t'] // 60)}:{int(f['t'] % 60):02d} self-contradiction"
              f"{' near the ' + miss + ' miss' if miss else ''}: {verdict or 'not judged'}")
        if miss:
            near += 1
            kept += verdict == "keep"
print(f"kept {kept} of {near} self-contradictions near a miss")
if not near:
    print("FAIL S19 A2 · no self-contradiction near a miss to judge")
    sys.exit(1)
if kept < near:
    print("FAIL S19 A2 · the judge dropped a self-contradiction near a miss")
    sys.exit(1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S19 A2 · The judge keeps a contradiction that it excused on the speaker's behalf" \
  || echo "FAIL S19 A2 · see above"
exit $rc
