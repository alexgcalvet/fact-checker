"""S36 A1 · The comparison counts what the judge keeps, per hour of speech

Story: The person runs `fact-checker compare` with three analysed invented interviews: Marta Ibarra speaks 41 min with
26 checked figures, 17 correct and 3 serious flags; Jorge Salcedo and Núria Vidal likewise. The command prints the path
of a PNG and of its alt text. The card reads "Comparativa · 3 entrevistas", "78 datos verificados" and, in Marta's
column, "41 min hablando · 26 datos", "65 %" correct, "4,4" serious per hour with "3 graves", "Datos a conveniencia ·
4 veces" and "Preguntas esquivadas 2 de 11". The alt text holds the same numbers within 1000 characters.
Edge case: WHEN a flag is marked unfair, or a host makes it THEN it counts in no column, as on the profile card.
Edge case: WHEN a person has no speaking time (the voices were not told apart) THEN "Graves por hora" shows "—" and
the count "3 graves" stays.

Setup: a temporary helper home with the three S36 invented interviews (s36_fakes.MARTA, JORGE, NURIA) and their marks
in the store. Each holds the guest's kept flags with no mark, one serious flag of the guest's most repeated device
marked unfair, and one serious flag of the host. `fact-checker compare marta36 jorge36 nuria36` runs in process in a
temporary folder, with the thumbnail download off and the screenshot faked to return the card's HTML, so compare.png
holds that HTML. The edge case on speaking time runs Núria's interview again without `people` (no voices told apart),
with 3 serious figures.
"""
from s36_fakes import HOST_QUOTE, JORGE, MARTA, NURIA, UNFAIR_QUOTE, column, compare, interview, save, visible

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
