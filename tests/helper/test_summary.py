"""The summary: the profile card of each guest and the comparison card."""
import json
import re
import threading
import urllib.error
import urllib.request
from html import unescape
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

from card_fakes import (
    flag,
    get,
    GUEST,
    HOST_FLAG,
    INTERVIEW,
    MARKS,
    NITPICKS,
    REJECTED,
    save_with_marks,
    SERIOUS_FALSE,
    SERIOUS_MISLEADING,
    start,
    UNFAIR,
    VIDEO,
    visible,
)
from compare_fakes import (
    column,
    compare,
    HOST_QUOTE,
    interview,
    JORGE,
    MARTA,
    NURIA,
    save,
    UNFAIR_QUOTE,
)
from fact_checker import analyses, server
from fact_checker.core import summary
from fact_checker.core.summary import alt_text, card
from fact_checker.server import run_analysis
from fact_checker.store import Store
from fake_servers import FakeCollector
from roles_fakes import GUEST as GUEST_roles, HOST, NamingModel, TITLED, TURNS
from video_fakes import FakeVoices


# S15 A3 · The shareable card takes the speaker from the judge
#
# Story: A flag marked correct that the judge gave from "Luis" to "Ana Ruiz" appears on Ana Ruiz's card, and a flag the
# judge dropped and the person never marked appears nowhere.
# The person's mark wins: a flag the judge dropped and the person marked correct stays.
#
# Setup: an invented flag file as GET /videos/<id> returns it (each flag with its latest mark and its `judge`
# field), with two speakers and no `people`, so each speaker gets a card; passed to fact_checker.core.summary.card and
# alt_text (S35).

LUIS = "Luis (presentador)"


def judged_flag(id, t, speaker, type, label, judge=None, mark=None):
    f = {"id": id, "t": t, "speaker": speaker, "quote": f"frase inventada {id}", "type": type, "label": label,
         "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "sources": [], "note": None,
         "on_player": True}
    if judge:
        f["judge"] = judge
    return f | {"mark": mark} if mark else f


DATA = {"video_id": "abcdefgh", "published_at": "2026-11-10", "status": "done", "stop_reason": None,
        "title": "Entrevista inventada", "channel": "Canal de prueba", "duration": 600.0,
        "speakers": {"SPEAKER_00": LUIS, "SPEAKER_01": GUEST},
        "flags": [
            judged_flag("ad_hominem-60.0", 60, LUIS, "fallacy", "ad_hominem",
                 {"verdict": "keep", "reason": "Lo dice el invitado.", "speaker": GUEST}, "correct"),
            judged_flag("false-120.0", 120, GUEST, "inaccuracy", "false", {"verdict": "drop", "reason": "Error menor."}),
            judged_flag("false-180.0", 180, GUEST, "inaccuracy", "false", {"verdict": "drop", "reason": "Error menor."},
                 "correct"),
        ]}


def test_summary_speaker():
    guest, host = card(DATA, GUEST), card(DATA, LUIS)

    # Case 1 · a flag marked correct that the judge gave from Luis to Ana Ruiz → on Ana Ruiz's card, not Luis's
    assert guest["devices"] == [("Ad hominem", 1)], f"FAIL S15 A3 · Ana Ruiz's devices {guest['devices']}"
    assert host["devices"] == [] and host["wrong"] == 0, f"FAIL S15 A3 · Luis's card {host}"

    # Case 2 · the alt text → the fallacy on Ana Ruiz's alt text only
    assert "Ad hominem ×1" in alt_text(guest), f"FAIL S15 A3 · {alt_text(guest)!r}"
    assert "Ad hominem" not in alt_text(host), f"FAIL S15 A3 · {alt_text(host)!r}"

    # Case 3 · a flag the judge dropped and the person never marked → nowhere on the card or the alt text
    assert "frase inventada false-120.0" not in json.dumps(guest, ensure_ascii=False) + alt_text(guest)

    # Case 4 · a flag the judge dropped and the person marked correct → still on its speaker's card
    assert guest["wrong"] == 1 and [g["quote"] for g in guest["gravest"]] == ["frase inventada false-180.0"], \
        f"FAIL S15 A3 · Ana Ruiz's false figures {guest['gravest']}"
    print("PASS S15 A3 · The shareable card takes the speaker from the judge")


# S26 A4 · The shareable card follows the interface language
#
# Story: A person whose flag file says `lang` "en" exports the card (S35): the image says "claims, false or misleading",
# "False." and "Detected with AI", and the page says "Alt text, ready to copy" above an alt text that starts
# "Profile of". A file with `lang` "es", or none, keeps the Spanish texts.
#
# Setup: an invented flag file with one guest and a false figure marked correct, saved three times in a temporary helper
# home: with `lang` "en", with `lang` "es" and with no `lang`. The image page is built from the card and the image
# template, as the PNG route builds it but with no thumbnail; the share page and the alt text come from the helper's own
# HTTP server on a free local port.

FLAG = {"id": "false-10.0", "t": 10.0, "speaker": "Ann Lee (guest)", "quote": "unemployment fell by half in one year",
        "type": "inaccuracy", "label": "false", "reason": "It fell from 12 % to 11 %.", "confidence": 0.9,
        "related": None, "sources": [{"publisher": "BLS", "url": "https://www.bls.gov/x", "date": "2026-10-01"}],
        "note": None, "on_player": True}
FILE = {"published_at": "2026-11-10", "status": "done", "stop_reason": None, "title": "An invented interview",
        "channel": "Invented Channel", "duration": 60.0, "speakers": {}, "flags": [FLAG]}
LANGS = {"enfile": {"lang": "en"}, "esfile": {"lang": "es"}, "oldfile": {}}


def test_summary_language(tmp_path):
    store = Store(tmp_path)
    for video, lang in LANGS.items():
        store.save(FILE | {"video_id": video} | lang)
        store.add_mark(video, FLAG, "correct", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    get = lambda path: urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_port}{path}", timeout=10).read().decode()
    html = lambda video: summary.page(summary.card(store.load(video) | {"flags": [FLAG | {"mark": "correct"}]},
                                                   FLAG["speaker"]), server.SUMMARY_TEMPLATE.read_text())
    # The image's words, without the markup, styles or line breaks.
    words = lambda video: " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>", "", html(video), flags=re.S)).split())
    try:
        # Case 1 · lang "en" → the card in English: the hook, the verdict of the flag and the footer
        for text in ("claims, false or misleading", "False.", "Detected with AI"):
            assert text in words("enfile"), f"FAIL S26 A4 · the English image lacks {text!r}"
        for text in ("datos, falsos", "Falso.", "Detectado con IA"):
            assert text not in words("enfile"), f"FAIL S26 A4 · the English image still says {text!r}"
        assert '<html lang="en">' in html("enfile"), "FAIL S26 A4 · the English image page is not lang en"

        # Case 2 · lang "en" → the share page and the alt text in English
        page, alt = get("/videos/enfile/summary"), get("/videos/enfile/summary.txt")
        assert "Alt text, ready to copy" in page and 'lang="en"' in page, "FAIL S26 A4 · the share page is not English"
        assert alt.startswith("Profile of Ann Lee in «An invented interview»"), f"FAIL S26 A4 · alt text {alt[:60]!r}"
        assert "0:10" in alt and "False." in alt, f"FAIL S26 A4 · alt text {alt!r}"

        # Case 3 · lang "es", or no lang (an older file) → the Spanish texts
        for video in ("esfile", "oldfile"):
            image, page, alt = words(video), get(f"/videos/{video}/summary"), get(f"/videos/{video}/summary.txt")
            assert "datos, falsos o engañosos" in image and "Detectado con IA" in image, \
                f"FAIL S26 A4 · {video}: the image is not Spanish"
            assert "Texto alternativo, listo para copiar" in page, f"FAIL S26 A4 · {video}: the share page is not Spanish"
            assert alt.startswith("Ficha de Ann Lee en «An invented interview»") and "Falso." in alt, \
                f"FAIL S26 A4 · {video}: alt text {alt[:80]!r}"
    finally:
        httpd.shutdown()
    print("PASS S26 A4 · The shareable card follows the interface language")


# S33 A3 · A role the person sets holds, and the image follows
#
# Story: The reading took a guest for the host. The person sets that speaker to guest from the side panel and exports the
# summary again. The export now has a card for that speaker (S35). When the analysis later names the voices again, the
# role the person set stays.
#
# Setup: a temporary helper home with the flag file of the invented interview of roles_fakes, where the reading named both
# voices host: "Presentador" and "Ana Ruiz (invitada)". Ana Ruiz has one false figure marked correct. The helper's own
# HTTP server runs on a free local port. The later naming is a new analysis of the same video with the voice turns of
# roles_fakes and a fake model that again names Ana Ruiz host.

ANA = "Ana Ruiz (invitada)"
QUOTE = "el paro bajó a la mitad en un solo año"
ANA_FALSE = {"id": "false-1300.0", "t": 1300.0, "speaker": ANA, "quote": QUOTE, "type": "inaccuracy", "label": "false",
        "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "sources": [], "note": None,
        "on_player": True}
BOTH_HOSTS = {"video_id": "entrevista", "published_at": "2026-11-10", "status": "done", "stop_reason": None, "lang": "es",
        "title": "Entrevista inventada a Ana Ruiz", "channel": "Canal inventado", "duration": 3750.0,
        "speakers": {HOST: "Presentador", GUEST_roles: ANA},
        "people": {"Presentador": {"role": "host", "person": "Presentador", "spoken_s": 1260, "set_by": "llm"},
                   ANA: {"role": "host", "person": "Ana Ruiz", "spoken_s": 2460, "set_by": "llm"}},
        "flags": [ANA_FALSE]}


def test_role_set_by_person(tmp_path):
    store = Store(tmp_path)
    store.save(BOTH_HOSTS)
    store.add_mark("entrevista", ANA_FALSE, "correct", "")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}/videos/entrevista"

    def export():
        """The export page (S35): one card and its alt text per guest."""
        return urllib.request.urlopen(f"{base}/summary", timeout=10).read().decode()

    def post(body):
        req = urllib.request.Request(f"{base}/people", method="POST", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status
        except urllib.error.HTTPError as e:
            return e.code

    try:
        # Case 1 · Ana Ruiz taken for the host → the summary leaves her out
        assert QUOTE not in export(), "FAIL S33 A3 · the summary shows a speaker read as host"

        # Case 2 · the person sets Ana Ruiz to guest → 200, kept with set_by person, and the summary shows her
        assert post({"name": ANA, "role": "guest"}) == 200, "FAIL S33 A3 · POST /people did not answer 200"
        entry = store.load("entrevista")["people"][ANA]
        assert entry["role"] == "guest" and entry["set_by"] == "person", f"FAIL S33 A3 · entry {entry}"
        assert "Ana Ruiz" in export() and QUOTE in export(), f"FAIL S33 A3 · the summary does not follow: {export()!r}"

        # Case 3 · a name not in the speakers, or a role other than host or guest → 400, the file unchanged
        assert post({"name": "Nadie", "role": "guest"}) == 400, "FAIL S33 A3 · an unknown name did not answer 400"
        assert post({"name": ANA, "role": "moderadora"}) == 400, "FAIL S33 A3 · a bad role did not answer 400"
        people = store.load("entrevista")["people"]
        assert "Nadie" not in people and people[ANA]["role"] == "guest", f"FAIL S33 A3 · people changed: {people}"
    finally:
        httpd.shutdown()

    # Case 4 · a later naming reads Ana Ruiz as host again → the role the person set stays
    named = {HOST: ("Presentador", "host", "Presentador"), GUEST_roles: (ANA, "host", "Ana Ruiz")}
    run_analysis("entrevista", 0, transcript=TITLED, llm=NamingModel(named), home=tmp_path,
                 voices=FakeVoices(TURNS))
    people = store.load("entrevista")["people"]
    assert people[ANA]["role"] == "guest" and people[ANA]["set_by"] == "person", \
        f"FAIL S33 A3 · the later naming overwrote the person's role: {people[ANA]}"
    assert people[ANA]["spoken_s"] == 2460, f"FAIL S33 A3 · seconds of speech {people[ANA]}"
    assert people["Presentador"]["role"] == "host" and people["Presentador"]["set_by"] == "llm", \
        f"FAIL S33 A3 · host entry {people['Presentador']}"
    print("PASS S33 A3 · A role the person sets holds, and the image follows")


# S35 A1 · The card counts what the judge keeps for one guest
#
# Story: The person exports an invented interview where Ana Ruiz makes 26 checked claims; the judge keeps 4 false or
# misleading flags and rules 2 puntualizaciones, none of them marked by the person; 2 of the 4 are serious; she
# uses "Falso dilema" three times and dodges 2 of the 11 questions put to her. The card reads "4 de 26 datos, falsos o
# engañosos", lists 2 serious among all her kept flags, "Falso dilema ×3" and "Esquivó 2 de 11 preguntas", and shows the two serious claims, each
# with its correction and the name of its source.
# Edge case: WHEN the person marks a flag unfair THEN it counts nowhere on the card, even if the judge kept it.
# Edge case: WHEN the person marks a puntualización correct THEN the mark wins, as on the player: it counts under its found
# verdict, such as false.
#
# Setup: a temporary helper home with the S35 invented interview (card_fakes.INTERVIEW) and its marks in the store: 4 false
# or misleading flags of Ana Ruiz (2 serious, 1 moderate, 1 minor), 3 "Falso dilema", 1 "Ad hominem" and 2 dodged
# questions, all kept by the judge and not marked; 2 puntualizaciones of the judge (a false and a misleading figure) with
# no mark; a serious false figure, a "Falso dilema", a dodged question and a serious misleading figure, kept by the judge
# and marked unfair; a host fallacy. The helper's HTTP server runs on a free local port with the screenshot faked to return the
# card's HTML: `summary.png?person=` gives the card, `summary.txt?person=` its alt text. The second edge case marks the
# false puntualización correct in another helper home.

def test_card_content(tmp_path, monkeypatch):
    save_with_marks(tmp_path)
    base, stop = start(tmp_path, monkeypatch)
    try:
        card = visible(get(f"{base}/videos/{VIDEO}/summary.png?person={quote(GUEST)}"))
        alt = get(f"{base}/videos/{VIDEO}/summary.txt?person={quote(GUEST)}")
    finally:
        stop()

    # Case 1 · the hook → "4 de 26 datos, falsos o engañosos" under the name of the guest
    assert "Ana Ruiz" in card, f"FAIL S35 A1 · the card lacks the guest's name: {card[:200]!r}"
    assert "4 de 26 datos, falsos o engañosos" in card, f"FAIL S35 A1 · no hook '4 de 26': {card!r}"

    # Case 2 · the verdict bar → 2 falsos, 2 engañosos, the 2 unmarked puntualizaciones and 20 correctos
    for want in ("2 falsos", "2 engañosos", "2 puntualiz", "20 correctos"):
        assert want in card, f"FAIL S35 A1 · the verdict bar lacks {want!r}: {card!r}"

    # Case 3 · counts by severity of every kept flag but questions (figures and rhetoric), on one line (2026-11-16)
    # → 2 graves · 4 moderados · 2 leves
    assert "2 graves · 4 moderados · 2 leves" in card, f"FAIL S35 A1 · the severity line is not 2, 4, 2: {card!r}"

    # Case 4 · the devices she repeats and the questions she dodged → "Falso dilema ×3", "Esquivó 2 de 11 preguntas"
    assert "Falso dilema ×3" in card, f"FAIL S35 A1 · no 'Falso dilema ×3': {card!r}"
    assert "Esquivó 2 de 11 preguntas" in card, f"FAIL S35 A1 · no 'Esquivó 2 de 11 preguntas': {card!r}"

    # Case 5 · the two most serious → each quote with "Falso, grave." or "Engañoso, grave.", its correction and source
    for f, verdict in ((SERIOUS_FALSE, "Falso, grave."), (SERIOUS_MISLEADING, "Engañoso, grave.")):
        assert f["quote"] in card, f"FAIL S35 A1 · the card lacks the serious quote {f['quote']!r}"
        assert verdict in card and f["reason"] in card and f["sources"][0]["publisher"] in card, \
            f"FAIL S35 A1 · {f['id']} lacks its verdict, correction or source: {card!r}"
    assert card.index(SERIOUS_FALSE["quote"]) < card.index(SERIOUS_MISLEADING["quote"]), \
        "FAIL S35 A1 · the serious misleading figure comes before the serious false one"

    # Case 6 · a flag marked unfair, or the host's → nowhere on the card or in its alt text
    for f in [UNFAIR, *REJECTED, HOST_FLAG]:
        assert f["quote"] not in card and f["quote"] not in alt, f"FAIL S35 A1 · {f['id']} shows on the card"
    assert "Falso dilema ×4" not in card and "Esquivó 3" not in card, "FAIL S35 A1 · a flag marked unfair is counted"

    # Case 7 · the alt text → the same numbers and both serious quotes, within 1000 characters
    for want in ("Ana Ruiz", "4 de 26", "Falso dilema ×3", "2 de 11", SERIOUS_FALSE["quote"], SERIOUS_MISLEADING["quote"]):
        assert want in alt, f"FAIL S35 A1 · the alt text lacks {want!r}: {alt!r}"
    assert len(alt) <= 1000, f"FAIL S35 A1 · the alt text has {len(alt)} characters"
    print("PASS S35 A1 · The card counts what the judge keeps for one guest")


def test_marked_puntualizacion(tmp_path, monkeypatch):
    save_with_marks(tmp_path, marks=MARKS | {NITPICKS[0]["id"]: "correct"})
    base, stop = start(tmp_path, monkeypatch)
    try:
        card = visible(get(f"{base}/videos/{VIDEO}/summary.png?person={quote(GUEST)}"))
    finally:
        stop()

    # Case 8 · the false puntualización marked correct → it counts as false: 5 de 26, 3 falsos, 1 puntualización
    assert "5 de 26 datos, falsos o engañosos" in card, f"FAIL S35 A1 · a marked puntualización is not false: {card!r}"
    for want in ("3 falsos", "2 engañosos", "1 puntualiz", "20 correctos"):
        assert want in card, f"FAIL S35 A1 · the verdict bar lacks {want!r}: {card!r}"


def test_long_alt_text(tmp_path, monkeypatch):
    long = "y además le digo que " * 30
    flags = [flag(100.0 * n, GUEST, "inaccuracy", "false", f"{n} {long}", severity="serious", source="INE " * 20,
                  reason=long) for n in range(1, 9)]
    data = INTERVIEW | {"title": long, "flags": flags}
    save_with_marks(tmp_path, data, {f["id"]: "correct" for f in flags})
    base, stop = start(tmp_path, monkeypatch)
    try:
        alt = get(f"{base}/videos/{VIDEO}/summary.txt?person={quote(GUEST)}")
    finally:
        stop()

    # Case 9 · very long quotes, reasons and title → an alt text of at most 1000 characters that still names her
    assert len(alt) <= 1000 and "Ana Ruiz" in alt, f"FAIL S35 A1 · alt text of {len(alt)} characters: {alt[:120]!r}"


# S35 A2 · "Exportar resumen" gives one card per guest
# S33 A2 · The summary image leaves out the host: no card and no alt text of the host here; the image: S35 A1 Case 6
#
# Story: The person clicks "Exportar resumen" on a debate with a host and two guests. The page that opens shows two
# cards, one per guest and none for the host, each with its own alt text to copy. The person types "1/3 · Candidatos a
# la Xunta" in the series field and both cards show that line.
#
# Setup: a temporary helper home with an invented debate: the host "Moderadora" and the guests "Ana Ruiz (invitada)" and
# "Xoán Pereira (invitado)" in `people`, one false figure of each guest and one fallacy of the host, all marked correct.
# The helper's HTTP server runs on a free local port with the screenshot faked to return the card's HTML. The button
# opens GET /videos/<id>/summary (tests/extension/panel.test.ts (S14 A3)); the series field is a form field named `series` that
# reloads that page with `?series=`.

DEBATE_VIDEO = "debate35"
MODERATOR, XOAN = "Moderadora", "Xoán Pereira (invitado)"
PERSON = {GUEST: "Ana Ruiz", XOAN: "Xoán Pereira"}
SERIES = "1/3 · Candidatos a la Xunta"
DEBATE_FLAGS = [flag(60.0, MODERATOR, "fallacy", "ad_hominem", "ustedes nunca responden a nada", severity="minor"),
         flag(300.0, GUEST, "inaccuracy", "false", "el paro bajó a la mitad en un año", severity="serious",
              source="INE", reason="Bajó un 8 %."),
         flag(900.0, XOAN, "inaccuracy", "misleading", "somos los que más invierten en sanidad", severity="moderate",
              source="Ministerio de Sanidad", reason="Por habitante es la novena.")]
DEBATE = {"video_id": DEBATE_VIDEO, "published_at": "2026-11-12", "status": "done", "stop_reason": None, "lang": "es",
          "spoken": "es", "title": "Debate inventado", "channel": "Canal inventado", "duration": 5400.0,
          "speakers": {"SPEAKER_00": MODERATOR, "SPEAKER_01": GUEST, "SPEAKER_02": XOAN},
          "people": {MODERATOR: {"role": "host", "person": MODERATOR, "spoken_s": 900, "set_by": "llm"},
                     GUEST: {"role": "guest", "person": "Ana Ruiz", "spoken_s": 2000, "set_by": "llm"},
                     XOAN: {"role": "guest", "person": "Xoán Pereira", "spoken_s": 2100, "set_by": "person"}},
          "claims": {GUEST: 12, XOAN: 15}, "questions": {GUEST: 6, XOAN: 7}, "flags": DEBATE_FLAGS}


def cards(page: str) -> list[tuple[str, str]]:
    """Each card image of the page with the alt text box after it: (image address, alt text)."""
    found = re.findall(r'<img\b[^>]*\bsrc="([^"]*summary\.png[^"]*)".*?<textarea\b[^>]*>(.*?)</textarea>', page, re.S)
    return [(unescape(src), unescape(alt)) for src, alt in found]


def test_card_per_guest(tmp_path, monkeypatch):
    save_with_marks(tmp_path, DEBATE, {f["id"]: "correct" for f in DEBATE_FLAGS})
    base, stop = start(tmp_path, monkeypatch)
    try:
        page = get(f"{base}/videos/{DEBATE_VIDEO}/summary")
        with_series = get(f"{base}/videos/{DEBATE_VIDEO}/summary?series={quote(SERIES)}")
        shown = cards(page)
        named = cards(with_series)
        images = {src: visible(get(f"{base}/videos/{DEBATE_VIDEO}/{src}")) for src, _ in named}
    finally:
        stop()

    # Case 1 · the export page → two cards, one per guest in the order of the file, none for the host
    people = [parse_qs(urlsplit(src).query).get("person", [""])[0] for src, _ in shown]
    assert people == [GUEST, XOAN], f"FAIL S35 A2 · cards for {people}, want {[GUEST, XOAN]}"

    # Case 2 · each card → its own alt text, with that guest's name and quote and nothing of the other guest
    for (src, alt), (mine, theirs) in zip(shown, ((GUEST, XOAN), (XOAN, GUEST))):
        assert PERSON[mine] in alt and PERSON[theirs] not in alt, f"FAIL S35 A2 · alt text of {mine}: {alt!r}"
        assert MODERATOR not in alt and "ustedes nunca" not in alt, f"FAIL S35 A2 · the host is in the alt text of {mine}"

    # Case 3 · the page → a series field the person types in
    assert re.search(r'<input\b[^>]*\bname="series"', page), "FAIL S35 A2 · the page has no series field"

    # Case 4 · the series typed → both card addresses and both alt texts carry "1/3 · Candidatos a la Xunta"
    assert len(named) == 2, f"FAIL S35 A2 · {len(named)} cards with the series"
    for src, alt in named:
        assert parse_qs(urlsplit(src).query).get("series") == [SERIES], f"FAIL S35 A2 · card address {src!r}"
        assert SERIES in alt, f"FAIL S35 A2 · alt text without the series: {alt!r}"
    assert re.search(r'<input\b[^>]*\bvalue="1/3 · Candidatos a la Xunta"', unescape(with_series)), \
        "FAIL S35 A2 · the series field forgets what the person typed"

    # Case 5 · each card image → the series line and its own guest
    for (src, _), mine in zip(named, (GUEST, XOAN)):
        image = images[src]
        assert SERIES in image, f"FAIL S35 A2 · the card of {mine} lacks the series line"
        assert PERSON[mine] in image, f"FAIL S35 A2 · the card at {src} is not {mine}'s"
    print("PASS S35 A2 · \"Exportar resumen\" gives one card per guest")


# S35 A4 · A shared analysis gives the same card
#
# Story: The person analyses the invented interview with sharing on and marks nothing. A second person opens the same
# video, gets the shared analysis and exports it, marking nothing either. Both cards count what the judge keeps and read
# the same "6 de 26" and "Esquivó 3 de 11".
#
# Setup: the S28 fake collector on a free local port, empty. The first person's helper home holds the S35 invented
# interview (card_fakes.INTERVIEW) with no marks, and uploads it the way the helper does after a whole analysis with
# sharing on (analyses.upload). The author's approval is out of this test: the fake collector serves what it holds. The
# second person's helper home points `feedback_url` to the collector and has no flag file. Each helper runs its HTTP
# server on a free port with the screenshot faked to return the card's HTML. With no marks, the judge's 6 false or
# misleading flags and 3 dodged questions of Ana Ruiz count on both cards.

def test_shared_card(tmp_path, monkeypatch):
    collector = FakeCollector()
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (second / "config.toml").write_text(f'feedback_url = "{collector.url}"\nshare_marks = false\n')
    save_with_marks(first, marks={})
    try:
        analyses.upload(first, collector.url, json.loads((first / "videos" / f"{VIDEO}.json").read_text()))
        base, stop = start(first, monkeypatch)
        try:
            mine = visible(get(f"{base}/videos/{VIDEO}/summary.png?person={quote(GUEST)}"))
        finally:
            stop()

        base, stop = start(second, monkeypatch)
        try:
            assert get(f"{base}/videos/{VIDEO}?at=0&lang=es"), "FAIL S35 A4 · the second person got no analysis"
            theirs = visible(get(f"{base}/videos/{VIDEO}/summary.png?person={quote(GUEST)}"))
            alt = get(f"{base}/videos/{VIDEO}/summary.txt?person={quote(GUEST)}")
        finally:
            stop()
    finally:
        collector.stop()

    # Case 1 · the upload → the claims and questions per speaker travel, as numbers only
    sent = next(r["body"]["analysis"] for r in collector.requests if r["method"] == "PUT")
    assert sent.get("claims") == INTERVIEW["claims"] and sent.get("questions") == INTERVIEW["questions"], \
        f"FAIL S35 A4 · uploaded claims {sent.get('claims')!r}, questions {sent.get('questions')!r}"

    # Case 2 · the first person's card → "6 de 26" and "Esquivó 3 de 11"
    assert "6 de 26" in mine and "Esquivó 3 de 11" in mine, f"FAIL S35 A4 · the first card: {mine!r}"

    # Case 3 · the second person's card and alt text → the same "6 de 26" and "Esquivó 3 de 11"
    assert "6 de 26" in theirs and "Esquivó 3 de 11" in theirs, f"FAIL S35 A4 · the shared card: {theirs!r}"
    assert "6 de 26" in alt and "Esquivó 3 de 11" in alt, f"FAIL S35 A4 · the shared alt text: {alt!r}"
    print("PASS S35 A4 · A shared analysis gives the same card")


# S36 A1 · The comparison counts what the judge keeps, per hour of speech
#
# Story: The person runs `fact-checker compare` with three analysed invented interviews: Marta Ibarra speaks 41 min with
# 26 checked figures, 17 correct and 3 serious flags; Jorge Salcedo and Núria Vidal likewise. The command prints the path
# of a PNG and of its alt text. The card reads "Comparativa · 3 entrevistas", "78 datos verificados" and, in Marta's
# column, "41 min hablando · 26 datos", "65 %" correct, "4,4" serious per hour with "3 graves", "Datos a conveniencia ·
# 4 veces" and "Preguntas esquivadas 2 de 11". The alt text holds the same numbers within 1000 characters.
# Edge case: WHEN a flag is marked unfair, or a host makes it THEN it counts in no column, as on the profile card.
# Edge case: WHEN a person has no speaking time (the voices were not told apart) THEN "Graves por hora" shows "—" and
# the count "3 graves" stays.
#
# Setup: a temporary helper home with the three S36 invented interviews (compare_fakes.MARTA, JORGE, NURIA) and their marks
# in the store. Each holds the guest's kept flags with no mark, one serious flag of the guest's most repeated device
# marked unfair, and one serious flag of the host. `fact-checker compare marta36 jorge36 nuria36` runs in process in a
# temporary folder, with the thumbnail download off and the screenshot faked to return the card's HTML, so compare.png
# holds that HTML. The edge case on speaking time runs Núria's interview again without `people` (no voices told apart),
# with 3 serious figures.

NAMES = ["Marta Ibarra", "Jorge Salcedo", "Núria Vidal"]


def test_compare_content(tmp_path, monkeypatch, capsys):
    home, out = tmp_path / "home", tmp_path / "out"
    out.mkdir()
    save(home, MARTA, JORGE, NURIA)
    code, printed = compare(home, out, monkeypatch, capsys, "marta36", "jorge36", "nuria36")

    # Case 1 · the command → exit 0 and the paths of compare.png and compare.txt in the current folder
    assert code == 0, f"FAIL S36 A1 · compare exited {code}: {printed!r}"
    png, txt = out / "compare.png", out / "compare.txt"
    assert str(png) in printed and str(txt) in printed, f"FAIL S36 A1 · the paths are not printed: {printed!r}"
    assert png.exists() and txt.exists(), "FAIL S36 A1 · compare.png or compare.txt is missing"
    card, alt = visible(png.read_text()), txt.read_text()

    # Case 2 · the header → "Comparativa · 3 entrevistas", the programme and months, "78 datos verificados"
    for want in ("Comparativa · 3 entrevistas", "«La entrevista de las 9» · oct–nov 2026", "78 datos verificados"):
        assert want in card, f"FAIL S36 A1 · the header lacks {want!r}: {card[:300]!r}"

    # Case 3 · one column per guest, in the order of the ids → Marta, Jorge, Núria
    assert all(n in card for n in NAMES), f"FAIL S36 A1 · a guest has no column: {card!r}"
    assert card.index(NAMES[0]) < card.index(NAMES[1]) < card.index(NAMES[2]), "FAIL S36 A1 · columns out of order"

    # Case 4 · Marta's column → her time and figures, correct share, serious per hour, device and dodged questions
    marta = column(card, "Marta Ibarra", NAMES)
    for want in ("41 min hablando · 26 datos", "Datos correctos 65 %", "Graves por hora 4,4 3 graves",
                 "Datos a conveniencia 4 veces", "Preguntas esquivadas 2 de 11"):
        assert want in marta, f"FAIL S36 A1 · Marta's column lacks {want!r}: {marta!r}"

    # Case 5 · Jorge's and Núria's columns → their own numbers
    jorge, nuria = column(card, "Jorge Salcedo", NAMES), column(card, "Núria Vidal", NAMES)
    for want in ("52 min hablando · 31 datos", "77 %", "2,3 2 graves", "Y tú más 5 veces", "4 de 12"):
        assert want in jorge, f"FAIL S36 A1 · Jorge's column lacks {want!r}: {jorge!r}"
    for want in ("47 min hablando · 21 datos", "62 %", "5,1 4 graves", "Apelación al miedo 3 veces", "1 de 10"):
        assert want in nuria, f"FAIL S36 A1 · Núria's column lacks {want!r}: {nuria!r}"

    # Case 6 · a flag marked unfair or the host's → in no column: not 5 uses, not 4 serious, no host quote or column
    assert "5 veces" not in marta and "4 graves" not in marta, f"FAIL S36 A1 · an unfair flag counts: {marta!r}"
    assert "Presentador" not in card and HOST_QUOTE not in card and UNFAIR_QUOTE not in card, \
        "FAIL S36 A1 · the host or an unfair flag shows on the card"

    # Case 7 · the footer → «Detectado con IA · no revisado por humanos»
    assert "Detectado con IA · no revisado por humanos" in card, "FAIL S36 A1 · the footer is not the S36 one"

    # Case 8 · the alt text → the same numbers, within 1000 characters
    for want in ("3 entrevistas", "78 datos", "Marta Ibarra", "41 min", "26 datos", "65 %", "4,4", "3 graves",
                 "Datos a conveniencia", "2 de 11", "Jorge Salcedo", "77 %", "Núria Vidal", "62 %",
                 "no revisado por humanos"):
        assert want in alt, f"FAIL S36 A1 · the alt text lacks {want!r}: {alt!r}"
    assert len(alt) <= 1000, f"FAIL S36 A1 · the alt text has {len(alt)} characters"
    print("PASS S36 A1 · The comparison counts what the judge keeps, per hour of speech")


def test_no_speaking_time(tmp_path, monkeypatch, capsys):
    home, out = tmp_path / "home", tmp_path / "out"
    out.mkdir()
    silent = interview("nuria36", "Núria Vidal", None, spoken_s=2820, claims=21, asked=10, false=3, misleading=3,
                       nitpicks=2, serious=3, device="appeal_to_fear", repeats=3, dodged=1, voices=False)
    save(home, MARTA, silent)
    code, printed = compare(home, out, monkeypatch, capsys, "marta36", "nuria36")
    assert code == 0, f"FAIL S36 A1 · compare exited {code}: {printed!r}"
    nuria = column(visible((out / "compare.png").read_text()), "Núria Vidal", ["Marta Ibarra", "Núria Vidal"])

    # Case 9 · no speaking time → "Graves por hora —" with the count "3 graves", and no "hablando"
    assert "Graves por hora — 3 graves" in nuria, f"FAIL S36 A1 · no '—' per hour: {nuria!r}"
    assert "hablando" not in nuria and "21 datos" in nuria, f"FAIL S36 A1 · a speaking time is made up: {nuria!r}"


# S36 A2 · The same person in two interviews is one column
#
# Story: The person compares two interviews of Marta Ibarra, one named "Marta Ibarra (invitada)" by the voices and one
# "Marta Ibarra", and one of Jorge Salcedo. The card has two columns; Marta's adds both interviews: her speaking time,
# checked figures, serious flags and questions. The header says "3 entrevistas".
# Edge case: WHEN the interviews hold more than three guests, or an id is not analysed THEN the command writes no card
# and names the guests, or the id, in one line.
#
# Setup: a temporary helper home with the S36 invented interviews of Marta Ibarra (compare_fakes.MARTA: voice "Marta Ibarra
# (invitada)", 41 min, 26 figures with 2 false, 4 misleading and 3 puntualizaciones, 3 serious, 2 of 11 questions dodged)
# and Jorge Salcedo (compare_fakes.JORGE), and a second invented interview of Marta whose voice is "Marta Ibarra", with no
# person name: 20 min, 10 figures with 1 false, 1 misleading and 1 puntualización, 1 serious, 1 of 5 questions dodged.
# A debate of three invented guests feeds the edge case. `fact-checker compare` runs in process in a temporary folder,
# with the thumbnail download off and the screenshot faked to return the card's HTML (compare_fakes.compare).

MARTA_2 = interview("marta36b", "Marta Ibarra", None, spoken_s=1200, claims=10, asked=5, false=1, misleading=1,
                    nitpicks=1, serious=1, device="cherry_picking", repeats=1, dodged=1, published_at="2026-11-10",
                    title="Hoy por la tarde | Marta Ibarra")


def test_same_person(tmp_path, monkeypatch, capsys):
    home, out = tmp_path / "home", tmp_path / "out"
    out.mkdir()
    save(home, MARTA, MARTA_2, JORGE)
    code, printed = compare(home, out, monkeypatch, capsys, "marta36", "jorge36", "marta36b")
    assert code == 0, f"FAIL S36 A2 · compare exited {code}: {printed!r}"
    card, alt = visible((out / "compare.png").read_text()), (out / "compare.txt").read_text()

    # Case 1 · two interviews of Marta and one of Jorge → two columns, Marta first, and "3 entrevistas" in the header
    assert "Comparativa · 3 entrevistas" in card, f"FAIL S36 A2 · the header lacks '3 entrevistas': {card[:300]!r}"
    assert card.count("Marta Ibarra") == 1 and "(invitada)" not in card, \
        f"FAIL S36 A2 · Marta is not one column: {card!r}"
    assert card.index("Marta Ibarra") < card.index("Jorge Salcedo"), "FAIL S36 A2 · columns out of order"

    # Case 2 · Marta's column adds both → 1 h 01 min, 36 figures, 24 correct (67 %), 4 serious in 61 min (3,9),
    # "Datos a conveniencia" 5 times, 3 of 16 questions dodged
    marta = column(card, "Marta Ibarra", ["Marta Ibarra", "Jorge Salcedo"])
    for want in ("1 h 01 min hablando · 36 datos", "Datos correctos 67 %", "Graves por hora 3,9 4 graves",
                 "Datos a conveniencia 5 veces", "Preguntas esquivadas 3 de 16"):
        assert want in marta, f"FAIL S36 A2 · Marta's column lacks {want!r}: {marta!r}"

    # Case 3 · the header and the alt text → both programmes, 67 figures checked, Marta once with the added numbers
    for want in ("La entrevista de las 9", "Hoy por la tarde", "oct–nov 2026", "67 datos verificados"):
        assert want in card, f"FAIL S36 A2 · the header lacks {want!r}: {card[:300]!r}"
    assert alt.count("Marta Ibarra") == 1 and "36 datos" in alt and "3 de 16" in alt, \
        f"FAIL S36 A2 · the alt text does not add Marta's interviews: {alt!r}"


THREE_GUESTS = interview("debate36", "Ana Ruiz (invitada)", "Ana Ruiz", spoken_s=1500, claims=8, asked=4, false=1,
                   misleading=0, nitpicks=0, serious=1, device="false_dilemma", repeats=1, dodged=0)
THREE_GUESTS[0]["people"] |= {"Xoán Pereira (invitado)": {"role": "guest", "person": "Xoán Pereira", "spoken_s": 1400},
                        "Lucía Prado (invitada)": {"role": "guest", "person": "Lucía Prado", "spoken_s": 1300}}


def test_too_many_or_unknown(tmp_path, monkeypatch, capsys):
    home, out = tmp_path / "home", tmp_path / "out"
    out.mkdir()
    save(home, THREE_GUESTS, MARTA)

    # Case 4 · a debate of three guests and one interview of Marta → four guests: no card, one line naming them
    code, printed = compare(home, out, monkeypatch, capsys, "debate36", "marta36")
    assert code != 0, "FAIL S36 A2 · four guests gave a card"
    assert not (out / "compare.png").exists() and not (out / "compare.txt").exists(), \
        "FAIL S36 A2 · a card was written for four guests"
    lines = printed.strip().splitlines()
    assert len(lines) == 1 and all(n in lines[0] for n in ("Ana Ruiz", "Xoán Pereira", "Lucía Prado", "Marta Ibarra")), \
        f"FAIL S36 A2 · the line does not name the four guests: {printed!r}"

    # Case 5 · an id that is not analysed → no card, one line naming the id
    code, printed = compare(home, out, monkeypatch, capsys, "marta36", "nosuch36")
    assert code != 0 and not (out / "compare.png").exists(), "FAIL S36 A2 · a card for an id not analysed"
    lines = printed.strip().splitlines()
    assert len(lines) == 1 and "nosuch36" in lines[0], f"FAIL S36 A2 · the line does not name the id: {printed!r}"
    print("PASS S36 A2 · The same person in two interviews is one column")
