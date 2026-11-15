"""S35 A2 · "Exportar resumen" gives one card per guest

Story: The person clicks "Exportar resumen" on a debate with a host and two guests. The page that opens shows two
cards, one per guest and none for the host, each with its own alt text to copy. The person types "1/3 · Candidatos a
la Xunta" in the series field and both cards show that line.

Setup: a temporary helper home with an invented debate: the host "Moderadora" and the guests "Ana Ruiz (invitada)" and
"Xoán Pereira (invitado)" in `people`, one false figure of each guest and one fallacy of the host, all marked correct.
The helper's HTTP server runs on a free local port with the screenshot faked to return the card's HTML. The button
opens GET /videos/<id>/summary (s14-a3-export-button.test.ts); the series field is a form field named `series` that
reloads that page with `?series=`.
"""
import re
from html import unescape
from urllib.parse import parse_qs, quote, urlsplit

from s35_fakes import flag, get, save_with_marks, start, visible

VIDEO = "debate35"
HOST, ANA, XOAN = "Moderadora", "Ana Ruiz (invitada)", "Xoán Pereira (invitado)"
PERSON = {ANA: "Ana Ruiz", XOAN: "Xoán Pereira"}
SERIES = "1/3 · Candidatos a la Xunta"
FLAGS = [flag(60.0, HOST, "fallacy", "ad_hominem", "ustedes nunca responden a nada", severity="minor"),
         flag(300.0, ANA, "inaccuracy", "false", "el paro bajó a la mitad en un año", severity="serious",
              source="INE", reason="Bajó un 8 %."),
         flag(900.0, XOAN, "inaccuracy", "misleading", "somos los que más invierten en sanidad", severity="moderate",
              source="Ministerio de Sanidad", reason="Por habitante es la novena.")]
DEBATE = {"video_id": VIDEO, "published_at": "2026-11-12", "status": "done", "stop_reason": None, "lang": "es",
          "spoken": "es", "title": "Debate inventado", "channel": "Canal inventado", "duration": 5400.0,
          "speakers": {"SPEAKER_00": HOST, "SPEAKER_01": ANA, "SPEAKER_02": XOAN},
          "people": {HOST: {"role": "host", "person": HOST, "spoken_s": 900, "set_by": "llm"},
                     ANA: {"role": "guest", "person": "Ana Ruiz", "spoken_s": 2000, "set_by": "llm"},
                     XOAN: {"role": "guest", "person": "Xoán Pereira", "spoken_s": 2100, "set_by": "person"}},
          "claims": {ANA: 12, XOAN: 15}, "questions": {ANA: 6, XOAN: 7}, "flags": FLAGS}


def cards(page: str) -> list[tuple[str, str]]:
    """Each card image of the page with the alt text box after it: (image address, alt text)."""
    found = re.findall(r'<img\b[^>]*\bsrc="([^"]*summary\.png[^"]*)".*?<textarea\b[^>]*>(.*?)</textarea>', page, re.S)
    return [(unescape(src), unescape(alt)) for src, alt in found]


def test_card_per_guest(tmp_path, monkeypatch):
    save_with_marks(tmp_path, DEBATE, {f["id"]: "correct" for f in FLAGS})
    base, stop = start(tmp_path, monkeypatch)
    try:
        page = get(f"{base}/videos/{VIDEO}/summary")
        with_series = get(f"{base}/videos/{VIDEO}/summary?series={quote(SERIES)}")
        shown = cards(page)
        named = cards(with_series)
        images = {src: visible(get(f"{base}/videos/{VIDEO}/{src}")) for src, _ in named}
    finally:
        stop()

    # Case 1 · the export page → two cards, one per guest in the order of the file, none for the host
    people = [parse_qs(urlsplit(src).query).get("person", [""])[0] for src, _ in shown]
    assert people == [ANA, XOAN], f"FAIL S35 A2 · cards for {people}, want {[ANA, XOAN]}"

    # Case 2 · each card → its own alt text, with that guest's name and quote and nothing of the other guest
    for (src, alt), (mine, theirs) in zip(shown, ((ANA, XOAN), (XOAN, ANA))):
        assert PERSON[mine] in alt and PERSON[theirs] not in alt, f"FAIL S35 A2 · alt text of {mine}: {alt!r}"
        assert HOST not in alt and "ustedes nunca" not in alt, f"FAIL S35 A2 · the host is in the alt text of {mine}"

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
    for (src, _), mine in zip(named, (ANA, XOAN)):
        image = images[src]
        assert SERIES in image, f"FAIL S35 A2 · the card of {mine} lacks the series line"
        assert PERSON[mine] in image, f"FAIL S35 A2 · the card at {src} is not {mine}'s"
    print("PASS S35 A2 · \"Exportar resumen\" gives one card per guest")
