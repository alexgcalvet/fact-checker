#!/usr/bin/env bash
# S9 A4 · A real promise shows its status on the 112-minute interview
#
# Story: The helper analyses the part of the 112-minute interview from 1:29:00 to 1:32:00, where
# homes delivered come up. The flag file has a promise flag about homes with the date of the promise, its
# figure and its status, and a dated source.
#
# Setup: the cached captions and voice turns of the interview in the person's helper home
# (FACT_CHECKER_HOME or ~/.fact-checker), read only and copied first; FACT_CHECK_API_KEY in the
# environment; a new temporary helper home. The voices are named on the whole interview, then only the
# window 5340-5520 s is analysed with the real Claude (Opus) and Fact Check Tools API.
# With a flag file as argument, the script only checks that file.
# Usage: s9-a4-real-promise.sh [flag-file]
set -u
flags="${1:-}"
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 112-minute interview in your helper home}"
start=5340
end=5520
root=$(cd "$(dirname "$0")/../.." && pwd)
src="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"

if [ -z "$flags" ]; then
  [ -n "${FACT_CHECK_API_KEY:-}" ] || { echo "FAIL S9 A4 · FACT_CHECK_API_KEY is not set"; exit 1; }
  [ -f "$src/captions/$video/$video.es-orig.json3" ] && [ -f "$src/voices/$video.turns.json" ] \
    || { echo "FAIL S9 A4 · no cached captions or voice turns in $src"; exit 1; }
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
  [ $? = 0 ] || { echo "FAIL S9 A4 · the analysis of the window crashed"; exit 1; }
  flags="$home/videos/$video.json"
  echo "flag file: $flags"
fi

# Case 2 · the guest gives home figures → a "promise" contradiction flag about homes in the window, with
# the date of the promise, its figure, its status and a dated source
PYTHONPATH="$root/src/helper" python3 - "$flags" "$start" "$end" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1]))
start, end = float(sys.argv[2]), float(sys.argv[3])
assert d["status"] == "done", f"status {d['status']} ({d['stop_reason']})"
for f in d["flags"]:
    print(f"  {f['t']:.0f}s {f['type']}/{f['label']} {f['confidence']:.2f}: {f['quote'][:80]} | "
          f"{f.get('promise')} | {f['reason'][:120]}")
def dated(f):
    return f["sources"] and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["date"] or "") for s in f["sources"])
def homes(f):
    p = f.get("promise") or {}
    return re.search(r"vivienda|casa", (f["quote"] + " " + str(p.get("figure", "")) + " " + f["reason"]).lower())
def complete(p):
    return p and re.match(r"\d{4}", p.get("made") or "") and p.get("figure") and p.get("status")
hits = [f for f in d["flags"] if f["type"] == "contradiction" and f["label"] == "promise" and start <= f["t"] < end
        and homes(f) and complete(f.get("promise")) and dated(f)]
assert hits, "no promise flag about homes with its date, figure, status and a dated source"
PY
rc=$?
[ $rc = 0 ] && echo "PASS S9 A4 · A real promise shows its status on the 112-minute interview" || echo "FAIL S9 A4 · see above"
exit $rc
