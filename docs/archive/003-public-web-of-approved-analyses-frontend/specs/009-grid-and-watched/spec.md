# S9 Grid view and what you watched

**Implements**: [RFC Specs S9](../../RFC.md) · [ARCHITECTURE Contracts: `/es/*`, `/en/*`, `GET /api/videos`; Components: Web app](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-22

## Summary

A reader can switch the video list to a grid of thumbnails, and each video says whether it is new to them, started or watched, with a bar under its thumbnail showing how far they got. This lets a returning reader pick up where they left off without an account: what they watched is kept in their own browser and never sent anywhere. The design is the approved canvas page "S4 · Elegir vídeo" (boards List and ListPhone, with the grid card of board "S4 · Arriba y cuadrícula v2").

## Acceptance

- [X] A1 · The list switches to a grid and keeps the choice
  - **Story:** A reader on `/es/videos` presses the grid button ("Cuadrícula") at the right of the toolbar. The videos show as cards of one height: thumbnail, a title of at most two lines in a block of fixed height (the full title on hover), one line "canal · fecha", and one line with the mix bar and the avisos per 10 minutes, also for a video with no avisos; every card in a row lines up. Filters and sort stay; the address gets `vista=cuadricula`. A reload keeps the grid, Back returns to the list, and "Lista" brings back the rows. Opening `/es/videos` with no `vista` on the same device later shows the view they last chose.
  - **Test:** `tests/web/list-grid.test.ts`
- [X] A2 · Each video says if it is new, started or watched
  - **Story:** A reader watches 4 minutes of a 40-minute video in the viewer and comes back to the list. That video reads "Empezado" with a bar under its thumbnail filled to a tenth, in the list and in the grid. A video they watched to the end reads "Visto" with a full bar. A video published 3 days ago that they never opened reads "Nuevo"; one published 10 days ago reads nothing. Ten seconds of a video leave it unmarked. Thumbnails sit dimmed at rest and light up under the pointer or focus; the duration and the bar stay undimmed. In another browser, nothing is marked.
  - **Test:** `tests/web/list-watched.test.ts`
- [X] A3 · The owner sees their progress in the grid
  - **Story:** After deploy, the owner switches to the grid on a laptop, starts a video, returns, and sees its progress there; on a phone, which has no grid (design), the rows show it.
  - **Test:** `review: the deployed list and grid on a laptop and a phone, against the boards List and ListPhone`

## Files

| Path | Change |
|------|--------|
| `src/web/src/watched.ts` | new — the progress of each video and the last view, in the browser's storage; the state word of a video |
| `src/web/src/Viewer.tsx` | edit — save the time reached while a video plays, and its end |
| `src/web/src/List.tsx`, `src/web/src/filters.ts` | edit — the Lista / Cuadrícula toggle and `vista` in the address, the grid cards, the state word and the watched bar on rows and cards, the dimmed thumbnails |
| `src/web/src/texts.ts`, `src/web/src/style.css` | edit — the texts in both languages and the styles, laptop and phone |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Keep each video's progress and the last view in the browser, and save the time reached from the viewer, in `src/web/src/watched.ts` and `src/web/src/Viewer.tsx` → A2
- [X] T002 Add the Lista / Cuadrícula toggle, `vista` in the address and the grid cards, in `src/web/src/List.tsx`, `src/web/src/filters.ts`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T003 Show the state word, the watched bar and the dimmed thumbnails on rows and cards, in `src/web/src/List.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A2
- [X] T004 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A3

## Requirements

- [X] FR-001 — The progress is stored only in the browser's local storage; no request carries it, and the page works when storage is blocked.

## Decisions

- **"Empezado" from 30 s and under 90 %; "Visto" from 90 % or the player's end** (design, new default) — the owner may still change them.
- **"Nuevo": published 7 days ago or less and never opened on this device** (design, approved).
- **The address `vista` wins over the remembered view** (default) — a shared link shows what its sender saw.
- **A phone has no grid; it shows rows with the state and the bar** (design, v2) — the remembered view applies on open only; Back follows the address.

## Out of scope

- Syncing progress across devices: it needs accounts, a non-goal of the RFC.
