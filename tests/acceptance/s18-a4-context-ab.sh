#!/usr/bin/env bash
# S18 A4 · The cheaper context mode wins on the 1.5-hour interview
#
# Story: The person runs the comparison check. It analyses the 1.5-hour interview from the start, once per context mode,
# each in a separate helper home, and prints per mode the cost, the high-importance misses caught and the share of flags
# the judge drops. It exits 0 when the cheaper mode costs at most 6 dollars, catches at least 4 of the 9 misses and the
# judge drops at most 43 %; it prints which mode won.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) holds recall/<REAL_VIDEO>.json, the misses of a
# whole-video reading as minutes and kind only. RECALL_HOME (else a new temporary folder) holds one helper home per
# mode, RECALL_HOME/window and RECALL_HOME/conversation. The script copies the cached captions, voice turns, speech and
# audio of the video into each mode's home, from RECALL_HOME/cache if it exists, else from the person's helper home.
# It runs the two analyses one after the other, as the helper does with no extension (Helper._run from second 0: the
# whole video), one per mode, and writes each run's mode and exit code to RECALL_HOME/<mode>/run.txt. The person sets
# FACT_CHECK_API_KEY and HF_TOKEN in their own terminal. The runs spend real Claude Code tool calls.
# A run used its mode when the usage log says so: in the conversation mode every part reading names a session, in the
# window mode none does.
# With --no-run, the script only scores the flag files and usage logs already there; with --mode <mode>, it runs only
# that mode and scores both.
# A miss is caught when a flag that the judge did not drop lies within 60 s of one of its minutes and its type or label
# is the kind. The script never prints a quote of the interview.
# Usage: RECALL_HOME=<dir> s18-a4-context-ab.sh [--no-run | --mode window|conversation]
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 1.5-hour interview in your helper home}"
modes="window conversation"
root=$(cd "$(dirname "$0")/../.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
run_root="${RECALL_HOME:-$(mktemp -d)}"
misses="$home/recall/$video.json"
export PYTHONPATH="$root/src/helper"
[ -f "$misses" ] || { echo "FAIL S18 A4 · no misses list at $misses"; exit 1; }
[ "$(cd "$run_root" 2>/dev/null && pwd -P)" = "$(cd "$home" && pwd -P)" ] \
  && { echo "FAIL S18 A4 · RECALL_HOME is the person's helper home"; exit 1; }
cache="$home"
[ -d "$run_root/cache" ] && cache="$run_root/cache"
run="$modes"
[ "${1:-}" = "--no-run" ] && run=""
[ "${1:-}" = "--mode" ] && run="${2:-}"

# Case 1 · one analysis per context mode, each in its own helper home → each ends done
if [ -n "$run" ]; then
  [ -n "${FACT_CHECK_API_KEY:-}" ] && [ -n "${HF_TOKEN:-}" ] \
    || { echo "FAIL S18 A4 · set FACT_CHECK_API_KEY and HF_TOKEN, as the helper has them"; exit 1; }
  for mode in $run; do
    mode_home="$run_root/$mode"
    for dir in captions/$video voices/$video.turns.json speech/$video.words.json audio/$video; do
      if [ -e "$cache/$dir" ] && [ ! -e "$mode_home/$dir" ]; then
        mkdir -p "$mode_home/$(dirname "$dir")"
        cp -R "$cache/$dir" "$mode_home/$dir"
      fi
    done
    rm -f "$mode_home/videos/$video.json" "$mode_home/claims.jsonl" "$mode_home/usage.log"
    echo "analysing $video in $mode_home ($mode)"
    FACT_CHECKER_HOME="$mode_home" python3 -c 'import os, sys; from pathlib import Path; from fact_checker.server import Helper
Helper(Path(os.environ["FACT_CHECKER_HOME"]))._run(sys.argv[1], 0, context_mode=sys.argv[2])' "$video" "$mode"
    echo "$mode $?" > "$mode_home/run.txt"
  done
fi

# Case 2 · per mode → the run exited 0 in that mode, the cost split by step, the misses caught and the judge drop share
# Case 3 · the cheaper mode → at most 6 dollars, at least 4 of the 9 misses caught, the judge drops at most 43 %
python3 - "$run_root" "$misses" "$video" $modes <<'PY'
import collections, json, os, sys
run_root, misses_path, video, *modes = sys.argv[1:]
second = lambda m: int(m.split(":")[0]) * 60 + int(m.split(":")[1])
misses = json.load(open(misses_path))
scores = {}
for mode in modes:
    mode_home = os.path.join(run_root, mode)
    path = os.path.join(mode_home, "videos", f"{video}.json")
    print(f"== {mode}")
    if not os.path.exists(path):
        print(f"FAIL S18 A4 · no flag file for {mode} in {mode_home}")
        continue
    run_path = os.path.join(mode_home, "run.txt")
    ran = open(run_path).read().split() if os.path.exists(run_path) else []
    if ran != [mode, "0"]:
        print(f"FAIL S18 A4 · the {mode} run did not exit 0 in its mode: {ran or 'no run.txt'}")
        continue
    d = json.load(open(path))
    if d["status"] != "done":
        print(f"FAIL S18 A4 · {mode} ended {d['status']} ({d.get('stop_reason')})")
        continue
    usage_path = os.path.join(mode_home, "usage.log")
    lines = [json.loads(l) for l in open(usage_path)] if os.path.exists(usage_path) else []
    by_step = collections.defaultdict(lambda: collections.Counter())
    for l in (l for l in lines if l["video_id"] == video):
        s = by_step[l["step"]]
        s["readings"] += 1
        s["cost"] += l.get("cost_usd") or 0
        for k in ("cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
            s[k] += l.get(k) or 0
    parts = [l for l in lines if l["video_id"] == video and l["step"] == "analyze_chunk"]
    sessions = {l.get("session") for l in parts}
    if not parts or (sessions != {None} if mode == "window" else None in sessions or len(sessions) > len(parts) / 2):
        print(f"FAIL S18 A4 · the part readings of {mode} do not show its mode: {len(sessions)} sessions"
              f" for {len(parts)} readings")
        continue
    print(f"part readings: {len(parts)}, sessions: {len(sessions - {None})}")
    for step, s in sorted(by_step.items(), key=lambda kv: -kv[1]["cost"]):
        n = s["readings"]
        print(f"{step}: {n} readings, {s['cost']:.2f} USD ({s['cost'] / n:.3f} per reading; per reading"
              f" {s['cache_creation_input_tokens'] / n / 1000:.1f}k cache writes,"
              f" {s['cache_read_input_tokens'] / n / 1000:.1f}k cache reads, {s['output_tokens'] / n / 1000:.1f}k output)")
    flags = [f for f in d["flags"] if f["type"] != "context"]
    if not any("judge" in f for f in flags):
        print(f"FAIL S18 A4 · the judge ruled on no flag of {mode}")
        continue
    dropped = lambda f: f.get("judge", {}).get("verdict") == "drop"
    caught = 0
    for miss in misses:
        near = lambda t: any(abs(t - second(m)) <= 60 for m in miss["minutes"])
        hits = [f for f in flags if near(f["t"]) and miss["kind"] in (f["type"], f["label"])]
        kept = [f for f in hits if not dropped(f)]
        caught += bool(kept)
        print(f"{'/'.join(miss['minutes'])} {miss['kind']}: "
              f"{'caught' if kept else 'dropped by the judge' if hits else 'missed'}")
    share = round(100 * sum(map(dropped, flags)) / len(flags)) if flags else 0
    scores[mode] = (d["cost_usd"], caught, share)
    print(f"{mode}: {d['cost_usd']:.2f} USD; caught {caught} of {len(misses)};"
          f" judge drops {sum(map(dropped, flags))} of {len(flags)} non-context flags ({share} %)")
if len(scores) < len(modes):
    sys.exit(1)
mode = min(scores, key=lambda m: scores[m][0])
cost, caught, share = scores[mode]
print(f"winner: {mode} (the cheaper mode)")
ok = True
if cost > 6:
    ok = False
    print(f"FAIL S18 A4 · {mode} costs more than 6 dollars")
if caught < 4:
    ok = False
    print(f"FAIL S18 A4 · {mode} catches fewer than 4 of {len(misses)} misses")
if share > 43:
    ok = False
    print(f"FAIL S18 A4 · the judge drops more than 43 % of the flags of {mode}")
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S18 A4 · The cheaper context mode wins on the 1.5-hour interview" \
  || echo "FAIL S18 A4 · see above"
exit $rc
