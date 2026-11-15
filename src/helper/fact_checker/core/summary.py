"""The shareable summary of one video: each speaker's most serious reviewed flags, their counts and the alt text."""
import math
import re
from collections import Counter
from html import escape
from string import Template

# The colours and icons of the extension cards (src/extension/src/flags.ts), in the order of seriousness.
FAMILIES = {
    "false": ("#ff6b6b", "✗"),
    "contradiction": ("#f06fd0", "⇄"),
    "question": ("#4dabf7", "?"),
    "misleading": ("#ff9f43", "!"),
    "disputed": ("#ffd43b", "≈"),
    "fallacy": ("#b388ff", "⚑"),
}
ORDER = list(FAMILIES)
MAX_BOXES = 4
# Every text of the image and its alt text, in the language of the flag file's `lang`.
TEXTS = {
    "es": {
        "families": {"false": ("falso", "falsos"), "contradiction": ("contradicción", "contradicciones"),
                     "question": ("pregunta esquivada", "preguntas esquivadas"), "misleading": ("engañoso", "engañosos"),
                     "disputed": ("discutido", "discutidos"), "fallacy": ("falacia", "falacias")},
        "footer": "Señales automáticas, no veredictos · revisado · fact-checker", "bold": "no veredictos",
        "months": "ene feb mar abr may jun jul ago sep oct nov dic".split(),
        "video": "Vídeo {}", "more": "y {} más", "and": " y ", "guest": "invitad",
        "alt": "Resumen de «{}» ({}). Señales automáticas revisadas, no veredictos.", "none": "sin avisos revisados",
        "alt_more": "Y {} más.", "flags": "avisos", "reviewed": "avisos<br>revisados", "empty": "Sin avisos revisados",
        "kicker": "Avisos revisados",
    },
    "en": {
        "families": {"false": ("false", "false"), "contradiction": ("contradiction", "contradictions"),
                     "question": ("dodged question", "dodged questions"), "misleading": ("misleading", "misleading"),
                     "disputed": ("disputed", "disputed"), "fallacy": ("fallacy", "fallacies")},
        "footer": "Automatic signals, not verdicts · reviewed · fact-checker", "bold": "not verdicts",
        "months": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
        "video": "Video {}", "more": "and {} more", "and": " and ", "guest": "guest",
        "alt": "Summary of «{}» ({}). Reviewed automatic signals, not verdicts.", "none": "no reviewed flags",
        "alt_more": "And {} more.", "flags": "flags", "reviewed": "reviewed<br>flags", "empty": "No reviewed flags",
        "kicker": "Reviewed flags",
    },
}


def family(flag: dict) -> str | None:
    if flag["type"] == "inaccuracy":
        return {"false": "false", "disputed": "disputed"}.get(flag["label"], "misleading")
    return flag["type"] if flag["type"] in FAMILIES else None


def speaker(flag: dict) -> str:
    """The judge's speaker when it gave the line to someone else."""
    return (flag.get("judge") or {}).get("speaker") or flag["speaker"]


def _rank(flag: dict) -> tuple:
    # A question answered only in part is the mildest of all.
    level = len(ORDER) if flag["label"] == "partial" else ORDER.index(family(flag))
    return level, -flag["confidence"], flag["t"]


def minute(t: float) -> str:
    s = int(t)
    return f"{s // 3600}:{s // 60 % 60:02}:{s % 60:02}" if s >= 3600 else f"{s // 60}:{s % 60:02}"


def cut(text: str, size: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= size else text[:size].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def _meta(data: dict, duration: float, words: dict) -> str:
    parts = [data.get("channel")]
    if date := data.get("published_at"):
        parts.append(_date(date, words))
    if duration:
        h, m = divmod(round(duration / 60), 60)
        parts.append(f"{h} h {m:02} min" if h else f"{m} min")
    return " · ".join(p for p in parts if p)


def summarize(data: dict) -> dict:
    """The flag file with marks in, the content of the image out. Only flags marked correct go in, whatever the
    judge ruled, each under the judge's speaker.

    With more than four speakers, the four with the most flags in the file (any type, any mark) get a box:
    the number of flags stands for how much each one speaks. The texts follow the file's `lang`, Spanish without one.
    """
    lang = data.get("lang") or "es"
    words = TEXTS[lang]
    reviewed = [f for f in data["flags"] if f.get("mark") == "correct" and family(f)]
    talk = Counter(speaker(f) for f in data["flags"])
    names = list(dict.fromkeys([*data.get("speakers", {}).values(), *talk]))
    shown = sorted(names, key=lambda n: -talk[n])[:MAX_BOXES] if len(names) > MAX_BOXES else names
    shown = [n for n in names if n in shown]
    per_box = 3 if len(shown) <= 2 else 2
    # The image lists as many as fit, from this longer list.
    per_list = {1: 8, 2: 6}.get(len(shown), 4)
    duration = data.get("duration") or max([f["t"] for f in data["flags"]], default=0)
    speakers = []
    for name in shown:
        own = sorted((f for f in reviewed if speaker(f) == name), key=_rank)
        counts = Counter(family(f) for f in own)
        speakers.append({
            "name": name,
            "counts": {k: counts[k] for k in ORDER if counts[k]},
            "flags": own[:per_box],
            "highlights": own[:per_list],
            "ticks": [{"t": f["t"], "family": family(f), "confidence": f["confidence"]} for f in own],
        })
    more = len(names) - len(shown)
    return {
        "lang": lang,
        "title": data.get("title") or words["video"].format(data["video_id"]),
        "meta": _meta(data, duration, words),
        "duration": duration,
        "speakers": speakers,
        "more": more,
        "footer": f"{words['more'].format(more)} · {words['footer']}" if more else words["footer"],
    }


def _counts(counts: dict, words: dict) -> str:
    return " · ".join(f"{n} {words['families'][k][0 if n == 1 else 1]}" for k, n in counts.items())


def _date(date: str, words: dict) -> str:
    y, m, d = date.split("-")
    return f"{int(d)} {words['months'][int(m) - 1]} {y}"


def reference(flag: dict, words: dict) -> str:
    """What backs the flag, after the type: the first source, the earlier statement, or nothing for a question."""
    related = flag.get("related") or {}
    if flag["type"] == "contradiction":
        if related.get("t") is not None:
            return f" · vs. {minute(related['t'])}"
        source = (related.get("source") or {}).get("publisher", "")
        when = _date(related["date"], words) if related.get("date") else ""
        parts = [re.split(r"\s+[(–—-]\s*", source)[0], when]
        return " · " + ", ".join(p for p in parts if p) if any(parts) else ""
    if flag["type"] == "question" or not flag.get("sources"):
        return ""
    return " · " + re.split(r"\s+[(–—-]\s*", flag["sources"][0]["publisher"])[0]


def alt_text(summary: dict) -> str:
    """A plain text of the image for screen readers, within the 1000 characters of an alt text on X."""
    words = TEXTS[summary["lang"]]
    lines = [words["alt"].format(summary["title"], summary["meta"])]
    for s in summary["speakers"]:
        flags = " ".join(f"{minute(f['t'])} {words['families'][family(f)][0]}{reference(f, words)}: "
                         f"«{cut(f['quote'], 50)}»" for f in s["highlights"])
        lines.append(f"{s['name']}: {_counts(s['counts'], words) or words['none']}. {flags}".strip())
    if summary["more"]:
        lines.append(words["alt_more"].format(summary["more"]))
    return cut("\n".join(lines), 1000)


def _person(name: str) -> tuple[str, str]:
    """ "Ana Ruiz (invitada)" → ("Ana Ruiz", "invitada")."""
    m = re.fullmatch(r"(.*?)\s*\((.*)\)", name)
    return (m[1], m[2]) if m else (name, "")


def _badge(kind: str, size: str = "") -> str:
    color, icon = FAMILIES[kind]
    return f'<i class="badge" style="background:{color}{size}">{icon}</i>'


def _donut(counts: dict, size: int) -> str:
    """An inline SVG ring of the counts by family, with a 2 px surface gap between the arcs."""
    width = size * 0.08
    r = (size - width) / 2
    around = 2 * math.pi * r
    total = sum(counts.values())
    gap = 3 if len(counts) > 1 else 0
    arcs, start = [], 0.0
    for kind, n in counts.items():
        length = n / total * around
        arcs.append(f'<circle r="{r:.1f}" fill="none" stroke="{FAMILIES[kind][0]}" stroke-width="{width:.1f}" '
                    f'stroke-dasharray="{max(length - gap, 1):.1f} {around:.1f}" stroke-dashoffset="{-start:.1f}"/>')
        start += length
    return (f'<svg width="{size}" height="{size}" viewBox="{-size / 2} {-size / 2} {size} {size}">'
            f'<g transform="rotate(-90)"><circle r="{r:.1f}" fill="none" stroke="#262b32" stroke-width="{width:.1f}"/>'
            f'{"".join(arcs)}</g></svg>')


def _step(duration: float) -> int:
    """The tick step in seconds that gives at most seven ticks."""
    return next((m * 60 for m in (1, 2, 5, 10, 15, 20, 30, 60) if duration / (m * 60) <= 7), 7200)


def _timeline(speakers: list, duration: float) -> str:
    rows = []
    for s in speakers:
        # The mildest first, so the most serious marker sits on top where two overlap.
        ticks = sorted(s["ticks"], key=lambda k: -ORDER.index(k["family"]))
        dots = "".join(
            f'<i style="left:{min(100, k["t"] / duration * 100):.2f}%;width:{d}px;height:{d}px;'
            f'background:{FAMILIES[k["family"]][0]}"></i>'
            for k in ticks for d in [round(12 + 16 * max(0, k["confidence"] - 0.5) * 2)])
        rows.append(f'<div class="row"><span class="who">{escape(_person(s["name"])[0])}</span>'
                    f'<div class="track">{dots}</div></div>')
    step = _step(duration)
    ticks = "".join(f'<span style="left:{t / duration * 100:.2f}%">{t // 3600}:{t // 60 % 60:02}</span>'
                    f'<b style="left:{t / duration * 100:.2f}%"></b>'
                    for t in range(0, int(duration) + 1, step))
    return "".join(rows) + f'<div class="axis">{ticks}</div>'


def _item(flag: dict, words: dict) -> str:
    """One highlight: badge, minute, type and reference on one line, the quote under it."""
    kind = family(flag)
    return (f'<div class="item" style="border-color:{FAMILIES[kind][0]}">'
            f'<p class="ref clamp">{_badge(kind)}<b>{minute(flag["t"])}</b> {words["families"][kind][0]}'
            f'<span class="muted">{escape(reference(flag, words))}</span></p>'
            f'<p class="quote clamp">«{escape(cut(flag["quote"], 160))}»</p></div>')


def _headline(summary: dict, words: dict) -> tuple[str, str]:
    """The big line and the small one: the guests over the whole title, else the title split at its first separator."""
    guests = [_person(s["name"])[0] for s in summary["speakers"] if _person(s["name"])[1].startswith(words["guest"])]
    if guests:
        return words["and"].join(guests), summary["title"]
    m = re.fullmatch(r"(.*?)(?: \| | - | — |: )(.*)", summary["title"])
    return (m[1], m[2]) if m else (summary["title"], "")


def page(summary: dict, template: str, image: str | None = None) -> str:
    """The HTML page of the image: hero, timeline, one panel per speaker with a donut and a list of quotes, footer.

    `image` is the video thumbnail as a data URI; without it the hero is a gradient. Each panel gets the longer
    list of highlights; a script in the template drops the last ones that do not fit.
    """
    words = TEXTS[summary["lang"]]
    speakers = summary["speakers"]
    many = len(speakers) > 2
    donut = 120 if many else 176
    # A small donut has room for the number and one word only.
    label = words["flags"] if many else words["reviewed"]
    columns = []
    for s in speakers:
        name, role = _person(s["name"])
        total = sum(s["counts"].values())
        legend = "".join(f'<span class="chip">{_badge(k)}{n}</span>' for k, n in s["counts"].items())
        items = "".join(_item(f, words) for f in s["highlights"]) or f'<p class="none">{words["empty"]}</p>'
        columns.append(
            f'<section class="speaker"><div class="head">'
            f'<div class="donut">{_donut(s["counts"], donut)}<div><strong>{total}</strong><span>{label}</span></div></div>'
            f'<div class="side"><h2 class="clamp{" one" if many else ""}">{escape(name)}</h2>'
            + (f'<p class="role clamp one">{escape(role)}</p>' if role else "")
            + f'<div class="legend">{legend}</div></div></div>'
            f'<div class="items">{items}</div></section>')
    legend = "".join(f'<span class="chip">{_badge(k)}{words["families"][k][0]}</span>' for k in ORDER)
    footer = escape(summary["footer"]).replace(words["bold"], f"<b>{words['bold']}</b>")
    hero = f'url("{image}")' if image else "linear-gradient(135deg, #3a1d4f, #12304a 55%, #0b0d10)"
    headline, subtitle = _headline(summary, words)
    return Template(template).substitute(lang=summary["lang"], kicker=words["kicker"],
        hero=hero, hero_height="190px" if many else "250px", row_height="30px" if many else "38px",
        donut_size=f"{donut}px", total_size="36px" if many else "44px",
        title=escape(headline), subtitle=escape(subtitle), meta=escape(summary["meta"]),
        timeline=_timeline(speakers, summary["duration"] or 1),
        layout="four" if many else "one" if len(speakers) == 1 else "two", columns="".join(columns),
        legend=legend, footer=footer)
