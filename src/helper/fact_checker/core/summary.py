"""The profile card of one guest: how many of their checked claims were false or misleading, how serious, the devices
they repeat, the questions they dodged and their two most serious claims; and its alt text."""
import base64
import re
from collections import Counter
from html import escape
from pathlib import Path
from string import Template

FONTS = Path(__file__).parent.parent / "fonts"
# The labels of a false or misleading claim: the red and amber families of the player.
WRONG = {"false": "false", "misleading": "misleading", "definition_swap": "misleading", "plan_as_fact": "misleading"}
SEVERITIES = ("serious", "moderate", "minor")
DEVICES = ("fallacy", "contradiction")
TEXTS = {
    "es": {
        "kicker": "Entrevista", "months": "ene feb mar abr may jun jul ago sep oct nov dic".split(),
        "speaking": "{} hablando de {}", "hook": "datos, falsos<br>o engañosos", "of": "de",
        "verdicts": {"false": ("falso", "falsos"), "misleading": ("engañoso", "engañosos"),
                     "nitpick": ("puntualiz.", "puntualiz."), "correct": ("correcto", "correctos")},
        "nitpicks": ("puntualización", "puntualizaciones"),
        "severity": "Gravedad", "levels": {"serious": ("Grave", "grave", "graves"),
                                           "moderate": ("Moderado", "moderado", "moderados"),
                                           "minor": ("Leve", "leve", "leves")},
        "devices": "Lo que más repite", "no_devices": "Nada",
        "dodged": ("Esquivó <b>{} de {}</b> pregunta", "Esquivó <b>{} de {}</b> preguntas"),
        "gravest": "Lo más grave", "no_gravest": "Ningún dato falso o engañoso revisado",
        "verdict": {"false": "Falso", "misleading": "Engañoso"},
        "footer": "Detectado con IA · <b>revisado a mano</b> · fuentes en el enlace",
        "alt": "Ficha de {} en «{}»{}.", "alt_hook": "{} de {} datos, falsos o engañosos", "alt_devices": "Repite",
        "alt_footer": "Detectado con IA, revisado a mano.",
        "labels": {"ad_hominem": "Ad hominem", "tu_quoque": "Y tú más", "false_dilemma": "Falso dilema",
                   "straw_man": "Hombre de paja", "false_cause": "Causa falsa",
                   "hasty_generalization": "Generalización apresurada", "vague_authority": "Autoridad vaga",
                   "insinuation": "Insinuación", "double_standard": "Doble rasero",
                   "cherry_picking": "Datos a conveniencia", "appeal_to_fear": "Apelación al miedo",
                   "self": "Se contradice", "record": "Contradice lo que dijo antes", "promise": "Promesa incumplida"},
    },
    "en": {
        "kicker": "Interview", "months": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
        "speaking": "{} speaking of {}", "hook": "claims, false<br>or misleading", "of": "of",
        "verdicts": {"false": ("false", "false"), "misleading": ("misleading", "misleading"),
                     "nitpick": ("nitpick", "nitpicks"), "correct": ("correct", "correct")},
        "nitpicks": ("nitpick", "nitpicks"),
        "severity": "Severity", "levels": {"serious": ("Serious", "serious", "serious"),
                                           "moderate": ("Moderate", "moderate", "moderate"),
                                           "minor": ("Minor", "minor", "minor")},
        "devices": "Repeats most", "no_devices": "Nothing",
        "dodged": ("Dodged <b>{} of {}</b> question", "Dodged <b>{} of {}</b> questions"),
        "gravest": "Most serious", "no_gravest": "No reviewed false or misleading claim",
        "verdict": {"false": "False", "misleading": "Misleading"},
        "footer": "Detected with AI · <b>reviewed by hand</b> · sources at the link",
        "alt": "Profile of {} in «{}»{}.", "alt_hook": "{} of {} claims, false or misleading", "alt_devices": "Repeats",
        "alt_footer": "Detected with AI, reviewed by hand.",
        "labels": {"ad_hominem": "Ad hominem", "tu_quoque": "Whataboutism", "false_dilemma": "False dilemma",
                   "straw_man": "Straw man", "false_cause": "False cause",
                   "hasty_generalization": "Hasty generalization", "vague_authority": "Vague authority",
                   "insinuation": "Insinuation", "double_standard": "Double standard",
                   "cherry_picking": "Cherry-picking", "appeal_to_fear": "Appeal to fear",
                   "self": "Contradicts themself", "record": "Contradicts what they said before",
                   "promise": "Broken promise"},
    },
}


def speaker(flag: dict) -> str:
    """The judge's speaker when it gave the line to someone else."""
    return (flag.get("judge") or {}).get("speaker") or flag["speaker"]


def minute(t: float) -> str:
    s = int(t)
    return f"{s // 3600}:{s // 60 % 60:02}:{s % 60:02}" if s >= 3600 else f"{s // 60}:{s % 60:02}"


def cut(text: str, size: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= size else text[:size].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def guests(data: dict) -> list[str]:
    """The speakers who get a card: the guests once the voices are told apart, else every speaker."""
    names = list(dict.fromkeys([*data.get("speakers", {}).values(), *(speaker(f) for f in data["flags"])]))
    people = data.get("people")
    return [n for n in people if people[n].get("role") == "guest"] if people else names


def _length(seconds: float) -> str:
    h, m = divmod(round(seconds / 60), 60)
    return f"{h} h {m:02} min" if h else f"{m} min"


def _date(date: str, words: dict) -> str:
    y, m, d = date[:10].split("-")
    return f"{int(d)} {words['months'][int(m) - 1]} {y}"


def _source(flag: dict) -> str:
    return re.split(r"\s+[(–—-]\s*", flag["sources"][0]["publisher"])[0] if flag.get("sources") else ""


def card(data: dict, name: str, series: str | None = None) -> dict:
    """The content of the card of `name` from the flag file with marks. The mark wins, as on the player: a flag
    marked correct counts under its found verdict, whatever the judge ruled, and one marked unfair counts nowhere. A
    puntualización is a figure the judge ruled a nitpick and the person did not mark. The counts of checked claims and
    questions asked come from the file's `claims` and `questions`."""
    lang = data.get("lang") or "es"
    words = TEXTS[lang]
    mine = [f for f in data["flags"] if speaker(f) == name]
    kept = [f for f in mine if f.get("mark") == "correct"]
    wrong = [f for f in kept if f["type"] == "inaccuracy" and f["label"] in WRONG]
    small = [f for f in mine if "mark" not in f and f["type"] == "inaccuracy"
             and (f.get("judge") or {}).get("verdict") == "nitpick"]
    level = lambda f: (f.get("judge") or {}).get("severity")
    # An analysis from before the counts has none: the reviewed flags are then the least that was checked.
    checked = max((data.get("claims") or {}).get(name, 0), len(wrong) + len(small))
    dodged = sum(f["type"] == "question" for f in kept)
    kinds = Counter(WRONG[f["label"]] for f in wrong)
    person = (data.get("people") or {}).get(name, {})
    spoken, duration = person.get("spoken_s"), data.get("duration")
    gravest = sorted(wrong, key=lambda f: (SEVERITIES.index(level(f)) if level(f) in SEVERITIES else 3,
                                           WRONG[f["label"]] != "false", -f["confidence"], f["t"]))[:2]
    return {
        "lang": lang,
        "name": person.get("person") or re.sub(r"\s*\(.*\)$", "", name),
        "title": data.get("title") or data["video_id"],
        "date": _date(data["published_at"], words) if data.get("published_at") else "",
        "length": words["speaking"].format(_length(spoken), _length(duration)) if spoken and duration
        else _length(duration) if duration else "",
        "series": series or "",
        "wrong": len(wrong),
        "checked": checked,
        "verdicts": {"false": kinds["false"], "misleading": kinds["misleading"], "nitpick": len(small),
                     "correct": checked - len(wrong) - len(small)},
        "severity": {s: sum(level(f) == s for f in wrong) for s in SEVERITIES},
        "devices": Counter(words["labels"].get(f["label"], f["label"]) for f in kept
                           if f["type"] in DEVICES).most_common(3),
        "dodged": dodged,
        "asked": max((data.get("questions") or {}).get(name, 0), dodged),
        "gravest": [{"t": f["t"], "quote": f["quote"], "kind": WRONG[f["label"]], "severity": level(f),
                     "correction": f["reason"], "source": _source(f)} for f in gravest],
    }


def _verdict(item: dict, words: dict) -> str:
    """ "Falso, grave." """
    severity = item["severity"] in SEVERITIES and words["levels"][item["severity"]][1]
    return f"{words['verdict'][item['kind']]}{', ' + severity if severity else ''}."


def alt_text(c: dict) -> str:
    """A plain text of the card for screen readers, within the 1000 characters of an alt text on X."""
    words = TEXTS[c["lang"]]
    plural = lambda n, forms: forms[0] if n == 1 else forms[-1]
    names = dict(words["verdicts"], nitpick=words["nitpicks"])
    head = [words["alt"].format(c["name"], cut(c["title"], 80), f" ({c['date']})" if c["date"] else "")]
    if c["series"]:
        head.append(f"{cut(c['series'], 60)}.")
    counts = ", ".join(f"{n} {plural(n, names[k])}" for k, n in c["verdicts"].items() if n)
    head.append(f"{words['alt_hook'].format(c['wrong'], c['checked'])}{': ' + counts if counts else ''}.")
    severity = ", ".join(f"{n} {plural(n, words['levels'][s][1:])}" for s, n in c["severity"].items() if n)
    if severity:
        head.append(f"{words['severity']}: {severity}.")
    if c["devices"]:
        head.append(f"{words['alt_devices']}: {', '.join(f'{label} ×{n}' for label, n in c['devices'])}.")
    head.append(re.sub(r"</?b>", "", plural(c["asked"], words["dodged"]).format(c["dodged"], c["asked"])) + ".")
    tail = [words["alt_footer"]]
    room = 1000 - len(" ".join(head + tail)) - 2
    items = [f"{minute(g['t'])} «{g['quote']}» {_verdict(g, words)} {g['correction']}"
             + (f" ({g['source']})" if g["source"] else "") for g in c["gravest"]]
    gravest = [cut(item, max(room // max(len(items), 1) - 1, 0)) for item in items]
    return cut(" ".join(head + gravest + tail), 1000)


def _icon(symbol: str, color: str) -> str:
    return f'<svg class="vi vc-{color}" width="30" height="30" aria-hidden="true"><use href="#f2-{symbol}"></use></svg>'


def _fonts() -> str:
    """The @font-face rules with each font file inline, so the card asks the network for nothing."""
    data = lambda m: "url(data:font/woff2;base64," + base64.b64encode((FONTS / m[1]).read_bytes()).decode() + ")"
    return re.sub(r"url\(([\w-]+\.woff2)\)", data, (FONTS / "fonts.css").read_text())


LOOKS = {"false": ("fa", "fa", "--red"), "misleading": ("en", "en", "--amber"), "nitpick": ("en", "pu", "--grey"),
         "correct": ("ok", "ok", "--green")}
ORDER = ("false", "misleading", "nitpick", "correct")  # the verdict bar, false first


def page(c: dict, template: str, image: str | None = None) -> str:
    """The HTML page of the card, 1080×1350. `image` is the video thumbnail as a data URI; without it the plate is a
    gradient."""
    words = TEXTS[c["lang"]]
    v = c["verdicts"]
    bar = "".join(f'<i style="flex:{v[k]};background:var({LOOKS[k][2]})"></i>' for k in ORDER if v[k])
    legend = "".join(f'<div class="leg">{_icon(LOOKS[k][0], LOOKS[k][1])}<span><b class="num">{v[k]}</b> '
                     f'{words["verdicts"][k][0 if v[k] == 1 else 1]}</span></div>' for k in ORDER)
    top = max(c["severity"].values()) or 1
    severity = "".join(
        f'<div class="sev{" muted" if s == "minor" else ""}"><span>{words["levels"][s][0]}</span>'
        f'<span class="track"><i style="width:{n / top * 100:.0f}%;opacity:{(1, .55, .3)[i]}"></i></span>'
        f'<span class="num">{n}</span></div>' for i, (s, n) in enumerate(c["severity"].items()))
    devices = "".join(f'<div class="row">{_icon("re", "re")}<span class="grow">{escape(label)}</span>'
                      f'<span class="num bone">×{n}</span></div>' for label, n in c["devices"]) \
        or f'<div class="row muted">{words["no_devices"]}</div>'
    gravest = "".join(
        f'<div class="item"><div class="q">{_icon(LOOKS[g["kind"]][0], LOOKS[g["kind"]][1])}'
        f'<span class="quote">«{escape(cut(g["quote"], 60))}»</span><span class="min num">{minute(g["t"])}</span></div>'
        f'<div class="fix"><b class="c-{g["kind"]}">{escape(_verdict(g, words))}</b> {escape(cut(g["correction"], 110))}'
        + (f' <span class="src">{escape(cut(g["source"], 30))}</span>' if g["source"] else "") + '</div></div>'
        for g in c["gravest"]) or f'<div class="item muted">{words["no_gravest"]}</div>'
    plate = (f'<img class="p-dim" src="{image}" alt=""><div class="band"><img src="{image}" alt=""></div>'
             if image else '<div class="p-none"></div>')
    sub = " · ".join(x for x in (f"«{escape(cut(c['title'], 40))}»", escape(c["length"])) if x)
    dodged = words["dodged"][0 if c["asked"] == 1 else 1].format(c["dodged"], c["asked"])
    return Template(template).substitute(
        lang=c["lang"], fonts=_fonts(), wordmark=(FONTS / "calvet-wordmark.svg").read_text(), plate=plate,
        kicker=escape(" · ".join(x for x in (words["kicker"], c["date"]) if x)),
        series=f'<div class="sc ab series">{escape(c["series"])}</div>' if c["series"] else "",
        name=escape(c["name"]), name_size=92 if len(c["name"]) <= 18 else 72 if len(c["name"]) <= 24 else 56,
        sub=sub, wrong=c["wrong"], of=words["of"], checked=c["checked"], hook=words["hook"], bar=bar, legend=legend,
        severity_head=words["severity"], severity=severity, devices_head=words["devices"], devices=devices,
        dodged=dodged, gravest_head=words["gravest"], gravest=gravest, footer=words["footer"])
