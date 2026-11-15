#!/usr/bin/env bash
# S17 A4 · The 1.5-hour interview costs at most a third and catches as much
#
# Story: The person runs the cost check. It analyses the 1.5-hour interview again in a separate helper home and prints
# its cost: at most 7 dollars (it was about 20), with the high-importance misses caught no fewer than in the S16 run and
# a judge drop share no higher.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) holds recall/<REAL_VIDEO>.json, the misses
# of a whole-video reading as minutes and kind only, and the cached captions, voice turns, speech and audio of the
# video. The script copies those caches into a separate helper home (RECALL_HOME, else a new temporary folder) and
# runs the analysis there as the helper does (Helper._run from second 0). The person sets FACT_CHECK_API_KEY and
# HF_TOKEN in their own terminal. The run spends real Claude Code tool calls. With --no-run, the script only scores the
# flag file and usage log already in RECALL_HOME.
# The S16 run caught 4 of the 9 misses, and its judge dropped 30 of 69 non-context flags (43 %).
# A miss is caught when a flag that the judge did not drop lies within 60 s of one of its minutes and its type or label
# is the kind. The script never prints a quote of the interview.
# Usage: REAL_VIDEO=<id> RECALL_HOME=<dir> s17-a4-real-cost.sh [--no-run]
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 1.5-hour interview in your helper home}"
root=$(cd "$(dirname "$0")/../.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
run_home="${RECALL_HOME:-$(mktemp -d)}"
misses="$home/recall/$video.json"
export PYTHONPATH="$root/src/helper"
[ -f "$misses" ] || { echo "FAIL S17 A4 · no misses list at $misses"; exit 1; }
[ "$(cd "$run_home" 2>/dev/null && pwd -P)" = "$(cd "$home" && pwd -P)" ] \
  && { echo "FAIL S17 A4 · RECALL_HOME is the person's helper home"; exit 1; }

# Case 1 · the analysis in the separate helper home → it ends done
if [ "${1:-}" != "--no-run" ]; then
  [ -n "${FACT_CHECK_API_KEY:-}" ] && [ -n "${HF_TOKEN:-}" ] \
    || { echo "FAIL S17 A4 · set FACT_CHECK_API_KEY and HF_TOKEN, as the helper has them"; exit 1; }
  for dir in captions/$video voices/$video.turns.json speech/$video.words.json audio/$video; do
    if [ -e "$home/$dir" ] && [ ! -e "$run_home/$dir" ]; then
      mkdir -p "$run_home/$(dirname "$dir")"
      cp -R "$home/$dir" "$run_home/$dir"
    fi
  done
  rm -f "$run_home/videos/$video.json" "$run_home/claims.jsonl" "$run_home/usage.log"
  echo "analysing $video in $run_home"
  FACT_CHECKER_HOME="$run_home" python3 -c 'import os, sys; from pathlib import Path; from fact_checker.server import Helper
Helper(Path(os.environ["FACT_CHECKER_HOME"]))._run(sys.argv[1], 0)' "$video" \
    || { echo "FAIL S17 A4 · the analysis raised an error"; exit 1; }
fi

# Case 2 · the usage log → the cost of the video, split by step, is at most 7 dollars
# Case 3 · the new flags → at least 4 of the 9 misses caught, as in the S16 run
# Case 4 · the judge → drops no more than 43 % of the non-context flags, as in the S16 run
python3 - "$run_home" "$misses" "$video" <<'PY'
import collections, json, os, sys
run_home, misses_path, video = sys.argv[1:]
path = os.path.join(run_home, "videos", f"{video}.json")
if not os.path.exists(path):
    print(f"FAIL S17 A4 · no flag file in {run_home}")
    sys.exit(1)
d = json.load(open(path))
ok = True
if d["status"] != "done":
    ok = False
    print(f"FAIL S17 A4 · the analysis ended {d['status']} ({d.get('stop_reason')})")

usage_path = os.path.join(run_home, "usage.log")
lines = [json.loads(l) for l in open(usage_path)] if os.path.exists(usage_path) else []
lines = [l for l in lines if l["video_id"] == video]
by_step = collections.defaultdict(lambda: [0, 0.0])
for l in lines:
    by_step[l["step"]][0] += 1
    by_step[l["step"]][1] += l.get("cost_usd") or 0
for step, (n, cost) in sorted(by_step.items(), key=lambda kv: -kv[1][1]):
    print(f"{step}: {n} readings, {cost:.2f} USD")
total = d.get("cost_usd")
print(f"cost: {total} USD in the flag file; {sum(c for _, c in by_step.values()):.2f} USD in the usage log")
if not isinstance(total, (int, float)) or total <= 0:
    ok = False
    print("FAIL S17 A4 · the flag file has no cost")
elif total > 7:
    ok = False
    print("FAIL S17 A4 · the video costs more than 7 dollars")

flags = [f for f in d["flags"] if f["type"] != "context"]
if not any("judge" in f for f in flags):
    ok = False
    print("FAIL S17 A4 · the judge ruled on no flag")
dropped = lambda f: f.get("judge", {}).get("verdict") == "drop"
claims_path = os.path.join(run_home, "claims.jsonl")
claims = [json.loads(l) for l in open(claims_path)] if os.path.exists(claims_path) else []
claims = [c for c in claims if c["video_id"] == video]
second = lambda m: int(m.split(":")[0]) * 60 + int(m.split(":")[1])
caught, misses = 0, json.load(open(misses_path))
for miss in misses:
    near = lambda t: any(abs(t - second(m)) <= 60 for m in miss["minutes"])
    hits = [f for f in flags if near(f["t"]) and miss["kind"] in (f["type"], f["label"])]
    kept = [f for f in hits if not dropped(f)]
    caught += bool(kept)
    state = "caught" if kept else "dropped by the judge" if hits else "missed"
    nearby = collections.Counter(c["outcome"] for c in claims if near(c["t"]))
    print(f"{'/'.join(miss['minutes'])} {miss['kind']}: {state}; claims within 60 s: {dict(nearby) or 'none'}")
share = sum(map(dropped, flags)) / len(flags) if flags else 0
print(f"caught: {caught} of {len(misses)}; judge drops {sum(map(dropped, flags))} of {len(flags)} non-context flags"
      f" ({round(100 * share)} %)")
print(f"claims log: {len(claims)} claims, {dict(collections.Counter(c['outcome'] for c in claims))}")
if caught < 4:
    ok = False
    print(f"FAIL S17 A4 · fewer than 4 of {len(misses)} misses caught")
if round(100 * share) > 43:
    ok = False
    print("FAIL S17 A4 · the judge drops more than 43 % of the flags")
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S17 A4 · The 1.5-hour interview costs at most a third and catches as much" \
  || echo "FAIL S17 A4 · see above"
exit $rc
