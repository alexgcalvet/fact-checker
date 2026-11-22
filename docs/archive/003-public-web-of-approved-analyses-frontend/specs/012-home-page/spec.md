# S12 The home page

**Implements**: [RFC Specs S12](../../RFC.md) · [ARCHITECTURE Contracts: `GET /`, `/es/*`, `/en/*`, `GET /api/videos`, `GET /api/videos/<id>/flags`; Components: Web app](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

The site gets a front page: a first-time visitor reads in one sentence what this is and sees it working on the newest analysis, a few checked claims, the most disputed videos and the four steps of the method. The video list moves to its own address, and the wordmark leads home from every page. The design is the approved canvas page `portada` (laptop and phone), inside the shared reading-page frame.

## Acceptance

- [X] A1 · The home page shows what this is and the newest analysis
  - **Story:** A reader opens `/es/`. They see "Debates políticos, revisados frase a frase.", the line "Una IA señala lo dudoso. Tú puedes corregirlo." and the figures "2 vídeos · 2 h · 3 invitados" from the approved videos (1 h 30 min rounds to whole hours). Under them, "Lo último" shows the newest video (debate01): its title, "canal · fecha", its marks with counts, its lane, and "Ver con avisos" leading to `/es/v/debate01`; then the line with the V. No item of the header's pill bar is lit, and the page never names a severity or ranks anyone.
  - **Test:** `tests/web/home-hero.test.ts`
- [X] A2 · Checked claims, the most disputed videos and the method
  - **Story:** Under the line, "Datos revisados" shows at most 3 cards of Falso or Engañoso claims of 60 % confidence or more, from the 5 newest videos, highest confidence first, one per speaker; each card shows its mark, the quote, the speaker and the time, and opens the viewer at that second. "Los más discutidos" shows up to 4 videos by avisos per 10 minutes, each linking to its viewer, with "Ver los 2 vídeos" to the list. "Cómo se hace" shows Escucha → Señala → Aprueba → Corriges; hovering or focusing a box explains the step, and on a phone a tap shows it under the grid. A section with no data is not shown.
  - **Test:** `tests/web/home-sections.test.ts`
- [X] A3 · The list moves to its own address and the wordmark leads home
  - **Story:** The list now opens at `/es/videos` (and `/en/videos`), with "Vídeos" lit in the pill bar; an old link `/es/?orden=densidad` lands on `/es/videos?orden=densidad`. On every page, the viewer included, the CALVET wordmark links to `/es/` (or `/en/`); on the home page it is marked as the current page.
  - **Test:** `tests/web/home-routes.test.ts`
- [X] A4 · The owner reads the home page
  - **Story:** After deploy, the owner opens `/es/` on a laptop and a phone, checks it against the canvas, opens a checked claim and reaches the list from "Ver todos los vídeos".
  - **Test:** `review: the deployed home page on a laptop and a phone, against the canvas page portada`

## Files

| Path | Change |
|------|--------|
| `src/web/src/Home.tsx` | new — hero, figures, "Lo último", "Datos revisados", "Los más discutidos", "Cómo se hace", loading |
| `src/web/src/main.tsx` | edit — `/<lang>/` to the home page, `/<lang>/videos` to the list, old list links redirected |
| `src/web/src/List.tsx`, `src/web/src/Footer.tsx`, `src/web/src/Viewer.tsx` | edit — list links and sort URLs under `/videos`; the wordmark as a link home; "Vídeos" to `/videos` |
| `src/web/src/texts.ts`, `src/web/src/style.css` | edit — the home page's texts in both languages and its styles under `.home` |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Route `/<lang>/` to the home page and `/<lang>/videos` to the list, redirect old list links, and link the wordmark home on every page, in `src/web/src/main.tsx`, `src/web/src/List.tsx`, `src/web/src/Footer.tsx`, `src/web/src/Viewer.tsx` → A3
- [X] T002 Build the hero, figures and "Lo último" with the line, in `src/web/src/Home.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T003 Build "Datos revisados", "Los más discutidos" and "Cómo se hace" with their tooltips, laptop and phone, in `src/web/src/Home.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A2
- [X] T004 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **The button reads "Ver con avisos", as on the list** (default) — the owner renamed it there; the board's "Ver el análisis" predates that.
- **A section with no data is hidden, and the page with no approved video shows the list's empty state** (default) — the empty states are not designed yet.
- **The list keeps its own "Lo último" lead** (owner open question, RFC Open questions) — until he answers.

## Out of scope

- The search in the phone header: S8.
- The English copy beyond a translation of the Spanish one, and the error pages: the design session's second pass.
