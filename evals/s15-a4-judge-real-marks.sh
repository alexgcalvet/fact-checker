#!/usr/bin/env bash
# S15 A4 · The judge agrees with the person's marks on the 1.5-hour interview
#
# Story: The person runs `fact-checker judge <REAL_VIDEO> --against-marks` on the analysed 1.5-hour interview. It
# judges it again and prints how many of the 9 flags the person marked unfair the judge dropped, turned into
# "puntualización" or gave to another speaker (S32), and how many of the 10 marked correct it touched; it exits 0 only with at least 6 of 9 and
# at most 1 of 10.
#
# Setup: the person's helper home (FACT_CHECKER_HOME or ~/.fact-checker) with the analysed flag file of the
# video, its cached captions and voice turns, and marks.jsonl. The latest mark of each flag counts. A flag is
# "touched" when the judge dropped it, turned it into "puntualización" or gave it to another speaker. The run
# spends real Claude Code (Opus) tool calls. With --no-run, the script only checks the verdicts already in the
# flag file. The script never prints a quote of the interview.
# Usage: REAL_VIDEO=<id> s15-a4-judge-real-marks.sh [--no-run]; GUEST_NAMES (optional: the guest's names, space-separated, lower case)
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 1.5-hour interview in your helper home}"
root=$(cd "$(dirname "$0")/.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
export PYTHONPATH="$root/src/helper"

# Case 1 · the person runs the judge against the marks → it exits 0 (≥ 6 of 9 unfair touched, ≤ 1 of 10 correct)
if [ "${1:-}" != "--no-run" ]; then
  FACT_CHECKER_HOME="$home" python3 -m fact_checker.cli judge "$video" --against-marks \
    || { echo "FAIL S15 A4 · fact-checker judge exited non-zero"; exit 1; }
fi

# Case 2 · the flag file → a verdict on every non-context flag, and the counts hold on the latest marks
# Case 3 · the judge's fixed rules → no case from this interview: no five words in a row of a flag of this video
python3 - "$home/videos/$video.json" "$home/marks.jsonl" "$video" <<'PY'
import json, os, re, sys
from fact_checker.core import judge
d = json.load(open(sys.argv[1]))
marks = {}
for line in open(sys.argv[2]):
    m = json.loads(line)
    if m["video_id"] == sys.argv[3]:
        marks[m["flag_id"]] = m["verdict"]
flags = {f["id"]: f for f in d["flags"]}
ok = True
missing = [i for i, f in flags.items() if f["type"] != "context" and "judge" not in f]
if missing:
    ok = False
    print(f"FAIL S15 A4 · {len(missing)} non-context flags have no verdict")
touched = lambda f: f.get("judge", {}).get("verdict") in ("drop", "nitpick") \
    or f.get("judge", {}).get("speaker") not in (None, f["speaker"])
ruled_out = touched  # S32: a speaker fix also rules out an unfair flag
unfair = [i for i, v in marks.items() if v == "unfair"]
correct = [i for i, v in marks.items() if v == "correct"]
absent = [i for i in unfair + correct if i not in flags]
if absent:
    ok = False
    print(f"FAIL S15 A4 · {len(absent)} marked flags are missing from the flag file")
caught = sum(ruled_out(flags[i]) for i in unfair if i in flags)
hurt = sum(touched(flags[i]) for i in correct if i in flags)
print(f"unfair nitpicked or given to another speaker: {caught} of {len(unfair)}; correct touched: {hurt} of {len(correct)}")
if caught < 6 or hurt > 1:
    ok = False
    print("FAIL S15 A4 · the judge does not agree with the marks")
words = lambda text: re.findall(r"\w+", text.lower())
rules = " ".join(words(judge.RULES))
leaks = [i for i, f in flags.items() for w in [words(f["quote"])]
         if any(" ".join(w[k:k + 5]) in rules for k in range(len(w) - 4))]
if leaks or any(n in rules.split() for n in os.environ.get("GUEST_NAMES", "").lower().split()):
    ok = False
    print(f"FAIL S15 A4 · the judge's rules hold {len(leaks)} cases from this interview")
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc = 0 ] && echo "PASS S15 A4 · The judge agrees with the person's marks on the 1.5-hour interview" || echo "FAIL S15 A4 · see above"
exit $rc
