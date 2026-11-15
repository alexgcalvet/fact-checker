#!/usr/bin/env bash
# S4 A1 · Marking a card keeps the mark on the laptop
#
# Story: On a page that mimics the YouTube player, the person clicks "✗ No" on an ad hominem card,
# types "es una pregunta, no un ataque" and saves. The helper's marks log gets one line with the video,
# the flag, its words, its name, "unfair" and that reason. Marking it again "correct" adds a second line,
# and the latest mark is the one that counts.
#
# Setup: none; it runs the extension part (vitest) and the helper part (pytest) of the same behaviour.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
# Case 1 · extension part → the buttons send the mark with its verdict and reason
(cd "$root/src/extension" && npx vitest run s4-a1-mark-buttons) || { echo "FAIL S4 A1 · extension part"; exit 1; }
# Case 2 · helper part → the mark is kept in the marks log; unknown flags and verdicts are rejected
(cd "$root/src/helper" && uvx --quiet pytest -c pyproject.toml -q ../../tests/acceptance/test_s4_a1_mark_stored.py) || { echo "FAIL S4 A1 · helper part"; exit 1; }
echo "PASS S4 A1 · Marking a card keeps the mark on the laptop"
