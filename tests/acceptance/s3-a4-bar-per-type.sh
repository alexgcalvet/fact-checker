#!/usr/bin/env bash
# S3 A4 · Only flags above their type's bar reach the player
#
# Story: With bars fallacy 0.5 and inaccuracy 0.9, the helper marks a 0.55 fallacy for the player and a
# 0.85 inaccuracy not; on the mimic player page the fallacy card shows and the inaccuracy card does not.
#
# Setup: none; it runs the helper part (pytest) and the extension part (vitest) of the same rule.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
# Case 1 · helper part → the flag file marks on_player by the bar of each type
(cd "$root/src/helper" && uvx --quiet pytest -c pyproject.toml -q ../../tests/acceptance/test_s3_a4_on_player.py) || { echo "FAIL S3 A4 · helper part"; exit 1; }
# Case 2 · extension part → only the marked flag gets a card
(cd "$root/src/extension" && npx vitest run s3-a4-on-player) || { echo "FAIL S3 A4 · extension part"; exit 1; }
echo "PASS S3 A4 · Only flags above their type's bar reach the player"
