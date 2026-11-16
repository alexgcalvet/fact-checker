# S14 Shareable summary image

**Implements**: [ARCHITECTURE › External systems › Headless Chrome](../../../../ARCHITECTURE.md#external-systems), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-14

## Summary

The person wants to share what an interview held in one post on X, with each speaker apart and only useful information. This slice exports one 1080×1350 PNG per video from the side panel: a header, a timeline with one row per speaker, and one column per speaker with counts by type and their most serious reviewed flags, each with its minute and correction. Only the flags the person marked correct go in, and the footer says these are signals, not verdicts.

## Acceptance

- [X] A1 · The summary keeps each speaker's most serious reviewed flags
  - **Story:** A flag file with two speakers holds, for the guest, a false figure, a dodged question, a contradiction, a disputed figure and a fallacy marked correct, plus a false figure marked unfair; the host has one fallacy marked correct. The summary has two columns: the guest's lists the false figure, the contradiction and the dodged question, in that order, with counts of every reviewed type; the host's lists the fallacy. The unfair flag appears nowhere.
  - **Edge case:** WHEN the video has five speakers THEN the four who speak most get a box with up to two flags each, and the footer says "y 1 más".
  - **Test:** retired: replaced by S35 A1
- [X] A2 · The summary is one 1080×1350 PNG that holds everything
  - **Story:** The person exports the summary of an invented interview whose flags have long quotes. They get one PNG of 1080×1350 with the title, the timeline, both columns and the footer; no text runs outside the image and no text is smaller than 26 px.
  - **Test:** retired: replaced by S35 A3
- [X] A3 · The person exports the summary from the side panel
  - **Story:** On a page that mimics the YouTube player, the person opens the side panel and clicks "Exportar resumen". The extension asks the helper for the summary of that video and opens the PNG in a new tab, with the alt text ready to copy under it.
  - **Test:** `tests/acceptance/s14-a3-export-button.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/summary.py` | new — pick each speaker's flags, counts and order; the alt text |
| `src/helper/fact_checker/summary.html` | new — the page template of the image |
| `src/helper/fact_checker/adapters/screenshot.py` | new — headless Chrome: page in, PNG out |
| `src/helper/fact_checker/adapters/youtube.py` | edit — also keep the title, the channel and the duration |
| `src/helper/fact_checker/server.py` | edit — `GET /videos/<id>/summary.png` and `summary.txt` (alt text) |
| `src/extension/src/panel.ts`, `src/extension/src/sw.ts` | edit — the export button; open the image |
| `docs/ARCHITECTURE.md` | edit — the new requests and the `title`, `channel`, `duration` fields |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Pick the flags, counts and alt text per speaker in `src/helper/fact_checker/core/summary.py`; keep title, channel and duration in `adapters/youtube.py` → A1
- [X] T002 Lay out the page and turn it into a PNG in `src/helper/fact_checker/summary.html` and `adapters/screenshot.py`; serve it in `server.py` → A2
- [X] T003 Add the export button in `src/extension/src/panel.ts` and `sw.ts`; update `docs/ARCHITECTURE.md` → A3

## Decisions

- **Only flags marked correct go in** (person) — what is published has been reviewed; the footer says "revisado".
- **One PNG of 1080×1350 per video, rendered from an HTML page by headless Chrome** (person, default) — X shows images, not pages; HTML keeps the layout easy to change.
- **Seriousness order: false, contradiction or promise, dodged question, misleading / metric swap / plan as fact, disputed, fallacy; then confidence** (default) — the most useful first.
- **Two speakers: up to 3 flags each; three or four: up to 2 each; more: the four who speak most** (default) — it always fits.
- **No total score or ranking between speakers; context flags never go in** (default) — counts by type only.

## Out of scope

- The full HTML report with every flag and its sources: a later slice.
- Posting to X from the tool.
