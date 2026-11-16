#!/usr/bin/env bash
# S35 A3 · The card follows the CALVET layout with every text at 30 px or more
#
# Story: The person runs the render check on the invented interview. It saves the card as a PNG and fails if any text
# is under 30 px or the page asks the network for a font. The person opens the PNG beside the InterviewCard board of
# the brand canvas and sees the same plate, Fault, logo and order of blocks.
#
# Setup: the S35 invented interview (tests/support/card_fakes.py) with its marks merged in, the series line
# "1/3 · Candidatos a la Xunta" and, if S35_THUMB names a JPEG, that image as the video thumbnail (else no thumbnail).
# The card page comes from the helper's HTTP route GET /videos/<id>/summary.png?person=&series=, in process, with the
# screenshot faked to return the page's HTML (card_fakes.start); the real screenshot adapter then makes the PNG. A small
# script before </body> measures the page in the person's headless Chrome (--dump-dom) and writes the results on
# <body> attributes: the smallest computed font size of any element that holds text, each text line outside the
# 1080×1350 page, every resource the page requested over http(s), the fonts that loaded, and the top of each block.
# The PNG comes from the helper's own screenshot adapter and is saved at $S35_PNG (default: $TMPDIR/s35-a3-card.png).
set -u
root=$(cd "$(dirname "$0")/.." && pwd)
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
work=$(mktemp -d)
png=${S35_PNG:-${TMPDIR:-/tmp}/s35-a3-card.png}
fail=0
trap 'rm -rf "$work"' EXIT

PYTHONPATH="$root/src/helper:$root/tests/support" python3 - "$work" "$png" \
  "${S35_THUMB:-}" <<'PY' || fail=1
import base64, sys, urllib.parse, urllib.request
from pathlib import Path
from fact_checker import server
from fact_checker.adapters.screenshot import screenshot
from card_fakes import GUEST, save_with_marks, start

work, png, thumb = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
image = "data:image/jpeg;base64," + base64.b64encode(Path(thumb).read_bytes()).decode() if thumb else None

class Patch:  # what pytest's monkeypatch does in card_fakes.start, for this script
    def setattr(self, obj, name, value):
        setattr(obj, name, value)

save_with_marks(work)
base, stop = start(work, Patch())
server.thumbnail = lambda video_id, home: image
query = urllib.parse.urlencode({"person": GUEST, "series": "1/3 · Candidatos a la Xunta"})
html = urllib.request.urlopen(f"{base}/videos/entrevista35/summary.png?{query}", timeout=30).read().decode()
stop()
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
  const top = (sel) => { const el = document.querySelector(sel); return el ? Math.round(el.getBoundingClientRect().top) : -1; };
  const b = document.body;
  b.setAttribute("data-min-font", String(min));
  b.setAttribute("data-outside", JSON.stringify(out));
  b.setAttribute("data-network", JSON.stringify(performance.getEntriesByType("resource").map((e) => e.name).filter((n) => /^https?:/.test(n))));
  b.setAttribute("data-fonts", JSON.stringify([...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family.replace(/"/g, ""))));
  b.setAttribute("data-blocks", JSON.stringify(["plate", "fault", "logo", "hook", "bar", "severity", "devices", "dodged", "gravest", "foot"].map((k) => [k, top("[data-block=" + k + "]")])));
  b.setAttribute("data-logo", JSON.stringify((() => { const r = document.querySelector("[data-block=logo]")?.getBoundingClientRect(); return r ? [r.left, r.top, r.right, r.bottom] : null; })()));
  b.setAttribute("data-scroll", document.documentElement.scrollWidth + "x" + document.documentElement.scrollHeight);
  b.setAttribute("data-done", "1");
});
</script>"""
(work / "page.html").write_text(html.replace("</body>", check + "</body>"))
PY

# Case 1 · the card → a 1080×1350 PNG saved for the person to compare with the board
python3 - "$png" <<'PY' || fail=1
import struct, sys
raw = open(sys.argv[1], "rb").read()
ok = raw[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", raw[16:24]) == (1080, 1350)
print(f"Card saved at {sys.argv[1]}" if ok else f"FAIL S35 A3 · {sys.argv[1]} is not a 1080×1350 PNG")
sys.exit(0 if ok else 1)
PY

"$chrome" --headless --disable-gpu --hide-scrollbars --window-size=1080,1350 --virtual-time-budget=5000 \
  --dump-dom "file://$work/page.html" 2>/dev/null > "$work/dom.html"
python3 - "$work/dom.html" <<'PY' || fail=1
import html, json, re, sys
dom = open(sys.argv[1]).read()
def attr(name, default=None):
    m = re.search(rf'{name}="([^"]*)"', dom)
    return html.unescape(m[1]) if m else default
ok = attr("data-done") == "1"
if not ok:
    print("FAIL S35 A3 · the measuring script did not run")
    sys.exit(1)

# Case 2 · every text of the card → 30 px or more, inside the 1080×1350 page, no page scroll
if float(attr("data-min-font")) < 30:
    print(f"FAIL S35 A3 · the smallest text is {attr('data-min-font')} px"); ok = False
if json.loads(attr("data-outside")):
    print(f"FAIL S35 A3 · text outside the page: {json.loads(attr('data-outside'))[:5]}"); ok = False
if attr("data-scroll") != "1080x1350":
    print(f"FAIL S35 A3 · page scroll size {attr('data-scroll')}"); ok = False

# Case 3 · the page → no request over the network; Newsreader, Host Grotesk and JetBrains Mono loaded from the page
if json.loads(attr("data-network")):
    print(f"FAIL S35 A3 · the page asks the network: {json.loads(attr('data-network'))[:3]}"); ok = False
if "fonts.googleapis" in dom or "fonts.gstatic" in dom:
    print("FAIL S35 A3 · the page links Google Fonts"); ok = False
loaded = set(json.loads(attr("data-fonts")))
for family in ("Newsreader", "Host Grotesk", "JetBrains Mono"):
    if family not in loaded:
        print(f"FAIL S35 A3 · the font {family} did not load (loaded: {sorted(loaded)})"); ok = False

# Case 4 · the blocks of the board → plate, Fault and logo on top, then hook, bar, severity on one line, devices across
# the card (2026-11-16), dodged questions, the most serious, footer; the logo in the top right corner
tops = dict(json.loads(attr("data-blocks")))
missing = [k for k, t in tops.items() if t < 0]
if missing:
    print(f"FAIL S35 A3 · blocks missing: {missing}"); ok = False
else:
    order = [tops[k] for k in ("hook", "bar", "severity", "devices", "dodged", "gravest", "foot")]
    if order != sorted(order) or tops["plate"] != 0 or tops["fault"] > tops["hook"]:
        print(f"FAIL S35 A3 · blocks out of the board's order: {tops}"); ok = False
logo = json.loads(attr("data-logo"))
if not logo or logo[1] > 120 or logo[2] < 900:
    print(f"FAIL S35 A3 · the logo is not in the top right corner: {logo}"); ok = False
sys.exit(0 if ok else 1)
PY

[ $fail = 0 ] && echo "PASS S35 A3 · The card follows the CALVET layout with every text at 30 px or more"
exit $fail
