#!/usr/bin/env bash
# S10 A3 · A real interview gets a context card for a named minister
#
# Story: The helper analyses the part of the 112-minute interview from 26:40 to 28:40, where a minister is named. The flag file has a context flag for that minister
# (REAL_NAMED: the surname as said) with one sentence on who he is.
#
# Setup: the cached captions and voice turns of the interview in the person's helper home
# (FACT_CHECKER_HOME or ~/.fact-checker), read only and copied first; a new temporary helper home. The
# voices are named on the whole interview, then only the window 1600-1720 s is analysed with the real
# Claude (Opus), with no fact-check service.
# With a flag file as argument, the script only checks that file.
# Usage: s10-a3-real-context.sh [flag-file]
set -u
flags="${1:-}"
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 112-minute interview in your helper home}"
: "${REAL_NAMED:?set REAL_NAMED to the surname of the minister named in the window}"
start=1600
end=1720
root=$(cd "$(dirname "$0")/../.." && pwd)
src="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"

if [ -z "$flags" ]; then
  [ -f "$src/captions/$video/$video.es-orig.json3" ] && [ -f "$src/voices/$video.turns.json" ] \
    || { echo "FAIL S10 A3 · no cached captions or voice turns in $src"; exit 1; }
  home=$(mktemp -d)
  # Copy the cache first: another helper may rewrite the captions while this one reads them.
  mkdir -p "$home/cache/captions/$video" "$home/cache/voices"
  for _ in 1 2 3 4 5; do cp "$src/captions/$video/$video.es-orig.json3" "$home/cache/captions/$video/" 2>/dev/null && break; sleep 2; done
  cp "$src/voices/$video.turns.json" "$home/cache/voices/"

  # Case 1 · the window is analysed → status done
  PYTHONPATH="$root/src/helper" python3 - "$home/cache" "$home" "$video" "$start" "$end" <<'PY'
import json, sys
from dataclasses import replace
from pathlib import Path
from fact_checker.adapters.diarization import Diarizer
from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fact_checker.adapters.youtube import parse_json3
from fact_checker.core import speakers
from fact_checker.server import run_analysis

src, home, video = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
start, end = float(sys.argv[4]), float(sys.argv[5])
tr = parse_json3(json.loads((src / "captions" / video / f"{video}.es-orig.json3").read_text()), None)
tr = speakers.assign(tr, Diarizer(src / "voices", None).turns(video))
llm = ClaudeCLI(home, model="opus")
tr = replace(tr, speakers=speakers.name(tr, llm), segments=[s for s in tr.segments if start <= s.t < end])


class Window:
    def fetch(self, video_id):
        return tr


run_analysis(video, start, transcript=Window(), llm=llm, home=home)
PY
  [ $? = 0 ] || { echo "FAIL S10 A3 · the analysis of the window crashed"; exit 1; }
  flags="$home/videos/$video.json"
  echo "flag file: $flags"
fi

# Case 2 · the guest names the minister → a context flag of a person in the window that names REAL_NAMED,
# with one sentence on who he is
PYTHONPATH="$root/src/helper" python3 - "$flags" "$start" "$end" <<'PY'
import json, os, re, sys
d = json.load(open(sys.argv[1]))
start, end = float(sys.argv[2]), float(sys.argv[3])
assert d["status"] == "done", f"status {d['status']} ({d['stop_reason']})"
for f in d["flags"]:
    print(f"  {f['t']:.0f}s {f['type']}/{f['label']} {f['confidence']:.2f}: {f['quote'][:80]} | {f['reason'][:160]}")
hits = [f for f in d["flags"] if f["type"] == "context" and f["label"] == "person" and start <= f["t"] < end
        and os.environ["REAL_NAMED"].lower() in f["quote"].lower() and f["reason"].strip()
        and len(re.findall(r"[.!?](\s|$)", f["reason"].strip())) <= 1]
assert hits, "no context flag for REAL_NAMED with one sentence"
PY
rc=$?
[ $rc = 0 ] && echo "PASS S10 A3 · A real interview gets a context card for a named minister" || echo "FAIL S10 A3 · see above"
exit $rc
