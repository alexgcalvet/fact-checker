"""S36 A2 · The same person in two interviews is one column

Story: The person compares two interviews of Marta Ibarra, one named "Marta Ibarra (invitada)" by the voices and one
"Marta Ibarra", and one of Jorge Salcedo. The card has two columns; Marta's adds both interviews: her speaking time,
checked figures, serious flags and questions. The header says "3 entrevistas".
Edge case: WHEN the interviews hold more than three guests, or an id is not analysed THEN the command writes no card
and names the guests, or the id, in one line.

Setup: a temporary helper home with the S36 invented interviews of Marta Ibarra (s36_fakes.MARTA: voice "Marta Ibarra
(invitada)", 41 min, 26 figures with 2 false, 4 misleading and 3 puntualizaciones, 3 serious, 2 of 11 questions dodged)
and Jorge Salcedo (s36_fakes.JORGE), and a second invented interview of Marta whose voice is "Marta Ibarra", with no
person name: 20 min, 10 figures with 1 false, 1 misleading and 1 puntualización, 1 serious, 1 of 5 questions dodged.
A debate of three invented guests feeds the edge case. `fact-checker compare` runs in process in a temporary folder,
with the thumbnail download off and the screenshot faked to return the card's HTML (s36_fakes.compare).
"""
from s36_fakes import JORGE, MARTA, column, compare, interview, save, visible

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


DEBATE = interview("debate36", "Ana Ruiz (invitada)", "Ana Ruiz", spoken_s=1500, claims=8, asked=4, false=1,
                   misleading=0, nitpicks=0, serious=1, device="false_dilemma", repeats=1, dodged=0)
DEBATE[0]["people"] |= {"Xoán Pereira (invitado)": {"role": "guest", "person": "Xoán Pereira", "spoken_s": 1400},
                        "Lucía Prado (invitada)": {"role": "guest", "person": "Lucía Prado", "spoken_s": 1300}}


def test_too_many_or_unknown(tmp_path, monkeypatch, capsys):
    home, out = tmp_path / "home", tmp_path / "out"
    out.mkdir()
    save(home, DEBATE, MARTA)

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
