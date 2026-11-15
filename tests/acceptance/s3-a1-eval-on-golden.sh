#!/usr/bin/env bash
# S3 A1 · The eval prints precision and recall per flag type on the golden dataset
#
# Story: The person runs the eval command with their Google key. After some minutes it prints a table with
# one row per flag type (fallacy, inaccuracy) and, for each, the precision and recall at the bars 0.5, 0.6,
# 0.7, 0.8 and 0.9, and the bar it recommends.
#
# Setup: FACT_CHECK_API_KEY in the environment; the golden dataset in tests/golden/; the real Claude Code
# and Fact Check Tools API. The eval runs without saving the bars.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
[ -n "${FACT_CHECK_API_KEY:-}" ] || { echo "FAIL S3 A1 · FACT_CHECK_API_KEY is not set"; exit 1; }
out=$(mktemp)
trap 'rm -f "$out"' EXIT

# Case 1 · the golden dataset holds 10 dialogues → the eval runs on all of them and exits 0
[ "$(ls "$root"/tests/golden/*.json 2>/dev/null | wc -l | tr -d ' ')" = 10 ] || { echo "FAIL S3 A1 · tests/golden/ does not hold 10 dialogues"; exit 1; }
PYTHONPATH="$root/src/helper" python3 -m fact_checker.cli eval >"$out" 2>&1 || { tail -5 "$out"; echo "FAIL S3 A1 · eval exited with an error"; exit 1; }
cat "$out"

# Case 2 · one row per type → fallacy and inaccuracy rows, each with a recommended bar or "never"
# Case 3 · the header lists the five bars → 0.5 0.6 0.7 0.8 0.9
# Case 4 · the run reports its Claude tool calls → fewer than 100
python3 - "$out" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
for t in ("fallacy", "inaccuracy"):
    row = next((l for l in text.splitlines() if l.startswith(t)), None)
    assert row, f"no {t} row"
    assert re.search(r"(0\.\d+|never)\s*$", row), f"no recommended bar in: {row}"
head = next(l for l in text.splitlines() if l.startswith("type"))
assert all(b in head for b in ("0.5", "0.6", "0.7", "0.8", "0.9")), head
calls = int(re.search(r"Claude tool calls: (\d+)", text)[1])
assert calls < 100, f"{calls} calls"
PY
rc=$?
[ $rc = 0 ] && echo "PASS S3 A1 · The eval prints precision and recall per flag type on the golden dataset" || echo "FAIL S3 A1 · see above"
exit $rc
