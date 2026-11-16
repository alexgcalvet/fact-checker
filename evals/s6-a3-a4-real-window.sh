#!/usr/bin/env bash
# S6 A3 / A4 · An answer that swaps the metric asked is flagged; a plan told as a fact is flagged
#
# Story (A3): In the 112-minute interview, around 1:30:07, the host asks about homes delivered and
# the guest answers with homes "entregadas o en proceso". After the helper analyses that part, the flag
# file has a "definition_swap" flag on those words that names the metric asked and the metric given.
# Story (A4): Around 1:30:42, the guest talks about Casa 47 homes as if they already existed. After the
# helper analyses that part, the flag file has a "plan_as_fact" flag on those words with a dated source
# on the plan's real status.
#
# Setup: the cached captions and voice turns of the interview in the person's helper home
# (FACT_CHECKER_HOME or ~/.fact-checker), read only; FACT_CHECK_API_KEY in the environment; a new
# temporary helper home. The voices are named on the whole interview, then only the window 5340-5520 s
# (1:29:00-1:32:00) is analysed with the real Claude (Opus) and Fact Check Tools API. The temporary home
# stays, so the other label can reuse its flag file.
# With a flag file as second argument, the script only checks that file.
# Usage: s6-a3-a4-real-window.sh <definition_swap|plan_as_fact> [flag-file]
set -u
label="${1:?usage: $0 <label> [flag-file]}"
flags="${2:-}"
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 112-minute interview in your helper home}"
start=5340
end=5520
root=$(cd "$(dirname "$0")/.." && pwd)
src="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
[ "$label" = definition_swap ] && item=A3 || item=A4

if [ -z "$flags" ]; then
  [ -n "${FACT_CHECK_API_KEY:-}" ] || { echo "FAIL S6 $item · FACT_CHECK_API_KEY is not set"; exit 1; }
  [ -f "$src/captions/$video/$video.es-orig.json3" ] && [ -f "$src/voices/$video.turns.json" ] \
    || { echo "FAIL S6 $item · no cached captions or voice turns in $src"; exit 1; }
  home=$(mktemp -d)
  # Copy the cache first: another helper may rewrite the captions while this one reads them.
  mkdir -p "$home/cache/captions/$video" "$home/cache/voices"
  for _ in 1 2 3 4 5; do cp "$src/captions/$video/$video.es-orig.json3" "$home/cache/captions/$video/" 2>/dev/null && break; sleep 2; done
  cp "$src/voices/$video.turns.json" "$home/cache/voices/"
  date=$(yt-dlp --skip-download --print upload_date "https://www.youtube.com/watch?v=$video" 2>/dev/null | tail -1)

  # Case 1 · the window is analysed → status done
  PYTHONPATH="$root/src/helper" python3 - "$home/cache" "$home" "$video" "$start" "$end" "$date" <<'PY'
import json, os, sys
from dataclasses import replace
from pathlib import Path
from fact_checker.adapters.diarization import Diarizer
from fact_checker.adapters.factcheck_google import GoogleFactCheck
from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fact_checker.adapters.youtube import parse_json3
from fact_checker.core import speakers
from fact_checker.server import run_analysis

src, home, video = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
start, end, date = float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
published = f"{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 else None
tr = parse_json3(json.loads((src / "captions" / video / f"{video}.es-orig.json3").read_text()), published)
tr = speakers.assign(tr, Diarizer(src / "voices", None).turns(video))
llm = ClaudeCLI(home, model="opus")
tr = replace(tr, speakers=speakers.name(tr, llm), segments=[s for s in tr.segments if start <= s.t < end])


class Window:
    def fetch(self, video_id):
        return tr


run_analysis(video, start, transcript=Window(), llm=llm, home=home,
             factcheck=GoogleFactCheck(os.environ["FACT_CHECK_API_KEY"]))
PY
  [ $? = 0 ] || { echo "FAIL S6 $item · the analysis of the window crashed"; exit 1; }
  flags="$home/videos/$video.json"
  echo "flag file: $flags"
fi

# Case 2 · definition_swap: a flag on "entregadas o en proceso" near 5407 s → the reason names both metrics
# Case 2 · plan_as_fact: a flag on the Casa 47 words near 5442 s → a dated source on the plan's status
PYTHONPATH="$root/src/helper" python3 - "$flags" "$label" "$start" "$end" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1]))
label, start, end = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
assert d["status"] == "done", f"status {d['status']} ({d['stop_reason']})"
for f in d["flags"]:
    print(f"  {f['t']:.0f}s {f['type']}/{f['label']} {f['confidence']:.2f}: {f['quote'][:90]} | {f['reason'][:120]}")
def dated(f):
    return f["sources"] and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["date"] or "") for s in f["sources"])
def text(f):
    return (f["quote"] + " " + f["reason"]).lower()
if label == "definition_swap":
    hits = [f for f in d["flags"] if f["label"] == label and 5380 <= f["t"] < 5440 and "proceso" in text(f)
            and "entregad" in f["reason"].lower()]
else:
    hits = [f for f in d["flags"] if f["label"] == label and 5410 <= f["t"] < 5480 and "casa 47" in text(f)]
hits = [f for f in hits if f["type"] == "inaccuracy" and dated(f)]
assert hits, f"no {label} flag with a dated source on the words of the story"
PY
rc=$?
if [ "$label" = definition_swap ]; then title="An answer that swaps the metric asked is flagged"
else title="A plan told as a fact is flagged"; fi
[ $rc = 0 ] && echo "PASS S6 $item · $title" || echo "FAIL S6 $item · see above"
exit $rc
