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
        "devices": "Retórica y falacias", "no_devices": "Nada", "more": "y {} más",
        "dodged": ("Esquivó <b>{} de {}</b> preguntas", "Esquivó <b>{}</b> y respondió a medias <b>{}</b> de {} preguntas"),
        "gravest": "Lo más grave", "no_gravest": "Nada grave",
        "verdict": {"false": "Falso", "misleading": "Engañoso"},
        "footer": "Detectado con IA · <b>no revisado por humanos</b> · fuentes en el enlace",
        "alt": "Ficha de {} en «{}»{}.", "alt_hook": "{} de {} datos, falsos o engañosos", "alt_devices": "Retórica y falacias",
        "alt_footer": "Detectado con IA, no revisado por humanos.",
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
        "devices": "Rhetoric and fallacies", "no_devices": "Nothing", "more": "and {} more",
        "dodged": ("Dodged <b>{} of {}</b> questions", "Dodged <b>{}</b> and half-answered <b>{}</b> of {} questions"),
        "gravest": "Most serious", "no_gravest": "Nothing serious",
        "verdict": {"false": "False", "misleading": "Misleading"},
        "footer": "Detected with AI · <b>not reviewed by a person</b> · sources at the link",
        "alt": "Profile of {} in «{}»{}.", "alt_hook": "{} of {} claims, false or misleading", "alt_devices": "Rhetoric and fallacies",
        "alt_footer": "Detected with AI, not reviewed by a person.",
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
    """The content of the card of `name` from the flag file with marks. The card counts what the judge keeps, with no
    review needed (its footer says so); a flag the judge has not ruled on counts too. The mark wins, as on the
    player: a flag marked correct counts under its found verdict, whatever the judge ruled, and one marked unfair
    counts nowhere. A puntualización is a figure the judge ruled a nitpick and the person did not mark. The counts of
    checked claims and questions asked come from the file's `claims` and `questions`."""
    lang = data.get("lang") or "es"
    words = TEXTS[lang]
    mine = [f for f in data["flags"] if speaker(f) == name]
    kept = [f for f in mine if f.get("mark") == "correct"
            or "mark" not in f and (f.get("judge") or {}).get("verdict", "keep") == "keep"]
    wrong = [f for f in kept if f["type"] == "inaccuracy" and f["label"] in WRONG]
    small = [f for f in mine if "mark" not in f and f["type"] == "inaccuracy"
             and (f.get("judge") or {}).get("verdict") == "nitpick"]
    level = lambda f: (f.get("judge") or {}).get("severity")
    # An analysis from before the counts has none: the reviewed flags are then the least that was checked.
    checked = max((data.get("claims") or {}).get(name, 0), len(wrong) + len(small))
    dodged = sum(f["type"] == "question" and f["label"] == "dodged" for f in kept)
    partial = sum(f["type"] == "question" and f["label"] == "partial" for f in kept)
    kinds = Counter(WRONG[f["label"]] for f in wrong)
    # Severity covers every kept flag but questions; the gravest put false figures before misleading ones, then
    # rhetoric, at each level.
    rated = [f for f in kept if f["type"] == "inaccuracy" and f["label"] in WRONG or f["type"] in DEVICES]
    kind = lambda f: WRONG[f["label"]] if f["type"] == "inaccuracy" else "rhetoric"
    devices, grave = Counter(), Counter()
    for f in kept:
        if f["type"] in DEVICES:
            label = words["labels"].get(f["label"]) or words["labels"].get(f.get("closest") or "", f["label"])
            devices[label] += 1
            grave[label] += level(f) == "serious"
    person = (data.get("people") or {}).get(name, {})
    spoken, duration = person.get("spoken_s"), data.get("duration")
    gravest = sorted([f for f in rated if f in wrong or level(f) == "serious"],
                     key=lambda f: (SEVERITIES.index(level(f)) if level(f) in SEVERITIES else 3,
                                    ("false", "misleading", "rhetoric").index(kind(f)), -f["confidence"], f["t"]))[:2]
    return {
        "lang": lang,
        "name": person.get("person") or re.sub(r"\s*\(.*\)$", "", name),
        # The programme, not the whole YouTube title: "The Wild Project #392 - Name | topics" → "The Wild Project #392".
        "title": re.split(r" [-|–—] ", data.get("title") or "")[0] or data["video_id"],
        "date": _date(data["published_at"], words) if data.get("published_at") else "",
        "length": words["speaking"].format(_length(spoken), _length(duration)) if spoken and duration
        else _length(duration) if duration else "",
        "series": series or "",
        "spoken": spoken,
        "wrong": len(wrong),
        "checked": checked,
        "verdicts": {"false": kinds["false"], "misleading": kinds["misleading"], "nitpick": len(small),
                     "correct": checked - len(wrong) - len(small)},
        "severity": {s: sum(level(f) == s for f in rated) for s in SEVERITIES},
        # Ties go to the device with a serious flag.
        "devices": sorted(devices.items(), key=lambda x: (-x[1], -grave[x[0]])),
        "dodged": dodged,
        "partial": partial,
        "asked": max((data.get("questions") or {}).get(name, 0), dodged + partial),
        "gravest": [{"t": f["t"], "quote": f["quote"], "kind": kind(f),
                     "label": words["labels"].get(f["label"], f["label"]), "severity": level(f),
                     "correction": (f.get("judge") or {}).get("reason") or f["reason"] if kind(f) == "rhetoric"
                     else f["reason"], "source": _source(f)} for f in gravest],
    }


def _verdict(item: dict, words: dict) -> str:
    """ "Falso, grave." """
    severity = item["severity"] in SEVERITIES and words["levels"][item["severity"]][1]
    name = item["label"] if item["kind"] == "rhetoric" else words["verdict"][item["kind"]]
    return f"{name}{', ' + severity if severity else ''}."


def _dodged(c: dict, words: dict) -> str:
    """ "Esquivó 2 de 11 preguntas", or with half answers "Esquivó 10 y respondió a medias 10 de 49 preguntas"."""
    if c["partial"]:
        return words["dodged"][1].format(c["dodged"], c["partial"], c["asked"])
    return words["dodged"][0].format(c["dodged"], c["asked"])


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
        head.append(f"{words['alt_devices']}: {', '.join(f'{label} ×{n}' for label, n in c['devices'][:3])}.")
    head.append(re.sub(r"</?b>", "", _dodged(c, words)) + ".")
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
         "correct": ("ok", "ok", "--green"), "rhetoric": ("re", "re", "--mag")}
ORDER = ("false", "misleading", "nitpick", "correct")  # the verdict bar, false first


def page(c: dict, template: str, image: str | None = None) -> str:
    """The HTML page of the card, 1080×1350. `image` is the video thumbnail as a data URI; without it the plate is a
    gradient."""
    words = TEXTS[c["lang"]]
    v = c["verdicts"]
    bar = "".join(f'<i style="flex:{v[k]};background:var({LOOKS[k][2]})"></i>' for k in ORDER if v[k])
    legend = "".join(f'<div class="leg">{_icon(LOOKS[k][0], LOOKS[k][1])}<span><b class="num">{v[k]}</b> '
                     f'{words["verdicts"][k][0 if v[k] == 1 else 1]}</span></div>' for k in ORDER)
    severity = " · ".join(f'<b class="num">{n}</b> {words["levels"][s][1 if n == 1 else 2]}'
                          for s, n in c["severity"].items())
    # Six slots: past six devices, the last slot sums the rest.
    shown = c["devices"] if len(c["devices"]) <= 6 else [
        *c["devices"][:5], (words["more"].format(len(c["devices"]) - 5), sum(n for _, n in c["devices"][5:]))]
    devices = "".join(f'<div class="row">{_icon("re", "re")}<span class="grow">{escape(label)}</span>'
                      f'<span class="num bone">×{n}</span></div>' for label, n in shown) \
        or f'<div class="row muted">{words["no_devices"]}</div>'
    gravest = "".join(
        f'<div class="item"><div class="q">{_icon(LOOKS[g["kind"]][0], LOOKS[g["kind"]][1])}'
        f'<span class="quote">«{escape(cut(g["quote"], 60))}»</span><span class="min num">{minute(g["t"])}</span></div>'
        f'<div class="fix"><b class="c-{g["kind"]}">{escape(_verdict(g, words))}</b> {escape(cut(g["correction"], 92))}'
        + (f' <span class="src">{escape(cut(g["source"], 30))}</span>' if g["source"] else "") + '</div></div>'
        for g in c["gravest"]) or f'<div class="item muted">{words["no_gravest"]}</div>'
    plate = (f'<img class="p-dim" src="{image}" alt=""><div class="band"><img src="{image}" alt=""></div>'
             if image else '<div class="p-none"></div>')
    sub = " · ".join(x for x in (f"«{escape(cut(c['title'], 40))}»", escape(c["length"])) if x)
    dodged = _dodged(c, words)
    return Template(template).substitute(
        lang=c["lang"], fonts=_fonts(), wordmark=(FONTS / "calvet-wordmark.svg").read_text(), plate=plate,
        kicker=escape(" · ".join(x for x in (words["kicker"], c["date"]) if x)),
        series=f'<div class="sc ab series">{escape(c["series"])}</div>' if c["series"] else "",
        name=escape(c["name"]), name_size=92 if len(c["name"]) <= 18 else 72 if len(c["name"]) <= 24 else 56,
        sub=sub, wrong=c["wrong"], of=words["of"], checked=c["checked"], hook=words["hook"], bar=bar, legend=legend,
        severity_head=words["severity"], severity=severity, devices_head=words["devices"], devices=devices,
        dodged=dodged, gravest_head=words["gravest"], gravest=gravest, footer=words["footer"])


COMPARE_TEXTS = {
    "es": {"kicker": ("Comparativa · {} entrevista", "Comparativa · {} entrevistas"), "checked": "datos verificados",
           "line": "{} hablando · {}", "figures": ("{} dato", "{} datos"), "correct": "Datos correctos",
           "per_hour": "Graves por hora", "serious": ("{} grave", "{} graves"), "repeats": "Lo que más repite",
           "times": ("{} vez", "{} veces"), "dodged": "Preguntas esquivadas", "of": "de {}", "nothing": "Nada",
           "percent": "{} %", "legend": {"correct": "Correcto", "nitpick": "Puntualización",
                                         "misleading": "Engañoso", "false": "Falso"},
           "footer": "Detectado con IA · <b>no revisado por humanos</b>",
           "alt": "Comparativa de {} entrevistas: {}. {} datos verificados.",
           "alt_person": "{}: {}; {} correctos ({}); {} graves por hora ({}); lo que más repite: {}; esquivó {} de {} "
                         "preguntas.",
           "alt_footer": "Detectado con IA, no revisado por humanos."},
    "en": {"kicker": ("Comparison · {} interview", "Comparison · {} interviews"), "checked": "claims checked",
           "line": "{} speaking · {}", "figures": ("{} claim", "{} claims"), "correct": "Correct claims",
           "per_hour": "Serious per hour", "serious": ("{} serious", "{} serious"), "repeats": "Most repeated",
           "times": ("{} time", "{} times"), "dodged": "Questions dodged", "of": "of {}", "nothing": "Nothing",
           "percent": "{}%", "legend": {"correct": "Correct", "nitpick": "Nitpick", "misleading": "Misleading",
                                        "false": "False"},
           "footer": "Detected with AI · <b>not reviewed by a person</b>",
           "alt": "Comparison of {} interviews: {}. {} claims checked.",
           "alt_person": "{}: {}; {} correct ({}); {} serious per hour ({}); most repeated: {}; dodged {} of {} "
                         "questions.",
           "alt_footer": "Detected with AI, not reviewed by a person."},
}
BAR_ORDER = ("correct", "nitpick", "misleading", "false")  # the board's order of the comparison bars


def comparison(interviews: list[dict], series: str | None = None) -> dict:
    """The content of the comparison card: one column per guest of the flag files with marks, each from the profile
    card of that guest, so a person's numbers read the same on both cards. The same person in several interviews is
    one column: the canonical name drops the role in brackets, and the counts add up."""
    lang = interviews[0].get("lang") or "es"
    people = {}
    for data in interviews:
        for name in guests(data):
            c = card(data, name)
            key = re.sub(r"\s*\(.*\)$", "", c["name"])
            p = people.setdefault(key, {"name": key, "video_id": data["video_id"], "spoken": 0, "checked": 0,
                                        "verdicts": Counter(), "serious": 0, "devices": Counter(), "dodged": 0,
                                        "asked": 0})
            # A speaking time that one interview lacks makes the sum unknown.
            p["spoken"] = p["spoken"] + c["spoken"] if p["spoken"] is not None and c["spoken"] else None
            p["checked"] += c["checked"]
            p["verdicts"].update(c["verdicts"])
            p["serious"] += c["severity"]["serious"]
            p["devices"].update(dict(c["devices"]))
            p["dodged"] += c["dodged"]
            p["asked"] += c["asked"]
    # One name per programme: "The Wild Project #392" and "#393" are both "The Wild Project".
    titles = [re.sub(r"\s*#\d+$", "", card(data, "")["title"]) for data in interviews]
    return {"lang": lang, "interviews": len(interviews), "series": series or "",
            "programmes": list(dict.fromkeys(titles)),
            "months": _months([d["published_at"] for d in interviews if d.get("published_at")], TEXTS[lang]),
            "checked": sum(p["checked"] for p in people.values()), "people": list(people.values())}


def _months(dates: list[str], words: dict) -> str:
    """ "oct–nov 2026", "nov 2026" or "dic 2025–ene 2026"."""
    if not dates:
        return ""
    (y1, m1), (y2, m2) = (d[:7].split("-") for d in (min(dates), max(dates)))
    name = lambda m: words["months"][int(m) - 1]
    if (y1, m1) == (y2, m2):
        return f"{name(m1)} {y1}"
    return f"{name(m1)}–{name(m2)} {y1}" if y1 == y2 else f"{name(m1)} {y1}–{name(m2)} {y2}"


def _column(p: dict, lang: str) -> dict:
    """The texts of one column."""
    words = COMPARE_TEXTS[lang]
    plural = lambda n, forms: (forms[0] if n == 1 else forms[1]).format(n)
    decimal = lambda x: f"{x:.1f}".replace(".", "," if lang == "es" else ".")
    figures = plural(p["checked"], words["figures"])
    device = p["devices"].most_common(1)
    return {
        "line": words["line"].format(_length(p["spoken"]), figures) if p["spoken"] else figures,
        "share": words["percent"].format(round(100 * p["verdicts"]["correct"] / p["checked"])) if p["checked"]
        else "—",
        "per_hour": decimal(p["serious"] * 3600 / p["spoken"]) if p["spoken"] else "—",
        "serious": plural(p["serious"], words["serious"]),
        "device": device[0][0] if device else words["nothing"],
        "times": plural(device[0][1], words["times"]) if device else "",
    }


def compare_alt(c: dict) -> str:
    """A plain text of the comparison for screen readers, within the 1000 characters of an alt text on X."""
    words = COMPARE_TEXTS[c["lang"]]
    names = dict(TEXTS[c["lang"]]["verdicts"], nitpick=TEXTS[c["lang"]]["nitpicks"])
    head = words["alt"].format(c["interviews"], _header(c), c["checked"])
    tail = words["alt_footer"]
    room = (1000 - len(head) - len(tail)) // len(c["people"]) - 2
    people = []
    for p in c["people"]:
        col = _column(p, c["lang"])
        counts = ", ".join(f"{p['verdicts'][k]} {names[k][0 if p['verdicts'][k] == 1 else -1]}" for k in BAR_ORDER
                           if p["verdicts"][k])
        device = f"{col['device']}, {col['times']}" if col["times"] else col["device"]
        people.append(cut(words["alt_person"].format(p["name"], col["line"].replace(" · ", ", "), col["share"],
                                                     counts, col["per_hour"], col["serious"], device, p["dodged"],
                                                     p["asked"]), room))
    return cut(" ".join([head, *people, tail]), 1000)


def _header(c: dict) -> str:
    """The series, or else the programmes and the month range."""
    return c["series"] or " · ".join([*(f"«{t}»" for t in c["programmes"]), *([c["months"]] if c["months"] else [])])


def compare_page(c: dict, template: str, thumbnails: dict) -> str:
    """The HTML page of the comparison, 1080×1350. `thumbnails` maps a video id to its thumbnail as a data URI, or to
    None for a gradient."""
    words = COMPARE_TEXTS[c["lang"]]
    columns = []
    for p in c["people"]:
        col = _column(p, c["lang"])
        image = thumbnails.get(p["video_id"])
        bar = "".join(f'<i style="flex:{p["verdicts"][k]};background:var({LOOKS[k][2]})"></i>' for k in BAR_ORDER
                      if p["verdicts"][k])
        columns.append(
            f'<div class="col" data-block="col"><div class="thumb">'
            + (f'<img src="{image}" alt="">' if image else '<div class="p-none"></div>') + '</div>'
            f'<div class="name">{escape(p["name"])}</div><div class="lab line">{"&nbsp;".join(escape(col["line"]).rsplit(" ", 1))}</div>'
            f'<div class="lab head">{words["correct"]}</div><div class="val"><span class="big num">{col["share"]}'
            f'</span></div><div class="bar">{bar}</div>'
            f'<div class="lab head">{words["per_hour"]}</div><div class="val"><span class="big num">{col["per_hour"]}'
            f'</span><span class="lab">{col["serious"]}</span></div>'
            f'<div class="lab head">{words["repeats"]}</div><div class="dev">{_icon("re", "re")}'
            f'<span>{escape(col["device"])}</span></div>'
            + (f'<div class="lab times">{col["times"]}</div>' if col["times"] else "")
            + f'<div class="lab head">{words["dodged"]}</div><div class="val"><span class="big num">{p["dodged"]}'
            f'</span><span class="lab">{words["of"].format(p["asked"])}</span></div></div>')
    legend = "".join(f'<div class="leg">{_icon(LOOKS[k][0], LOOKS[k][1])}<span class="lab">{words["legend"][k]}'
                     f'</span></div>' for k in BAR_ORDER)
    kicker = words["kicker"][0 if c["interviews"] == 1 else 1].format(c["interviews"])
    return Template(template).substitute(
        lang=c["lang"], fonts=_fonts(), wordmark=(FONTS / "calvet-wordmark.svg").read_text(), kicker=kicker,
        sub=f'{escape(_header(c))} · <b class="num">{c["checked"]}</b> {words["checked"]}', count=len(columns),
        columns="".join(columns), legend=legend, footer=words["footer"])
