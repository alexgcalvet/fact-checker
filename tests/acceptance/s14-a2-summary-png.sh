#!/usr/bin/env bash
# S14 A2 · The summary is one 1080×1350 PNG that holds everything
#
# Story: The person exports the summary of an invented interview whose flags have long quotes. They get one
# PNG of 1080×1350 with the title, the timeline, both columns and the footer; no text runs outside the image
# and no text is smaller than 26 px.
#
# Setup: a temporary helper home with the invented flag file of one video (two speakers, quotes and reasons
# of about 300 characters) and a marks log that marks every flag correct; the helper started on a free local
# port; the person's installed Google Chrome.
#
# How the layout is checked: the summary page that the helper turns into the PNG (fact_checker.server
# .summary_page) gets a small script before </body>. Real headless Chrome loads it at 1080×1350 with
# --dump-dom. The script measures every text line (Range.getClientRects): each line must lie inside the
# 1080×1350 page and inside its <section> (header, timeline, a speaker, footer). A line inside a `.clamp` box
# counts only for its visible part, since that box cuts long text on purpose with an ellipsis. It also takes
# the smallest computed font size of any element that holds text. It writes the results on <body>
# attributes, which the dumped DOM then shows.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
home=$(mktemp -d)
id="inventado1"
fail=0
trap 'kill $pid 2>/dev/null; rm -rf "$home"' EXIT

python3 - "$home" "$id" <<'PY'
import json, sys
from pathlib import Path
home, vid = Path(sys.argv[1]), sys.argv[2]
long = ("y además le digo que el desempleo juvenil ha bajado a la mitad en solo dos años gracias a nuestras "
        "políticas, cosa que ningún otro gobierno de la historia de este país ha conseguido jamás, ni de lejos, "
        "y eso lo saben todos los expertos aunque ustedes no lo quieran reconocer en este programa ni en ningún otro")
why = ("La EPA del tercer trimestre sitúa la tasa en el 25,1 %, frente al 29,4 % de hace dos años: baja cuatro "
       "puntos, no la mitad; el propio ministerio publicó esas cifras en su nota de prensa del mes pasado.")
def flag(n, t, who, type, label):
    return {"id": f"{label}-{t}", "t": t, "speaker": who, "quote": f"{n} {long}", "type": type, "label": label,
            "reason": why, "confidence": 0.9, "related": None, "on_player": True, "note": None,
            "sources": [{"publisher": "Instituto Nacional de Estadística de un país inventado", "url": "https://example.org/epa", "date": "2026-10-01"}]}
guest, host = "Ana Ruiz Fernández de la Peña (invitada)", "Luis Gil Montenegro (presentador)"
flags = [flag(1, 120.0, guest, "inaccuracy", "false"), flag(2, 900.0, guest, "contradiction", "self"),
         flag(3, 1500.0, guest, "question", "dodged"), flag(4, 2100.0, guest, "inaccuracy", "disputed"),
         flag(5, 600.0, host, "fallacy", "straw_man"), flag(6, 1800.0, host, "inaccuracy", "misleading"),
         flag(7, 3000.0, host, "fallacy", "false_dilemma"), flag(8, 3300.0, host, "fallacy", "ad_hominem")]
data = {"video_id": vid, "published_at": "2026-11-10", "status": "done", "stop_reason": None,
        "title": "Una entrevista inventada con un título muy largo que no cabe en una sola línea del encabezado de la imagen",
        "channel": "Canal de pruebas inventado", "duration": 3600.0,
        "speakers": {"SPEAKER_00": host, "SPEAKER_01": guest}, "flags": flags}
(home / "videos").mkdir(parents=True)
(home / "videos" / f"{vid}.json").write_text(json.dumps(data, ensure_ascii=False))
with open(home / "marks.jsonl", "w") as out:
    for f in flags:
        out.write(json.dumps({"video_id": vid, "flag_id": f["id"], "quote": f["quote"], "type": f["type"],
                              "label": f["label"], "confidence": f["confidence"], "verdict": "correct", "reason": ""},
                             ensure_ascii=False) + "\n")
PY

port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
FACT_CHECKER_HOME="$home" PYTHONPATH="$root/src/helper" python3 -m fact_checker.server --port "$port" >"$home/server.out" 2>&1 &
pid=$!
for _ in $(seq 1 50); do curl -s "http://127.0.0.1:$port/videos/$id" >/dev/null && break; sleep 0.2; done

# Case 1 · the person asks for the summary image → one PNG of exactly 1080×1350
code=$(curl -s -o "$home/summary.png" -w '%{http_code}' "http://127.0.0.1:$port/videos/$id/summary.png")
python3 - "$home/summary.png" "$code" <<'PY' || fail=1
import struct, sys
raw = open(sys.argv[1], "rb").read()
assert sys.argv[2] == "200", f"HTTP {sys.argv[2]}"
assert raw[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
width, height = struct.unpack(">II", raw[16:24])
assert (width, height) == (1080, 1350), f"size {width}×{height}"
PY
[ $fail = 0 ] || echo "FAIL S14 A2 · no 1080×1350 PNG from GET /videos/$id/summary.png"

# Case 2 · the page of the image, long quotes → title, timeline, two columns and footer; no text outside; ≥26 px
FACT_CHECKER_HOME="$home" PYTHONPATH="$root/src/helper" python3 - "$home" "$id" > "$home/page.html" <<'PY' || fail=1
import json, sys
from pathlib import Path
from fact_checker.server import summary_page
home, vid = Path(sys.argv[1]), sys.argv[2]
data = json.loads((home / "videos" / f"{vid}.json").read_text())
data["flags"] = [f | {"mark": "correct"} for f in data["flags"]]
check = """<script>
const W = 1080, H = 1350, bad = [];
let min = Infinity;
const inside = (r, b) => r.left >= b.left - 0.5 && r.top >= b.top - 0.5 && r.right <= b.right + 0.5 && r.bottom <= b.bottom + 0.5;
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
for (let node; (node = walker.nextNode());) {
  const el = node.parentElement;
  if (!node.textContent.trim() || el.closest("script")) continue;
  min = Math.min(min, parseFloat(getComputedStyle(el).fontSize));
  const section = el.closest("section");
  const clamp = el.closest(".clamp");
  const range = document.createRange();
  range.selectNodeContents(node);
  for (let r of range.getClientRects()) {
    if (clamp) {
      const c = clamp.getBoundingClientRect();
      if (r.top >= c.bottom - 0.5) continue;
      r = { left: r.left, top: r.top, right: r.right, bottom: Math.min(r.bottom, c.bottom) };
    }
    if (!inside(r, { left: 0, top: 0, right: W, bottom: H })) bad.push("page: " + node.textContent.slice(0, 30));
    else if (!section || !inside(r, section.getBoundingClientRect())) bad.push("section: " + node.textContent.slice(0, 30));
  }
}
const sections = (cls) => document.querySelectorAll("section." + cls).length;
document.body.setAttribute("data-min-font", String(min));
document.body.setAttribute("data-bad", JSON.stringify(bad));
document.body.setAttribute("data-sections", [sections("title"), sections("timeline"), sections("speaker"), sections("footer")].join(","));
document.body.setAttribute("data-text", document.body.innerText.replace(/\\s+/g, " "));
document.body.setAttribute("data-scroll", document.documentElement.scrollWidth + "x" + document.documentElement.scrollHeight);
</script>"""
print(summary_page(data).replace("</body>", check + "</body>"))
PY
"$chrome" --headless --disable-gpu --hide-scrollbars --window-size=1080,1350 --virtual-time-budget=2000 \
  --dump-dom "file://$home/page.html" 2>/dev/null > "$home/dom.html"
python3 - "$home/dom.html" <<'PY' || fail=1
import html, json, re, sys
dom = open(sys.argv[1]).read()
attr = lambda name: html.unescape(re.search(rf'{name}="([^"]*)"', dom)[1]) if re.search(rf'{name}="([^"]*)"', dom) else None
ok = True
if attr("data-sections") != "1,1,2,1":
    print(f"FAIL S14 A2 · sections title,timeline,speaker,footer = {attr('data-sections')}, want 1,1,2,1"); ok = False
if attr("data-min-font") is None or float(attr("data-min-font")) < 26:
    print(f"FAIL S14 A2 · smallest text {attr('data-min-font')} px"); ok = False
if json.loads(attr("data-bad") or '["no check ran"]'):
    print(f"FAIL S14 A2 · text outside: {json.loads(attr('data-bad') or '[]')[:5]}"); ok = False
text = attr("data-text") or ""
for want in ("Una entrevista inventada", "Ana Ruiz", "Luis Gil", "no veredictos", "revisado"):
    if want not in text:
        print(f"FAIL S14 A2 · the image does not say {want!r}"); ok = False
if attr("data-scroll") != "1080x1350":
    print(f"FAIL S14 A2 · page scroll size {attr('data-scroll')}"); ok = False
sys.exit(0 if ok else 1)
PY

# Case 3 · the share page of the summary → the image and its alt text, ready to copy under it
curl -s "http://127.0.0.1:$port/videos/$id/summary" > "$home/share.html"
curl -s "http://127.0.0.1:$port/videos/$id/summary.txt" > "$home/alt.txt"
python3 - "$home/share.html" "$home/alt.txt" <<'PY' || fail=1
import html, sys
page, alt = open(sys.argv[1]).read(), open(sys.argv[2]).read()
ok = 'src="summary.png"' in page and "<textarea" in page and alt.strip() and html.escape(alt.strip()) in page
ok = ok and "Ana Ruiz" in alt and len(alt) <= 1000
if not ok:
    print("FAIL S14 A2 · the share page has no image and alt text, or the alt text is missing or over 1000 characters")
sys.exit(0 if ok else 1)
PY

[ $fail = 0 ] && echo "PASS S14 A2 · The summary is one 1080×1350 PNG that holds everything"
exit $fail
