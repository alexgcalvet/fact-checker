"""S35 A1 · The card counts what the judge keeps for one guest

Story: The person exports an invented interview where Ana Ruiz makes 26 checked claims; the judge keeps 4 false or
misleading flags and rules 2 puntualizaciones, none of them marked by the person; 2 of the 4 are serious; she
uses "Falso dilema" three times and dodges 2 of the 11 questions put to her. The card reads "4 de 26 datos, falsos o
engañosos", lists 2 serious among all her kept flags, "Falso dilema ×3" and "Esquivó 2 de 11 preguntas", and shows the two serious claims, each
with its correction and the name of its source.
Edge case: WHEN the person marks a flag unfair THEN it counts nowhere on the card, even if the judge kept it.
Edge case: WHEN the person marks a puntualización correct THEN the mark wins, as on the player: it counts under its found
verdict, such as false.

Setup: a temporary helper home with the S35 invented interview (s35_fakes.INTERVIEW) and its marks in the store: 4 false
or misleading flags of Ana Ruiz (2 serious, 1 moderate, 1 minor), 3 "Falso dilema", 1 "Ad hominem" and 2 dodged
questions, all kept by the judge and not marked; 2 puntualizaciones of the judge (a false and a misleading figure) with
no mark; a serious false figure, a "Falso dilema", a dodged question and a serious misleading figure, kept by the judge
and marked unfair; a host fallacy. The helper's HTTP server runs on a free local port with the screenshot faked to return the
card's HTML: `summary.png?person=` gives the card, `summary.txt?person=` its alt text. The second edge case marks the
false puntualización correct in another helper home.
"""
from urllib.parse import quote

from s35_fakes import GUEST, HOST_FLAG, INTERVIEW, MARKS, NITPICKS, SERIOUS_FALSE, SERIOUS_MISLEADING, UNFAIR, \
    REJECTED, VIDEO, flag, get, save_with_marks, start, visible


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
