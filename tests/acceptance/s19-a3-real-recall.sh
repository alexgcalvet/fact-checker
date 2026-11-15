#!/usr/bin/env bash
# S19 A3 · The live analysis catches 5 of the 9 misses on the 1.5-hour interview
#
# Story: The person runs the recall check. It analyses the 1.5-hour interview from the start in a separate helper home,
# the way the helper now does by default. It prints each of the 9 high-importance misses as caught, dropped by the
# judge or missed, the share of flags the judge drops and the cost. It exits 0 with at least 5 of 9 caught, at most
# 32 % dropped and at most 9 dollars.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) holds recall/<REAL_VIDEO>.json, the misses of a
# whole-video reading as minutes and kind only. RUN_HOME (else a new temporary folder) is the helper home of the run.
# The script copies the cached captions, voice turns, speech and audio of the video into it, from CACHE_HOME if set,
# else from the person's helper home, and runs the analysis there as the helper does with no extension
# (Helper._run from second 0, its default context mode: the whole video). The person sets FACT_CHECK_API_KEY and
# HF_TOKEN in their own terminal. The run spends real Claude Code tool calls (about 8 dollars).
# The run used the conversation mode when its usage log shows the part readings in at most a few sessions.
# With --no-run, the script only scores the flag file and usage log already in RUN_HOME.
# A miss is caught when a flag that the judge did not drop lies within 60 s of one of its minutes and its type or label
# is the kind. The script never prints a quote of the interview.
# Usage: REAL_VIDEO=<id> RUN_HOME=<dir> s19-a3-real-recall.sh [--no-run]
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 1.5-hour interview in your helper home}"
root=$(cd "$(dirname "$0")/../.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
run_home="${RUN_HOME:-$(mktemp -d)}"
cache="${CACHE_HOME:-$home}"
misses="$home/recall/$video.json"
export PYTHONPATH="$root/src/helper"
[ -f "$misses" ] || { echo "FAIL S19 A3 · no misses list at $misses"; exit 1; }
[ "$(cd "$run_home" 2>/dev/null && pwd -P)" = "$(cd "$home" && pwd -P)" ] \
  && { echo "FAIL S19 A3 · RUN_HOME is the person's helper home"; exit 1; }

# Case 1 · the analysis in a separate helper home, in the default context mode → it ends done
if [ "${1:-}" != "--no-run" ]; then
  [ -n "${FACT_CHECK_API_KEY:-}" ] && [ -n "${HF_TOKEN:-}" ] \
    || { echo "FAIL S19 A3 · set FACT_CHECK_API_KEY and HF_TOKEN, as the helper has them"; exit 1; }
  for dir in captions/$video voices/$video.turns.json speech/$video.words.json audio/$video; do
    if [ -e "$cache/$dir" ] && [ ! -e "$run_home/$dir" ]; then
      mkdir -p "$run_home/$(dirname "$dir")"
      cp -R "$cache/$dir" "$run_home/$dir"
    fi
  done
  rm -f "$run_home/videos/$video.json" "$run_home/claims.jsonl" "$run_home/usage.log"
  echo "analysing $video in $run_home"
  FACT_CHECKER_HOME="$run_home" python3 -c 'import os, sys; from pathlib import Path; from fact_checker.server import Helper
Helper(Path(os.environ["FACT_CHECKER_HOME"]))._run(sys.argv[1], 0)' "$video" \
    || { echo "FAIL S19 A3 · the analysis raised an error"; exit 1; }
fi

# Case 2 · the run → ended done, in the conversation mode, with the cost split by step
# Case 3 · the flags → at least 5 of the 9 misses caught, the judge drops at most 32 %, the run costs at most 9 dollars
python3 - "$run_home" "$misses" "$video" <<'PY'
import collections, json, os, sys
run_home, misses_path, video = sys.argv[1:]
second = lambda m: int(m.split(":")[0]) * 60 + int(m.split(":")[1])
path = os.path.join(run_home, "videos", f"{video}.json")
if not os.path.exists(path):
    print(f"FAIL S19 A3 · no flag file in {run_home}")
    sys.exit(1)
d = json.load(open(path))
ok = True
if d["status"] != "done":
    ok = False
    print(f"FAIL S19 A3 · the analysis ended {d['status']} ({d.get('stop_reason')})")
usage_path = os.path.join(run_home, "usage.log")
lines = [json.loads(l) for l in open(usage_path)] if os.path.exists(usage_path) else []
lines = [l for l in lines if l["video_id"] == video]
parts = [l for l in lines if l["step"] == "analyze_chunk"]
sessions = {l.get("session") for l in parts}
if not parts or None in sessions or len(sessions) > len(parts) / 2:
    ok = False
    print(f"FAIL S19 A3 · the part readings are not one conversation: {len(sessions)} sessions for {len(parts)} readings")
by_step = collections.defaultdict(collections.Counter)
for l in lines:
    by_step[l["step"]]["readings"] += 1
    by_step[l["step"]]["cost"] += l.get("cost_usd") or 0
for step, s in sorted(by_step.items(), key=lambda kv: -kv[1]["cost"]):
    print(f"{step}: {s['readings']} readings, {s['cost']:.2f} USD")
flags = [f for f in d["flags"] if f["type"] != "context"]
if not any("judge" in f for f in flags):
    ok = False
    print("FAIL S19 A3 · the judge ruled on no flag")
dropped = lambda f: f.get("judge", {}).get("verdict") == "drop"
caught, misses = 0, json.load(open(misses_path))
for miss in misses:
    near = lambda t: any(abs(t - second(m)) <= 60 for m in miss["minutes"])
    hits = [f for f in flags if near(f["t"]) and miss["kind"] in (f["type"], f["label"])]
    kept = [f for f in hits if not dropped(f)]
    caught += bool(kept)
    found = ", ".join(f"{f['type']}/{f['label']}" for f in flags if near(f["t"])) or "none"
    print(f"{'/'.join(miss['minutes'])} {miss['kind']}: "
          f"{'caught' if kept else 'dropped by the judge' if hits else 'missed'}; flags within 60 s: {found}")
share = 100 * sum(map(dropped, flags)) / len(flags) if flags else 0
cost = d.get("cost_usd") or 0
print(f"caught {caught} of {len(misses)}; judge drops {sum(map(dropped, flags))} of {len(flags)} non-context flags"
      f" ({share:.1f} %); cost {cost:.2f} USD")
if caught < 5:
    ok = False
    print(f"FAIL S19 A3 · fewer than 5 of {len(misses)} misses caught")
if share > 32:
    ok = False
    print("FAIL S19 A3 · the judge drops more than 32 % of the flags")
if cost > 9:
    ok = False
    print("FAIL S19 A3 · the run costs more than 9 dollars")
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S19 A3 · The live analysis catches 5 of the 9 misses on the 1.5-hour interview" \
  || echo "FAIL S19 A3 · see above"
exit $rc
