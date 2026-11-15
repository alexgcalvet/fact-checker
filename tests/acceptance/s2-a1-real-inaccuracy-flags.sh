#!/usr/bin/env bash
# S2 A1 · A real interview gets inaccuracy flags with dated sources
#
# Story: The person starts the helper with their Google key and asks it for a 112-minute interview. When the analysis ends, the flag file holds at least one inaccuracy flag; each one quotes
# the words, says "false" or "misleading", and names at least one source with its publisher, link and date.
#
# Setup: FACT_CHECK_API_KEY in the environment, a temporary helper home, the helper on a free local port,
# the real YouTube, Claude Code and Fact Check Tools API. Usage: s2-a1-real-inaccuracy-flags.sh <youtube-url>
set -u
url="${1:?usage: $0 <youtube-url>}"
[ -n "${FACT_CHECK_API_KEY:-}" ] || { echo "FAIL S2 A1 · FACT_CHECK_API_KEY is not set"; exit 1; }
root=$(cd "$(dirname "$0")/../.." && pwd)
id=$(printf '%s' "$url" | sed -E 's/.*[?&]v=([^&]+).*/\1/')
home=$(mktemp -d)
port=8798
trap 'kill $pid 2>/dev/null; rm -rf "$home"' EXIT

FACT_CHECKER_HOME="$home" PYTHONPATH="$root/src/helper" python3 -m fact_checker.server --port $port >"$home/server.out" 2>&1 &
pid=$!
for _ in $(seq 1 50); do curl -s "http://127.0.0.1:$port/videos/$id" >/dev/null && break; sleep 0.2; done

# Case 1 · the video is analysed to the end → status done, or stopped by the budget
curl -sf -X POST "http://127.0.0.1:$port/videos/$id?from=0" >/dev/null || { echo "FAIL S2 A1 · POST rejected"; exit 1; }
for _ in $(seq 1 240); do
  status=$(curl -sf "http://127.0.0.1:$port/videos/$id" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' 2>/dev/null)
  [ "$status" = "running" ] || break
  sleep 5
done
curl -sf "http://127.0.0.1:$port/videos/$id" > "$home/flags.json"

# Case 2 · at least one inaccuracy flag; each is false or misleading with a dated source
# Case 3 · the fact-check step ran → the usage log has fact-check calls
python3 - "$home/flags.json" "$home/usage.log" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "done" or d["stop_reason"] == "budget", f"status {d['status']} ({d['stop_reason']})"
bad = [f for f in d["flags"] if f["type"] == "inaccuracy"]
assert bad, "no inaccuracy flag in a 112-minute political interview"
for f in bad:
    assert f["label"] in ("false", "misleading") and f["quote"].strip() and f["reason"].strip(), f
    assert f["sources"], f"no source: {f['quote']}"
    for s in f["sources"]:
        assert s["publisher"] and s["url"].startswith("http"), s
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["date"] or ""), f"undated source: {s}"
steps = [json.loads(x)["step"] for x in open(sys.argv[2])]
assert "fact_check" in steps, "no fact-check call in the usage log"
print(f"{len(bad)} inaccuracy flags")
PY
rc=$?
[ $rc = 0 ] && echo "PASS S2 A1 · A real interview gets inaccuracy flags with dated sources" || echo "FAIL S2 A1 · see above"
exit $rc
