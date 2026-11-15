#!/usr/bin/env bash
# S30 A4 · The repo names no real person or real video, and has a licence and a privacy notice
#
# Story: A stranger clones the repo. A search of the tracked files for the names and video ids of the real interviews
# finds nothing outside the cited public sources of the research notes. `LICENSE` is MIT, 2026 Alex G. Calvet;
# `PRIVACY.md` says what the collector keeps and how to ask for deletion; the README lists the third-party software
# that the setup downloads.
#
# Setup: none. The script reads the files that git tracks in the working tree (not the history). It skips itself and
# the S30 spec, which name the search, and the source links of docs/research/, which cite public articles.
# Usage: bash tests/acceptance/s30-a4-public-repo.sh (from the repo root)
set -u
cd "$(dirname "$0")/../.." || exit 1
pattern='feij|sánchez|sanchez|1YlGArMx_N4|mStOFBvToUI|ábalos|koldo|óscar puente|Óscar Puente|évole|Évole'
fail=0
say() { echo "FAIL S30 A4 · $1"; fail=1; }

# Case 1 · the content of the tracked files → no real name or real video id
hits=$(git grep -niE "$pattern" -- . ':!tests/acceptance/s30-a4-public-repo.sh' ':!docs/specs/030-ready-to-publish/' |
  grep -vE '^docs/research/[^:]+:[0-9]+:- \[[^]]*\]\(https?://' || true)
[ -z "$hits" ] || say "real names or video ids in tracked files:
$hits"

# Case 2 · the names of the tracked files → no real name or real video id
names=$(git ls-files | grep -iE "$pattern" || true)
[ -z "$names" ] || say "real names in file names:
$names"

# Case 3 · LICENSE → MIT, 2026 Alex G. Calvet
grep -q "MIT License" LICENSE 2>/dev/null && grep -q "Copyright (c) 2026 Alex G. Calvet" LICENSE ||
  say "LICENSE is missing or not MIT 2026 Alex G. Calvet"

# Case 4 · PRIVACY.md → what is kept, the IP, how to turn sharing off and ask for deletion, no real address
if [ -f PRIVACY.md ]; then
  for part in "install id" "IP" "share_marks" "<owner email>"; do
    grep -q "$part" PRIVACY.md || say "PRIVACY.md does not mention \"$part\""
  done
  grep -qiE "delet" PRIVACY.md || say "PRIVACY.md does not say how to ask for deletion"
  ! grep -qE "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}" PRIVACY.md || say "PRIVACY.md holds a real email address"
else
  say "PRIVACY.md is missing"
fi

# Case 5 · README → a "Third-party software" section with yt-dlp and FFmpeg (LGPL/GPL), and a link to PRIVACY.md
section=$(awk '/^## Third-party software/{on=1; next} /^## /{on=0} on' README.md)
for part in "yt-dlp" "FFmpeg" "LGPL" "GPL"; do
  printf '%s' "$section" | grep -q "$part" || say "README \"Third-party software\" does not name $part"
done
grep -q "PRIVACY.md" README.md || say "README does not link PRIVACY.md"

[ $fail = 0 ] && echo "PASS S30 A4 · The repo names no real person or real video, and has a licence and a privacy notice"
exit $fail
