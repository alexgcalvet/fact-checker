# S35 Profile card

**Implements**: [RFC › Specs](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts), [ARCHITECTURE › Components › Summary](../../../../ARCHITECTURE.md#components)
**Approval**: agent · approved 2026-11-15

## Summary

Today "Exportar resumen" gives one image that sets every speaker side by side, with no sense of how much a guest got right or how serious each slip was. After this slice it gives one card per guest in the author's CALVET look: how many of the guest's checked figures were false or misleading, how serious they were, the rhetorical devices the guest repeats, the questions the guest dodged and the two most serious claims with their correction and source. A shared analysis gives the same card, because it now carries the counts behind those numbers.

## Acceptance

- [X] A1 · The card counts what the judge keeps for one guest
  - **Story:** The person exports an invented interview where Ana Ruiz makes 26 checked claims; the judge keeps 4 false or misleading flags and rules 2 puntualizaciones, none marked by the person; 2 of the 4 are serious; she uses "Falso dilema" three times and dodges 2 of the 11 questions put to her. The card reads "4 de 26 datos, falsos o engañosos", lists 2 serious among all her kept flags, "Falso dilema ×3" and "Esquivó 2 de 11 preguntas", and shows the two serious claims, each with its correction and the name of its source.
  - **Edge case:** WHEN the person marks a flag unfair THEN it counts nowhere on the card, even if the judge kept it.
  - **Edge case:** WHEN the person marks a puntualización correct THEN the mark wins, as on the player: it counts under its found verdict, such as false.
  - **Test:** `test_s35_a1_card_content.py`
- [X] A2 · "Exportar resumen" gives one card per guest
  - **Story:** The person clicks "Exportar resumen" on a debate with a host and two guests. The page that opens shows two cards, one per guest and none for the host, each with its own alt text to copy. The person types "1/3 · Candidatos a la Xunta" in the series field and both cards show that line.
  - **Test:** `test_s35_a2_card_per_guest.py`
- [X] A3 · The card follows the CALVET layout with every text at 30 px or more
  - **Story:** The person runs the render check on the invented interview. It saves the card as a PNG and fails if any text is under 30 px or the page asks the network for a font. The person opens the PNG beside the InterviewCard board of the brand canvas and sees the same plate, Fault, logo and order of blocks.
  - **Test:** `check: bash tests/acceptance/s35-a3-card-render.sh`
- [X] A4 · A shared analysis gives the same card
  - **Story:** The person analyses the invented interview with sharing on and marks nothing. A second person opens the same video, gets the shared analysis and exports it, marking nothing either. Both cards count what the judge keeps and read the same "6 de 26" and "Esquivó 3 de 11".
  - **Test:** `test_s35_a4_shared_card.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/pipeline.py` | edit — a part result also counts the questions put to each speaker, answered ones included |
| `src/helper/fact_checker/server.py` | edit — `claims` and `questions` per speaker in the flag file; `summary.png` and `summary.txt` take `person` and `series`; the summary page shows a card per guest |
| `src/helper/fact_checker/core/summary.py` | edit — the card of one guest and its alt text |
| `src/helper/fact_checker/summary.html` | edit — the InterviewCard layout of the brand canvas, all text ≥ 30 px |
| `src/helper/fact_checker/fonts/` | new — Newsreader, Host Grotesk, JetBrains Mono (OFL) and the CALVET wordmark SVG |
| `src/helper/fact_checker/analyses.py` | edit — `claims` and `questions` in a shared analysis |
| `tests/acceptance/` | new — the tests and the check |

## Tasks

- [X] T001 [P] Count the questions put to each speaker in `pipeline.py`; write `claims` and `questions` per speaker in `server.py` → A1
- [X] T002 Build the card of one guest and its alt text in `summary.py` → A1
- [X] T003 Add `person` and `series` to the summary routes and one card per guest on the summary page in `server.py` → A2
- [X] T004 Lay out the card in `summary.html` with the fonts and wordmark in `fonts/` → A3
- [X] T005 [P] Add `claims` and `questions` to the shared fields in `analyses.py` → A4

## Requirements

- [X] FR-001 — The alt text of a card MUST stay within 1000 characters.

## Decisions

- **Questions asked are a count per speaker in the flag file** (default) — "de 11" needs the answered questions, which make no flag; rejected: logging them as claims.
- **False or misleading means the labels `false`, `misleading`, `definition_swap` and `plan_as_fact`** (default) — the amber and red families of the player; `disputed` is context.
- **The verdict bar runs Falso, Engañoso, Puntualización, Correcto** (default) — the panel asked for false first; correct is checked claims minus the rest.
- **Devices are fallacy and contradiction labels only** (default) — a misleading figure already counts in the hook; no double counting.
- **The card counts what the judge keeps, with no review** (person, 2026-11-15) — the footer says «no revisado por humanos»; rejected: only flags marked correct.
- **Severity counts every kept flag but questions; the two most serious rank by severity, then false, misleading, rhetoric** (person, 2026-11-15) — an insinuation can be serious too.
- **The interview line names the programme, not the whole YouTube title; half answers show apart from dodged ones** (person, 2026-11-15).
- **The mark wins, as on the player** (person, 2026-11-15) — a flag marked correct counts under its found verdict even when the judge ruled it a nitpick; a puntualización is a judge nitpick the person did not mark; so the card matches the side panel.

## Out of scope

- The card's link and the page behind it: S37. Comparison and rates per hour: S36. A weakest topic: not built (RFC).
