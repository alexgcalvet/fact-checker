#!/usr/bin/env bash
# S0 A1 · The brand files are in the repo
# Story: A developer opens the web's brand folder and finds the brand's token sheet with all six verdict marks, the
# three fonts each beside its open font licence, and the CALVET wordmark as an SVG.
# Setup: none; the script reads src/web/brand/ and exits 1 on the first missing item.
cd "$(dirname "$0")/../../src/web/brand" 2>/dev/null || { echo "FAIL S0 A1 · src/web/brand/ is missing"; exit 1; }
fail() { echo "FAIL S0 A1 · $1"; exit 1; }

# Case 1 · tokens.css → each of the six verdict marks has its token, Evasiva with its three
for t in falso enganoso retorica contexto correcto evasiva evasiva-text evasiva-bone; do
  grep -q -- "--st-$t:" tokens.css 2>/dev/null || fail "tokens.css has no --st-$t"
done

# Case 2 · fonts/fonts.css → each family has at least one face, each face's file exists, and each OFL licence is there
for fam in "Newsreader" "Host Grotesk" "JetBrains Mono"; do
  urls=$(grep -E "font-family: *['\"]$fam['\"]" fonts/fonts.css 2>/dev/null | grep -oE "url\(['\"]?[^'\")]+" | sed -E "s/url\(['\"]?//")
  [ -n "$urls" ] || fail "fonts/fonts.css has no @font-face with a url for $fam"
  for f in $urls; do [ -s "fonts/$f" ] || fail "fonts/fonts.css points to a missing file: $f"; done
done
for lic in OFL-newsreader.txt OFL-hostgrotesk.txt OFL-jetbrainsmono.txt; do
  grep -q "SIL Open Font License" "fonts/$lic" 2>/dev/null || fail "fonts/$lic is missing"
done

# Case 3 · the wordmark → both SVGs exist and are the brand's drawing (labelled Calvet), not typed text
for svg in calvet-quilla-night.svg calvet-quilla-nav.svg; do
  grep -q 'aria-label="Calvet"' "$svg" 2>/dev/null || fail "$svg is missing"
  grep -q '<text' "$svg" && fail "$svg types the wordmark in a font"
done

echo "PASS S0 A1 · The brand files are in the repo"
