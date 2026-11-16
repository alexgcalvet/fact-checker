#!/usr/bin/env bash
# S21 A3 · Without a Hugging Face token, the speakers come from the text, and the loss is measured
#
# Story: The person runs the comparison check on the 112-minute interview, analysed once with no Hugging Face token
# in a scratch helper home. It prints, for the run with voices and the run without: the share of flags whose speaker
# (host or guest) matches the voice heard at that second, and how many of the 4 cards the person marked unfair for a
# wrong speaker come back. It never prints a quote.
#
# Setup: the first argument is the scratch helper home of the run without a token (the person runs it as the helper
# does, Helper._run from second 0, with HF_TOKEN unset). The person's helper home (FACT_CHECKER_HOME or ~/.fact-checker)
# holds the run with voices (videos/<REAL_VIDEO>.json), its voice turns (voices/<REAL_VIDEO>.turns.json) and marks.jsonl.
# The voice heard at a flag's second is the turn that holds it, named by the speakers of the run with voices; a speaker
# name is host when it says presentador, entrevistador or a word of HOST_NAMES, guest when it says invitado or a
# word of GUEST_NAMES (both optional: names, space-separated, lower case).
# The 4 cards marked unfair for a wrong speaker are the marks whose reason says the host said it or the guest said it to
# himself: tu_quoque-578.3, misleading-1416.2, tu_quoque-1597.5, evasion-1623.3. A card comes back when a card on the
# player has the same type, the same label for a fallacy, and at least half of the marked quote's words.
# Usage: s21-a3-no-diarization.sh <scratch helper home>
set -u
video="${REAL_VIDEO:?set REAL_VIDEO to the id of the 112-minute interview in your helper home}"
root=$(cd "$(dirname "$0")/.." && pwd)
home="${FACT_CHECKER_HOME:-$HOME/.fact-checker}"
scratch="${1:-}"
[ -n "$scratch" ] || { echo "FAIL S21 A3 · usage: s21-a3-no-diarization.sh <scratch helper home>"; exit 1; }
[ "$(cd "$scratch" 2>/dev/null && pwd -P)" = "$(cd "$home" && pwd -P)" ] \
  && { echo "FAIL S21 A3 · the scratch home is the person's helper home"; exit 1; }

PYTHONPATH="$root/src/helper" python3 - "$scratch" "$home" "$video" <<'PY'
import json, os, sys
from fact_checker.core.score import _matches
scratch, home, video = sys.argv[1:]
WRONG_SPEAKER = ["tu_quoque-578.3", "misleading-1416.2", "tu_quoque-1597.5", "evasion-1623.3"]
HOST = ("presentador", "entrevistador", *os.environ.get("HOST_NAMES", "").lower().split())
GUEST = ("invitado", *os.environ.get("GUEST_NAMES", "").lower().split())


def role(name):
    name = (name or "").lower()
    return "host" if any(k in name for k in HOST) else "guest" if any(k in name for k in GUEST) else None


# Case 1 · the run without a token → done, with no voice turns and no voice names
path = os.path.join(scratch, "videos", f"{video}.json")
if not os.path.exists(path):
    sys.exit(f"FAIL S21 A3 · no flag file at {path}")
plain = json.load(open(path))
if plain["status"] != "done":
    sys.exit(f"FAIL S21 A3 · the run without a token is {plain['status']} ({plain['stop_reason']})")
if os.path.exists(os.path.join(scratch, "voices")) or plain.get("speakers"):
    sys.exit("FAIL S21 A3 · the run without a token used voices")

voiced = json.load(open(os.path.join(home, "videos", f"{video}.json")))
turns = json.load(open(os.path.join(home, "voices", f"{video}.turns.json")))
voice_role = {k: role(v) for k, v in voiced["speakers"].items()}
marks = {}
for line in open(os.path.join(home, "marks.jsonl")):
    m = json.loads(line)
    if m["video_id"] == video:
        marks[m["flag_id"]] = m


def heard(t):
    turn = next((x for x in turns if x["start"] <= t < x["end"]), None) \
        or min(turns, key=lambda x: min(abs(x["start"] - t), abs(x["end"] - t)))
    return voice_role.get(turn["speaker"])


# Case 2 · per run → the share of flags whose speaker matches the voice heard at their second
# Case 3 · per run → how many of the 4 cards marked unfair for a wrong speaker come back on the player
print(f"{'run':<15} {'flags':>5} {'speaker = voice':>16} {'unknown name':>13} {'wrong-speaker cards back':>25} "
      f"{'cost':>7}")
for name, run in (("with voices", voiced), ("without voices", plain)):
    flags = [f for f in run["flags"] if f["type"] != "context"]
    same = sum(role(f["speaker"]) == heard(f["t"]) for f in flags)
    unknown = sum(role(f["speaker"]) is None for f in flags)
    cards = [f for f in run["flags"] if f.get("on_player")]
    back = sum(any(_matches(c, marks[i]) for c in cards) for i in WRONG_SPEAKER if i in marks)
    cost = run.get("cost_usd")
    print(f"{name:<15} {len(flags):>5} {same / max(1, len(flags)):>15.0%} {unknown:>13} {back:>21} of 4 "
          f"{'-' if cost is None else f'{cost:.2f}':>7}")
print("PASS S21 A3 · Without a Hugging Face token, the speakers come from the text, and the loss is measured")
PY
