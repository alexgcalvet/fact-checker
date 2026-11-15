#!/usr/bin/env bash
# S20 A3 · Codex on the 1.5-hour interview, beside Claude
#
# Story: The person runs the Codex check. It analyses the 1.5-hour interview with Codex in a separate helper home and
# prints the precision on the person's marks (of the Codex flags that match a marked card, the share marked correct),
# the precision of those marks on Claude, and how many of the 9 known misses Codex catches. It exits 0 when the
# analysis ends done and every reading ran Codex.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) holds marks.jsonl and recall/<REAL_VIDEO>.json
# (the misses of a whole-video reading, as minutes and kind only). CODEX_HOME_RUN (else a new temporary folder) is the
# helper home of the Codex run; the script copies the cached captions, voice turns, speech and audio of the video
# into it from the person's helper home. It runs the analysis as the helper does with no extension (Helper._run from
# second 0: the whole video) with FACT_CHECK_PROVIDER=codex, and writes its exit code to CODEX_HOME_RUN/run.txt. The
# person sets FACT_CHECK_API_KEY and HF_TOKEN in their own terminal and is logged in to Codex (`codex login`); the
# command is CODEX_BIN, else `codex`. The run spends real Codex readings of the person's ChatGPT plan.
# A Codex flag matches a marked card when it has the same type, the same label for a fallacy, and at least half of
# the marked quote's words (as core/score.py matches). Flags that the judge dropped do not count. A miss is caught
# when a flag that the judge did not drop lies within 60 s of one of its minutes and its type or label is the kind.
# With --no-run, the script only scores the flag file and usage log already there. It never prints a quote.
# Usage: REAL_VIDEO=<id> CODEX_HOME_RUN=<dir> s20-a3-codex-real.sh [--no-run]
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 1.5-hour interview in your helper home}"
root=$(cd "$(dirname "$0")/../.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
run_home="${CODEX_HOME_RUN:-$(mktemp -d)}"
misses="$home/recall/$video.json"
export PYTHONPATH="$root/src/helper"
[ -f "$misses" ] || { echo "FAIL S20 A3 · no misses list at $misses"; exit 1; }
[ -f "$home/marks.jsonl" ] || { echo "FAIL S20 A3 · no marks at $home/marks.jsonl"; exit 1; }
[ "$(cd "$run_home" 2>/dev/null && pwd -P)" = "$(cd "$home" && pwd -P)" ] \
  && { echo "FAIL S20 A3 · CODEX_HOME_RUN is the person's helper home"; exit 1; }

# Case 1 · the interview is analysed with Codex in its own helper home → the run exits 0 and the file ends done
if [ "${1:-}" != "--no-run" ]; then
  [ -n "${FACT_CHECK_API_KEY:-}" ] && [ -n "${HF_TOKEN:-}" ] \
    || { echo "FAIL S20 A3 · set FACT_CHECK_API_KEY and HF_TOKEN, as the helper has them"; exit 1; }
  "${CODEX_BIN:-codex}" login status >/dev/null 2>&1 \
    || { echo "FAIL S20 A3 · Codex is not logged in: run codex login"; exit 1; }
  for dir in captions/$video voices/$video.turns.json speech/$video.words.json audio/$video; do
    if [ -e "$home/$dir" ] && [ ! -e "$run_home/$dir" ]; then
      mkdir -p "$run_home/$(dirname "$dir")"
      cp -R "$home/$dir" "$run_home/$dir"
    fi
  done
  rm -f "$run_home/videos/$video.json" "$run_home/claims.jsonl" "$run_home/usage.log"
  echo "analysing $video with Codex in $run_home"
  FACT_CHECK_PROVIDER=codex FACT_CHECKER_HOME="$run_home" python3 -c 'import os, sys; from pathlib import Path
from fact_checker.server import Helper
Helper(Path(os.environ["FACT_CHECKER_HOME"]))._run(sys.argv[1], 0)' "$video"
  echo "$?" > "$run_home/run.txt"
fi

# Case 2 · the Codex flags → the precision on the person's marks, beside the precision of the marks on Claude
# Case 3 · the 9 known misses → how many Codex catches
# Case 4 · the readings → every one ran a Codex model (gpt-*, or codex-default: the account's model, S22); tokens per step
python3 - "$run_home" "$home" "$misses" "$video" <<'PY'
import collections, json, os, sys
from fact_checker.core.score import _matches
run_home, home, misses_path, video = sys.argv[1:]
path = os.path.join(run_home, "videos", f"{video}.json")
if not os.path.exists(path):
    sys.exit(print(f"FAIL S20 A3 · no flag file in {run_home}") or 1)
run_path = os.path.join(run_home, "run.txt")
ran = open(run_path).read().strip() if os.path.exists(run_path) else "no run.txt"
d = json.load(open(path))
if ran != "0" or d["status"] != "done":
    sys.exit(print(f"FAIL S20 A3 · the run exited {ran} and ended {d['status']} ({d.get('stop_reason')})") or 1)
marks = {}
for line in open(os.path.join(home, "marks.jsonl")):
    m = json.loads(line)
    if m["video_id"] == video:
        marks[m["flag_id"]] = m
marks = list(marks.values())
dropped = lambda f: f.get("judge", {}).get("verdict") == "drop"
flags = [f for f in d["flags"] if f["type"] != "context" and not dropped(f)]
matched = collections.Counter()
for f in flags:
    hit = next((m for m in marks if _matches(f, m)), None)
    matched[hit["verdict"] if hit else "unmarked"] += 1
judged = matched["correct"] + matched["unfair"]
claude = collections.Counter(m["verdict"] for m in marks)
pct = lambda a, b: f"{100 * a / b:.0f} %" if b else "-"
print(f"Codex: {len(flags)} flags the judge kept; {judged} match a marked card: {matched['correct']} correct,"
      f" {matched['unfair']} unfair; {matched['unmarked']} unmarked")
print(f"precision on marks · Codex {pct(matched['correct'], judged)}"
      f" · Claude {pct(claude['correct'], len(marks))} ({claude['correct']} of {len(marks)} marks correct)")
second = lambda m: int(m.split(":")[0]) * 60 + int(m.split(":")[1])
misses = json.load(open(misses_path))
caught = 0
for miss in misses:
    hits = [f for f in flags if any(abs(f["t"] - second(m)) <= 60 for m in miss["minutes"])
            and miss["kind"] in (f["type"], f["label"])]
    caught += bool(hits)
    print(f"{'/'.join(miss['minutes'])} {miss['kind']}: {'caught' if hits else 'missed'}")
print(f"misses caught by Codex: {caught} of {len(misses)}")
usage_path = os.path.join(run_home, "usage.log")
lines = [l for l in (json.loads(x) for x in open(usage_path)) if l["video_id"] == video] \
    if os.path.exists(usage_path) else []
others = sorted({m for m in (str(l.get("model")) for l in lines) if not (m.startswith("gpt-") or m == "codex-default")})
if not lines or others:
    sys.exit(print(f"FAIL S20 A3 · not every reading ran Codex: {len(lines)} readings, other models {others}") or 1)
steps = collections.defaultdict(collections.Counter)
for l in lines:
    s = steps[(l["step"], l.get("model"))]
    s["readings"] += 1
    for k in ("input_tokens", "cache_read_input_tokens", "output_tokens"):
        s[k] += l.get(k) or 0
for (step, model), s in sorted(steps.items()):
    print(f"{step} ({model}): {s['readings']} readings, {s['input_tokens'] / 1000:.0f}k input,"
          f" {s['cache_read_input_tokens'] / 1000:.0f}k cached, {s['output_tokens'] / 1000:.0f}k output")
PY
rc=$?
[ $rc = 0 ] && echo "PASS S20 A3 · Codex on the 1.5-hour interview, beside Claude" || echo "FAIL S20 A3 · see above"
exit $rc
