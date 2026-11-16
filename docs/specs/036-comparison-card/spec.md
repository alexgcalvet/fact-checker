# S36 Comparison card

**Implements**: [RFC › Specs](../../RFC.md#specs), [ARCHITECTURE › Components › Summary](../../ARCHITECTURE.md#components), [ARCHITECTURE › Decisions](../../ARCHITECTURE.md#decisions)
**Approval**: agent · approved 2026-11-16

## Summary

Today each analysed interview gives a card per guest, but nothing sets two or three people side by side. After this slice one command takes up to three analysed interviews and gives one card in the CALVET look, with a column per person: share of correct figures, serious flags per hour of speech, the device each one repeats most and the questions each one dodged. It counts what the judge keeps, exactly as the profile card does, so a person's numbers read the same on both cards.

## Acceptance

- [X] A1 · The comparison counts what the judge keeps, per hour of speech
  - **Story:** The person runs `fact-checker compare` with three analysed invented interviews: Marta Ibarra speaks 41 min with 26 checked figures, 17 correct and 3 serious flags; Jorge Salcedo and Núria Vidal likewise. The command prints the path of a PNG and of its alt text. The card reads "Comparativa · 3 entrevistas", "78 datos verificados" and, in Marta's column, "41 min hablando · 26 datos", "65 %" correct, "4,4" serious per hour with "3 graves", "Datos a conveniencia · 4 veces" and "Preguntas esquivadas 2 de 11". The alt text holds the same numbers within 1000 characters.
  - **Edge case:** WHEN a flag is marked unfair, or a host makes it THEN it counts in no column, as on the profile card.
  - **Edge case:** WHEN a person has no speaking time (the voices were not told apart) THEN "Graves por hora" shows "—" and the count "3 graves" stays.
  - **Test:** `test_s36_a1_compare_content.py`
- [X] A2 · The same person in two interviews is one column
  - **Story:** The person compares two interviews of Marta Ibarra, one named "Marta Ibarra (invitada)" by the voices and one "Marta Ibarra", and one of Jorge Salcedo. The card has two columns; Marta's adds both interviews: her speaking time, checked figures, serious flags and questions. The header says "3 entrevistas".
  - **Edge case:** WHEN the interviews hold more than three guests, or an id is not analysed THEN the command writes no card and names the guests, or the id, in one line.
  - **Test:** `test_s36_a2_same_person.py`
- [X] A3 · The comparison follows the CALVET layout with every text at 30 px or more
  - **Story:** The person runs the render check on the three invented interviews. It saves the card as a 1080×1350 PNG and fails if any text is under 30 px, a line leaves the page or the page asks the network for a font. The person opens the PNG beside the InterviewCompare board and sees the same header, three columns, legend and footer «Detectado con IA · no revisado por humanos».
  - **Test:** `check: bash tests/acceptance/s36-a3-compare-render.sh`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/summary.py` | edit — the comparison content from the profile card of each person, its alt text and its page |
| `src/helper/fact_checker/compare.html` | new — the InterviewCompare layout, with the fonts and wordmark of S35 |
| `src/helper/fact_checker/cli.py` | edit — `compare <id> <id> [<id>] [--series]`: loads each flag file with its marks, writes the PNG and the alt text |
| `tests/acceptance/` | new — the tests, their fakes and the render check |

## Tasks

- [X] T001 Build the comparison from `card()` of each guest, merged by canonical name, with its alt text in `summary.py` → A1, A2
- [X] T002 Add the `compare` command in `cli.py`: flag files with marks, at most three guests, PNG and alt text → A1, A2
- [X] T003 Lay out the comparison in `compare.html` and its page in `summary.py` → A3

## Decisions

- **The columns come from the profile card of each person** (default) — one rule for both cards; rejected: a second count.
- **Canonical name is the person's name without the role in brackets** (default) — the voices write "Marta Ibarra (invitada)"; the card already strips it.
- **Correct share is correct over checked figures; puntualizaciones are not correct** (default) — the verdict bar of the column shows all four.
- **The card and alt text go to the current folder as `compare.png` and `compare.txt`** (default) — a CLI output the person posts by hand.
- **The header line is `--series` or else the programmes and the month range** (default) — the board shows «La entrevista de las 9» · oct–nov 2026.
- **The footer says «Detectado con IA · no revisado por humanos», not the board's «100 % revisado»** (person, 2026-11-15) — the same rule as the profile card.

## Out of scope

- A comparison button in the extension, and the card's link: S37. A single score or ranking: never (ARCHITECTURE).
