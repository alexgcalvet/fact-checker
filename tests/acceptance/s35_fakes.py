"""The invented interview that the S35 tests share, and the helpers that serve it.

INTERVIEW is a flag file as the helper keeps it: the host "Presentador" and the guest "Ana Ruiz (invitada)" (person
"Ana Ruiz"), 26 checked claims and 11 questions put to Ana Ruiz. MARKS gives the verdict the person gave each flag;
a flag missing from MARKS has no mark, such as the judge's two puntualizaciones (NITPICKS). Every name, quote and
figure is invented.
"""
import re
import threading
import urllib.request
from html import unescape
from http.server import ThreadingHTTPServer

from fact_checker import server
from fact_checker.store import Store

VIDEO = "entrevista35"
HOST, GUEST = "Presentador", "Ana Ruiz (invitada)"


def flag(t, speaker, type, label, quote, verdict="keep", severity=None, source=None, reason="Motivo inventado."):
    judge = {"verdict": verdict, "reason": "Regla inventada."} | ({"severity": severity} if severity else {})
    return {"id": f"{label}-{t:.1f}", "t": t, "speaker": speaker, "quote": quote, "type": type, "label": label,
            "reason": reason, "confidence": 0.9, "related": None, "note": None, "on_player": True, "judge": judge,
            "sources": [{"publisher": source, "url": "https://example.org/fuente", "date": "2026-10-01"}]
            if source else []}


SERIOUS_FALSE = flag(840.0, GUEST, "inaccuracy", "false", "el paro juvenil ha bajado a la mitad desde que gobernamos",
                     severity="serious", source="INE", reason="Bajó del 31 % al 26 %: un 16 %, no la mitad.")
SERIOUS_MISLEADING = flag(2460.0, GUEST, "inaccuracy", "misleading", "hemos hecho más vivienda pública que nadie",
                          severity="serious", source="Ministerio de Vivienda",
                          reason="Cuenta las iniciadas; en terminadas es tercera de cinco.")
UNFAIR = flag(2600.0, GUEST, "inaccuracy", "false", "la sanidad recibe el doble que hace diez años",
              severity="serious", source="Hacienda")
UNMARKED = [flag(2700.0, GUEST, "fallacy", "false_dilemma", "o nosotros o el caos de siempre"),
            flag(2800.0, GUEST, "question", "dodged", "eso ya lo explicaremos en su momento"),
            flag(3000.0, GUEST, "inaccuracy", "misleading", "somos la región que más crece de toda Europa",
                 severity="serious", source="Eurostat")]
# The judge's puntualizaciones, which the person leaves unmarked.
NITPICKS = [flag(300.0, GUEST, "inaccuracy", "false", "llevamos doce años gobernando", verdict="nitpick", source="BOE"),
            flag(1800.0, GUEST, "inaccuracy", "misleading", "el puerto mueve un millón de contenedores",
                 verdict="nitpick", source="Puertos del Estado")]
HOST_FLAG = flag(60.0, HOST, "fallacy", "ad_hominem", "la oposición no tiene autoridad para hablar de nada",
                 severity="minor")

CORRECT = [
    SERIOUS_FALSE,
    SERIOUS_MISLEADING,
    flag(1200.0, GUEST, "inaccuracy", "false", "los alquileres han bajado este año", severity="moderate",
         source="Banco de España"),
    flag(1500.0, GUEST, "inaccuracy", "plan_as_fact", "ya funcionan los nuevos centros de salud", severity="minor",
         source="Consejería de Sanidad"),
    flag(600.0, GUEST, "fallacy", "false_dilemma", "o bajamos impuestos o cierran las empresas", severity="moderate"),
    flag(1100.0, GUEST, "fallacy", "false_dilemma", "o se está con nosotros o con ellos", severity="moderate"),
    flag(2000.0, GUEST, "fallacy", "false_dilemma", "o este plan o ninguno", severity="moderate"),
    flag(2200.0, GUEST, "fallacy", "ad_hominem", "mi rival no sabe ni lo que firma", severity="minor"),
    flag(900.0, GUEST, "question", "dodged", "lo importante es lo que hemos hecho", severity="minor"),
    flag(1700.0, GUEST, "question", "dodged", "esa pregunta habría que hacérsela a otros", severity="minor"),
    HOST_FLAG,
]
FLAGS = sorted(CORRECT + NITPICKS + [UNFAIR] + UNMARKED, key=lambda f: f["t"])
MARKS = {f["id"]: "correct" for f in CORRECT} | {UNFAIR["id"]: "unfair"}

INTERVIEW = {
    "video_id": VIDEO, "published_at": "2026-11-12", "status": "done", "stop_reason": None, "lang": "es",
    "spoken": "es", "title": "La entrevista de las 9", "channel": "Canal inventado", "duration": 3720.0,
    "speakers": {"SPEAKER_00": HOST, "SPEAKER_01": GUEST},
    "people": {HOST: {"role": "host", "person": HOST, "spoken_s": 1260, "set_by": "llm"},
               GUEST: {"role": "guest", "person": "Ana Ruiz", "spoken_s": 2460, "set_by": "llm"}},
    "claims": {GUEST: 26, HOST: 3},
    "questions": {GUEST: 11},
    "flags": FLAGS,
}


def save_with_marks(home, data=INTERVIEW, marks=MARKS) -> Store:
    store = Store(home)
    store.save(data)
    for f in data["flags"]:
        if f["id"] in marks:
            store.add_mark(data["video_id"], f, marks[f["id"]], "", shared=False)
    return store


def start(home, monkeypatch):
    """The helper's HTTP server on a free local port, with no thumbnail download and a screenshot that returns the
    HTML of the card instead of a PNG. Returns the base URL and the stop function."""
    monkeypatch.setattr(server, "thumbnail", lambda video_id, home: None)
    monkeypatch.setattr(server, "screenshot", lambda html, *args, **kwargs: html.encode())
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_port}", httpd.shutdown


def get(url: str) -> str:
    return urllib.request.urlopen(url, timeout=10).read().decode()


def visible(html: str) -> str:
    """The text of a page as a reader sees it: no style, script or tags, one space between words."""
    html = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())
