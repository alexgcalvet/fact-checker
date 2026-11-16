#!/usr/bin/env bash
# S16 A4 · The live analysis catches the high-importance misses on the 1.5-hour interview
#
# Story: The person runs the recall check. It analyses the 1.5-hour interview again in a separate helper home (the
# real flag file and marks stay untouched), and prints how many of the 9 high-importance misses (minute ± 1 and
# kind, kept in the person's helper home) the new flags hold, and the share of flags the judge drops. It exits 0
# with at least 6 of 9 caught and a judge drop share no higher than 47 %, the share before this slice.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) holds recall/<REAL_VIDEO>.json, the misses
# of a whole-video reading as minutes and kind only, and the cached captions, voice turns, speech and audio of the
# video. The script copies those caches into a separate helper home (RECALL_HOME, else a new temporary folder) and
# runs the analysis there as the helper does: Opus, fact-check and judge on, from second 0. The person sets
# FACT_CHECK_API_KEY and HF_TOKEN in their own terminal. The run spends real Claude Code tool calls (about 90 Opus
# calls and the judge). With --no-run, the script only scores the flag file already in RECALL_HOME.
# A miss is caught when a flag that the judge did not drop lies within 60 s of one of its minutes and its type or
# label is the kind; a flag under its type's bar counts too, since the side panel shows it. The script never prints
# a quote of the interview.
# Usage: REAL_VIDEO=<id> RECALL_HOME=<dir> s16-a4-real-recall.sh [--no-run]
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 1.5-hour interview in your helper home}"
root=$(cd "$(dirname "$0")/.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
run_home="${RECALL_HOME:-$(mktemp -d)}"
misses="$home/recall/$video.json"
export PYTHONPATH="$root/src/helper"
[ -f "$misses" ] || { echo "FAIL S16 A4 · no misses list at $misses"; exit 1; }
[ "$(cd "$run_home" 2>/dev/null && pwd -P)" = "$(cd "$home" && pwd -P)" ] \
  && { echo "FAIL S16 A4 · RECALL_HOME is the person's helper home"; exit 1; }

# Case 1 · every kind of the misses list → a type or a label the helper can make, before any tool call is spent
python3 - "$misses" <<'PY' || { echo "FAIL S16 A4 · see above"; exit 1; }
import json, sys
from fact_checker.core.flags import FALLACY_LABELS
kinds = {m["kind"] for m in json.load(open(sys.argv[1]))}
unknown = kinds - {"contradiction", "inaccuracy", "question", "fallacy", *FALLACY_LABELS}
if unknown:
    print(f"FAIL S16 A4 · the helper cannot flag {sorted(unknown)}")
    sys.exit(1)
PY

# Case 2 · the analysis in the separate helper home → it ends done
if [ "${1:-}" != "--no-run" ]; then
  [ -n "${FACT_CHECK_API_KEY:-}" ] && [ -n "${HF_TOKEN:-}" ] \
    || { echo "FAIL S16 A4 · set FACT_CHECK_API_KEY and HF_TOKEN, as the helper has them"; exit 1; }
  for dir in captions/$video voices/$video.turns.json speech/$video.words.json audio/$video; do
    if [ -e "$home/$dir" ]; then
      mkdir -p "$run_home/$(dirname "$dir")"
      cp -R "$home/$dir" "$run_home/$dir"
    fi
  done
  rm -f "$run_home/videos/$video.json" "$run_home/claims.jsonl"
  echo "analysing $video in $run_home"
  FACT_CHECKER_HOME="$run_home" python3 -c 'import os, sys; from pathlib import Path; from fact_checker.server import Helper
Helper(Path(os.environ["FACT_CHECKER_HOME"]))._run(sys.argv[1], 0)' "$video" \
    || { echo "FAIL S16 A4 · the analysis raised an error"; exit 1; }
fi

# Case 3 · the new flags → at least 6 of the 9 misses caught
# Case 4 · the judge → drops no more than 47 % of the non-context flags
python3 - "$run_home/videos/$video.json" "$misses" "$run_home/claims.jsonl" "$video" <<'PY'
import collections, json, os, sys
path, misses_path, claims_path, video = sys.argv[1:]
if not os.path.exists(path):
    print(f"FAIL S16 A4 · no flag file in {os.path.dirname(os.path.dirname(path))}")
    sys.exit(1)
d = json.load(open(path))
ok = True
if d["status"] != "done":
    ok = False
    print(f"FAIL S16 A4 · the analysis ended {d['status']} ({d.get('stop_reason')})")
flags = [f for f in d["flags"] if f["type"] != "context"]
if not any("judge" in f for f in flags):
    ok = False
    print("FAIL S16 A4 · the judge ruled on no flag")
dropped = lambda f: f.get("judge", {}).get("verdict") == "drop"
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
    found = ", ".join(f"{f['type']}/{f['label']}" for f in flags if near(f["t"])) or "none"
    print(f"{'/'.join(miss['minutes'])} {miss['kind']}: {state}; claims within 60 s: {dict(nearby) or 'none'};"
          f" flags within 60 s: {found}")
share = sum(map(dropped, flags)) / len(flags) if flags else 0
print(f"caught: {caught} of {len(misses)}; judge drops {sum(map(dropped, flags))} of {len(flags)} non-context flags"
      f" ({round(100 * share)} %)")
print(f"claims log: {len(claims)} claims, {dict(collections.Counter(c['outcome'] for c in claims))}")
if caught < 6:
    ok = False
    print(f"FAIL S16 A4 · fewer than 6 of {len(misses)} misses caught")
if round(100 * share) > 47:
    ok = False
    print("FAIL S16 A4 · the judge drops more than 47 % of the flags")
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S16 A4 · The live analysis catches the high-importance misses on the 1.5-hour interview" \
  || echo "FAIL S16 A4 · see above"
exit $rc
