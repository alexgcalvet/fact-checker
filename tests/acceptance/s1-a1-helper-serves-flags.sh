#!/usr/bin/env bash
# S1 A1 · Opening a video makes the helper analyse it and serve its flags
#
# Story: The person starts the helper and asks it for a short public Spanish video (about 15 minutes).
# After a few minutes the helper answers with the flag file of that video: status "done", its publish
# date, and fallacy flags, each with a second, the exact words, one of the 8 fallacy names, a reason
# and a confidence. Asked again, it serves the saved file and calls Claude zero times.
#
# Setup: a temporary helper home, the helper started on a free local port, the real YouTube and the
# real Claude Code. Usage: s1-a1-helper-serves-flags.sh <youtube-url>
set -u
url="${1:?usage: $0 <youtube-url>}"
root=$(cd "$(dirname "$0")/../.." && pwd)
id=$(printf '%s' "$url" | sed -E 's/.*[?&]v=([^&]+).*/\1/')
home=$(mktemp -d)
port=8799
fail=0
trap 'kill $pid 2>/dev/null; rm -rf "$home"' EXIT

FACT_CHECKER_HOME="$home" PYTHONPATH="$root/src/helper" python3 -m fact_checker.server --port $port >"$home/server.out" 2>&1 &
pid=$!
for _ in $(seq 1 50); do curl -s "http://127.0.0.1:$port/videos/$id" >/dev/null && break; sleep 0.2; done

# Case 1 · a new video is posted and polled → status done, publish date, valid fallacy flags
curl -sf -X POST "http://127.0.0.1:$port/videos/$id?from=0" >/dev/null || { echo "FAIL S1 A1 · POST rejected"; exit 1; }
status=""
for _ in $(seq 1 180); do
  status=$(curl -sf "http://127.0.0.1:$port/videos/$id" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' 2>/dev/null)
  [ "$status" = "done" ] || [ "$status" = "stopped" ] && break
  sleep 5
done
curl -sf "http://127.0.0.1:$port/videos/$id" > "$home/flags.json"
python3 - "$home/flags.json" <<'PY' || fail=1
import json, re, sys
d = json.load(open(sys.argv[1]))
labels = {"ad_hominem", "tu_quoque", "false_dilemma", "straw_man", "evasion",
          "false_cause", "hasty_generalization", "vague_authority"}
assert d["status"] == "done", f"status {d['status']} ({d.get('stop_reason')})"
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["published_at"] or ""), "publish date missing"
assert d["flags"], "no flags in a 14-minute political video"
for f in d["flags"]:
    assert f["type"] == "fallacy" and f["label"] in labels, f"bad type or label: {f['type']} {f['label']}"
    assert isinstance(f["t"], (int, float)) and f["t"] >= 0, "bad second"
    assert f["quote"].strip() and f["reason"].strip(), "empty quote or reason"
    assert 0 <= f["confidence"] <= 1, "confidence out of range"
PY

# Case 2 · the same video is posted again → served from the file, zero new Claude calls
calls_before=$(grep -c . "$home/usage.log" 2>/dev/null || echo 0)
curl -sf -X POST "http://127.0.0.1:$port/videos/$id?from=0" >/dev/null
sleep 3
calls_after=$(grep -c . "$home/usage.log" 2>/dev/null || echo 0)
[ "$calls_before" -gt 0 ] && [ "$calls_before" = "$calls_after" ] || { echo "FAIL S1 A1 · second request called Claude ($calls_before → $calls_after)"; fail=1; }

[ $fail = 0 ] && echo "PASS S1 A1 · Opening a video makes the helper analyse it and serve its flags" || echo "FAIL S1 A1 · see above"
exit $fail
