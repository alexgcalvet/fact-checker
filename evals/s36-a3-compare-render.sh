#!/usr/bin/env bash
# S36 A3 · The comparison follows the CALVET layout with every text at 30 px or more
#
# Story: The person runs the render check on the three invented interviews. It saves the card as a 1080×1350 PNG and
# fails if any text is under 30 px, a line leaves the page or the page asks the network for a font. The person opens
# the PNG beside the InterviewCompare board and sees the same header, three columns, legend and footer «Detectado con
# IA · no revisado por humanos».
#
# Setup: the three S36 invented interviews (tests/support/compare_fakes.py: Marta Ibarra, Jorge Salcedo, Núria Vidal)
# with their marks in a temporary helper home. `fact-checker compare marta36 jorge36 nuria36` runs in process with no
# thumbnail download and the screenshot faked to return the card's HTML; the real screenshot adapter then makes the
# PNG. A small script before </body> measures the page in the person's headless Chrome (--dump-dom) and writes the
# results on <body> attributes: the smallest computed font size of any element that holds text, each text line outside
# the 1080×1350 page, every resource the page requested over http(s), the fonts that loaded, the top of each block and
# the left edge of each column. The PNG is saved at $S36_PNG (default: $TMPDIR/s36-a3-compare.png).
set -u
root=$(cd "$(dirname "$0")/.." && pwd)
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
work=$(mktemp -d)
png=${S36_PNG:-${TMPDIR:-/tmp}/s36-a3-compare.png}
fail=0
trap 'rm -rf "$work"' EXIT

PYTHONPATH="$root/src/helper:$root/tests/support" python3 - "$work" "$png" <<'PY' || fail=1
import os, sys
from pathlib import Path
from fact_checker import cli, server
from fact_checker.adapters.screenshot import screenshot
from compare_fakes import JORGE, MARTA, NURIA, save

work, png = Path(sys.argv[1]), Path(sys.argv[2])
save(work / "home", MARTA, JORGE, NURIA)
os.environ["FACT_CHECKER_HOME"] = str(work / "home")
os.chdir(work)
server.thumbnail = lambda video_id, home: None
server.screenshot = lambda html, *a, **k: html.encode()
sys.argv = ["fact-checker", "compare", "marta36", "jorge36", "nuria36"]
try:
    cli.main()
except SystemExit as stop:
    if stop.code:
        print(f"FAIL S36 A3 · compare exited {stop.code}")
        sys.exit(1)
html = (work / "compare.png").read_text()
png.write_bytes(screenshot(html))
check = """<script>
document.fonts.ready.then(() => {
  const W = 1080, H = 1350, out = [];
  let min = Infinity;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode());) {
    const el = node.parentElement;
    if (!node.textContent.trim() || el.closest("script, style")) continue;
    min = Math.min(min, parseFloat(getComputedStyle(el).fontSize));
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const r of range.getClientRects())
      if (r.left < -0.5 || r.top < -0.5 || r.right > W + 0.5 || r.bottom > H + 0.5) out.push(node.textContent.slice(0, 30));
  }
  const box = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]; };
  const b = document.body;
  b.setAttribute("data-min-font", String(min));
  b.setAttribute("data-outside", JSON.stringify(out));
  b.setAttribute("data-network", JSON.stringify(performance.getEntriesByType("resource").map((e) => e.name).filter((n) => /^https?:/.test(n))));
  b.setAttribute("data-fonts", JSON.stringify([...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family.replace(/"/g, ""))));
  b.setAttribute("data-blocks", JSON.stringify(["head", "fault", "cols", "legend", "foot", "logo"].map((k) => { const el = document.querySelector("[data-block=" + k + "]"); return [k, el ? box(el) : null]; })));
  b.setAttribute("data-columns", JSON.stringify([...document.querySelectorAll("[data-block=col]")].map(box)));
  b.setAttribute("data-foot", (document.querySelector("[data-block=foot]") || {}).textContent || "");
  b.setAttribute("data-scroll", document.documentElement.scrollWidth + "x" + document.documentElement.scrollHeight);
  b.setAttribute("data-done", "1");
});
</script>"""
(work / "page.html").write_text(html.replace("</body>", check + "</body>"))
PY

# Case 1 · the comparison → a 1080×1350 PNG saved for the person to compare with the board
python3 - "$png" <<'PY' || fail=1
import struct, sys
try:
    raw = open(sys.argv[1], "rb").read()
except OSError:
    raw = b""
ok = raw[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", raw[16:24]) == (1080, 1350)
print(f"Card saved at {sys.argv[1]}" if ok else f"FAIL S36 A3 · {sys.argv[1]} is not a 1080×1350 PNG")
sys.exit(0 if ok else 1)
PY

[ -f "$work/page.html" ] && "$chrome" --headless --disable-gpu --hide-scrollbars --window-size=1080,1350 \
  --virtual-time-budget=5000 --dump-dom "file://$work/page.html" 2>/dev/null > "$work/dom.html"
python3 - "$work/dom.html" <<'PY' || fail=1
import html, json, re, sys
try:
    dom = open(sys.argv[1]).read()
except OSError:
    dom = ""
def attr(name, default=None):
    m = re.search(rf'{name}="([^"]*)"', dom)
    return html.unescape(m[1]) if m else default
ok = attr("data-done") == "1"
if not ok:
    print("FAIL S36 A3 · the measuring script did not run")
    sys.exit(1)

# Case 2 · every text of the card → 30 px or more, inside the 1080×1350 page, no page scroll
if float(attr("data-min-font")) < 30:
    print(f"FAIL S36 A3 · the smallest text is {attr('data-min-font')} px"); ok = False
if json.loads(attr("data-outside")):
    print(f"FAIL S36 A3 · text outside the page: {json.loads(attr('data-outside'))[:5]}"); ok = False
if attr("data-scroll") != "1080x1350":
    print(f"FAIL S36 A3 · page scroll size {attr('data-scroll')}"); ok = False

# Case 3 · the page → no request over the network; Newsreader, Host Grotesk and JetBrains Mono loaded from the page
if json.loads(attr("data-network")):
    print(f"FAIL S36 A3 · the page asks the network: {json.loads(attr('data-network'))[:3]}"); ok = False
if "fonts.googleapis" in dom or "fonts.gstatic" in dom:
    print("FAIL S36 A3 · the page links Google Fonts"); ok = False
loaded = set(json.loads(attr("data-fonts")))
for family in ("Newsreader", "Host Grotesk", "JetBrains Mono"):
    if family not in loaded:
        print(f"FAIL S36 A3 · the font {family} did not load (loaded: {sorted(loaded)})"); ok = False

# Case 4 · the board's layout → header, Fault, three columns side by side, legend, then the footer with the logo
boxes = dict(json.loads(attr("data-blocks")))
missing = [k for k, b in boxes.items() if not b]
columns = json.loads(attr("data-columns"))
if missing:
    print(f"FAIL S36 A3 · blocks missing: {missing}"); ok = False
else:
    tops = [boxes[k][1] for k in ("head", "fault", "cols", "legend", "foot")]
    if tops != sorted(tops) or boxes["legend"][1] < boxes["cols"][3] or boxes["foot"][1] < boxes["legend"][3]:
        print(f"FAIL S36 A3 · blocks out of the board's order: {boxes}"); ok = False
    if boxes["logo"][1] < boxes["foot"][1] - 40 or boxes["logo"][0] < 700:
        print(f"FAIL S36 A3 · the logo is not at the right of the footer: {boxes['logo']}"); ok = False
if len(columns) != 3 or len({c[1] for c in columns}) != 1 or [c[0] for c in columns] != sorted(c[0] for c in columns) \
        or any(a[2] > b[0] + 1 for a, b in zip(columns, columns[1:])):
    print(f"FAIL S36 A3 · not three columns side by side: {columns}"); ok = False

# Case 5 · the footer → «Detectado con IA · no revisado por humanos», not the board's «100 % revisado»
foot = " ".join(attr("data-foot", "").split())
if "Detectado con IA · no revisado por humanos" not in foot or "100 %" in foot:
    print(f"FAIL S36 A3 · the footer reads {foot!r}"); ok = False
sys.exit(0 if ok else 1)
PY

[ $fail = 0 ] && echo "PASS S36 A3 · The comparison follows the CALVET layout with every text at 30 px or more"
exit $fail
