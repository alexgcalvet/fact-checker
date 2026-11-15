#!/usr/bin/env bash
# S7 A4 · A real dodged question shows on the 112-minute interview
#
# Story: The helper analyses the part of the 112-minute interview from 1:29:00 to 1:32:00, where
# the host asks about homes delivered. The flag file has a "question" flag with status "dodged" that quotes
# the host's question about homes.
#
# Setup: the cached captions and voice turns of the interview in the person's helper home
# (FACT_CHECKER_HOME or ~/.fact-checker), read only and copied first; a new temporary helper home. The
# voices are named on the whole interview, then only the window 5340-5520 s is analysed with the real
# Claude (Opus), without published checks. With a flag file as argument, the script only checks that file.
# Usage: s7-a4-real-dodged-question.sh [flag-file]
set -u
flags="${1:-}"
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 112-minute interview in your helper home}"
start=5340
end=5520
root=$(cd "$(dirname "$0")/../.." && pwd)
src="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"

if [ -z "$flags" ]; then
  [ -f "$src/captions/$video/$video.es-orig.json3" ] && [ -f "$src/voices/$video.turns.json" ] \
    || { echo "FAIL S7 A4 · no cached captions or voice turns in $src"; exit 1; }
  home=$(mktemp -d)
  # Copy the cache first: another helper may rewrite the captions while this one reads them.
  mkdir -p "$home/cache/captions/$video" "$home/cache/voices"
  for _ in 1 2 3 4 5; do cp "$src/captions/$video/$video.es-orig.json3" "$home/cache/captions/$video/" 2>/dev/null && break; sleep 2; done
  cp "$src/voices/$video.turns.json" "$home/cache/voices/"
  date=$(yt-dlp --skip-download --print upload_date "https://www.youtube.com/watch?v=$video" 2>/dev/null | tail -1)

  # Case 1 · the window is analysed → status done
  PYTHONPATH="$root/src/helper" python3 - "$home/cache" "$home" "$video" "$start" "$end" "$date" <<'PY'
import json, sys
from dataclasses import replace
from pathlib import Path
from fact_checker.adapters.diarization import Diarizer
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


run_analysis(video, start, transcript=Window(), llm=llm, home=home)
PY
  [ $? = 0 ] || { echo "FAIL S7 A4 · the analysis of the window crashed"; exit 1; }
  flags="$home/videos/$video.json"
  echo "flag file: $flags"
fi

# Case 2 · the host asks about homes delivered → a "question" flag with status "dodged" in the window
# that quotes the host's question about homes
PYTHONPATH="$root/src/helper" python3 - "$flags" "$start" "$end" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1]))
start, end = float(sys.argv[2]), float(sys.argv[3])
assert d["status"] == "done", f"status {d['status']} ({d['stop_reason']})"
for f in d["flags"]:
    q = (f.get("related") or {}).get("quote", "")
    print(f"  {f['t']:.0f}s {f['type']}/{f['label']} {f['confidence']:.2f}: {f['quote'][:80]} | Q: {q[:80]} | {f['reason'][:120]}")
hits = [f for f in d["flags"] if f["type"] == "question" and f.get("answer") == "dodged" and start <= f["t"] < end
        and re.search(r"vivienda|viviendo|entregad|casa|piso",(f.get("related") or {}).get("quote", "").lower())]
assert hits, "no dodged question flag that quotes the host's question about homes"
PY
rc=$?
[ $rc = 0 ] && echo "PASS S7 A4 · A real dodged question shows on the 112-minute interview" || echo "FAIL S7 A4 · see above"
exit $rc
