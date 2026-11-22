# S8 Filter and search the list

**Implements**: [RFC Specs S8](../../RFC.md) · [ARCHITECTURE Contracts: `/es/*`, `/en/*`, `GET /api/videos`; Components: Web app](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-22

## Summary

A reader of the video list can narrow it to what they look for: the videos that also exist in English, one channel, one guest, or words of a title, channel or name; the list is never filtered by kind of aviso (owner, 2026-11-22). Every number on a choice says how many videos that choice would leave, so a dead end shows before it is picked, and the address keeps every choice, so a reload or a shared link shows the same list. The design is the approved canvas page "S4 · Elegir vídeo" (boards List, ListStates and ListPhone, with the top area of board "S4 · Arriba y cuadrícula v2").

## Acceptance

- [X] A1 · One toolbar narrows the list, counted and kept in the address
  - **Story:** A reader opens `/es/videos` with 12 approved videos. Under the heading "Vídeos 12" one toolbar holds the search field, the buttons "Canal", "Invitado" and "También en inglés", then "Orden" and the view toggle; there is no chip per kind of aviso, and an old link with `?tipo=retorica` shows all 12. They press "También en inglés": the list shows the 3 that exist in English, the lead goes, the button shows it is set with a × to clear it, "3 de 12 vídeos · Quitar filtros" appears under the toolbar, and the address becomes `/es/videos?idioma=en`. Reloading shows the same list; Back returns to all 12; "Quitar filtros" brings back every video and keeps the sort.
  - **Test:** `tests/web/list-toolbar.test.ts`
- [X] A2 · Channel, guest and words narrow the list, with a way out when nothing matches
  - **Story:** The reader opens the channel menu and picks one channel, then the guest menu, types "an" in its search field and picks "Ana Pérez"; each option shows how many videos it would leave with the other choices kept, and the address reads `?canal=…&invitado=ana-perez`. In the search pill they type "presupuesto" (or "PRESUPUESTO", or without accents), which matches titles, channels and guests' names, and the address gets `q=presupuesto`. When nothing matches, the page names what fails, offers "Quitar la búsqueda «presupuesto»" first, then one "Quitar «x» · N vídeos" button for each choice whose removal gives at least one video, then "Ver los 12 vídeos".
  - **Test:** `tests/web/list-menus-search.test.ts`
- [X] A3 · On a phone, a search field and the "Filtros" sheet
  - **Story:** On a phone, the list shows the heading, a full-width search field that filters as the reader types, then one row with "Orden" on the left and "Filtros" on the right, with a count badge when two filters are on. "Filtros" opens a sheet with the channels, a guest search and the language; its bone button reads "Ver 5 vídeos" and its number changes with each pick before the reader closes it; "Restablecer" clears them.
  - **Test:** `tests/web/list-phone-filters.test.ts`
- [X] A4 · The owner filters the real list
  - **Story:** After deploy, the owner filters by a guest and a channel on a laptop and a phone, reloads with the same list, and "Quitar filtros" brings back every video.
  - **Test:** `review: the deployed list on a laptop and a phone, against the boards List, ListStates, ListPhone and "S4 · Arriba y cuadrícula v2"`

## Files

| Path | Change |
|------|--------|
| `src/web/src/filters.ts` | new — the filters read from and written to the address, the match of each video, the count of each option with the other filters kept |
| `src/web/src/List.tsx` | edit — the chip row, the menus, the search pill, the filtered status, the no-results state, the phone field, row and sheet; the sort keeps the filters in the address |
| `src/web/src/texts.ts`, `src/web/src/style.css` | edit — the texts in both languages and the styles, laptop and phone |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Read and write the filters in the address, match a video and count each option with the others kept, in `src/web/src/filters.ts` → A1, A2
- [X] T002 Draw the heading and the toolbar with "También en inglés", the set state of a filter and the filtered status, with no kind chips, and keep the filters when the sort changes, in `src/web/src/List.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T003 Add the channel and guest menus, the search pill with its `/` key and the no-results state, in `src/web/src/List.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A2
- [X] T004 Add the phone search field, the "Orden" and "Filtros" row and the "Filtros" sheet, in `src/web/src/List.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A3
- [X] T005 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **No API change: the browser filters the list it already loads** (default) — `GET /api/videos` serves the channel, the guests and the languages.
- **No filter by kind of aviso** (owner, 2026-11-22) — the sort orders already rank by Falso and the other kinds; `tipo` leaves the address.
- **A guest in the address is the slug of their name, as on the profile** (default) — "Ana Pérez" → `ana-perez`.
- **The language chip names the page's other language** (default) — «También en inglés» (`idioma=en`) on `/es/videos`, "Also in Spanish" (`idioma=es`) on `/en/videos`; the address keys are the same in both languages, as `orden` is; the board shows only the Spanish page.
- **The search is a flat field in the toolbar, never glass** (design, v2) — glass is reserved for the nav pill; on a phone it sits under the heading, on the list only.

## Out of scope

- The List / Cuadrícula toggle and `vista` in the address: S9.
- A search on other pages than the list.
