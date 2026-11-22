# S4 Pick a video

**Implements**: [RFC Specs S4](../../RFC.md) · [ARCHITECTURE Contracts: `GET /api/videos`, `GET /`, `/es/*`, `/en/*`; Components: Web app, Verdict kinds](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

The public web gets its front page: every approved video, newest first, with how many avisos each has and how disputed it is for its length, so a reader picks what to watch. They can sort the list, for example the most disputed first, and the sort stays in the link. A video analysed only in Spanish tells an English reader so on the viewer. The design is the approved canvas page `s4-elegir`.

## Acceptance

- [X] A1 · The list shows every approved video with its avisos and how disputed it is
  - **Story:** The owner opens `/es/`. The newest video, debate01, leads at the top with "Lo último"; under it every approved video is a row, newest first, each linking to `/es/v/<id>`. A row shows its title, channel, type, date, duration, languages ("ES · EN" or "ES"), its avisos with their count per verdict, the avisos per 10 minutes such as "4,9/10′" with its level ("muy discutido" from 6,0, "discutido" from 4,0, else "poco discutido"), and a mix bar. A video's avisos count every flag but context notes and hidden flags, puntualizaciones included.
  - **Edge case:** WHEN no video is approved THEN the page reads "Todavía no hay vídeos analizados" with a link to "Cómo funciona", and no sort.
  - **Test:** `tests/web/list-avisos.test.ts`
- [X] A2 · The reader sorts the list and the link keeps it
  - **Story:** On `/es/` the owner opens the sort word of the sentence "3 vídeos · más recientes primero" and picks "Más discutidos primero": the rows reorder by avisos per 10 minutes, each with its rank, the lead goes, and the address becomes `/es/?orden=densidad`. A reload keeps that order; a click on the column head "Duración" sorts the longest first and the sentence says "los más largos primero"; the browser's back button returns to the previous order.
  - **Test:** `tests/web/list-sort.test.ts`
- [X] A3 · An English reader learns the analysis is only in Spanish
  - **Story:** A reader opens `/en/v/intervw1`, analysed only in Spanish. Between the header and the video a note reads "This analysis is only in Spanish for now. Quotes and explanations are shown in Spanish." with a link "Abrir en español" to `/es/v/intervw1`. Its × hides it for the rest of the session. `/en/v/debate01`, analysed in English, shows no note.
  - **Test:** `tests/web/viewer-language-note.test.ts`
- [X] A4 · The owner picks a real video on a laptop and a phone
  - **Story:** After deploy, the owner opens `/es/` on a laptop and a phone, sees the real videos with their avisos per 10 minutes and mix bars as on the canvas, sorts by "Más discutidos primero", opens one, and sees the outline Puntualización mark in the list and in the viewer.
  - **Test:** `review: the deployed list on a laptop and a phone, against the canvas page s4-elegir`

## Files

| Path | Change |
|------|--------|
| `src/shared/kinds.ts` | new — the verdict kind of a flag, moved from `src/web/src/marks.ts` |
| `src/web/src/marks.ts`, `src/web/src/Viewer.tsx`, `src/web/src/Feedback.tsx`, `src/web/src/texts.ts` | edit — import the kinds; the outline Puntualización mark; the language note; the list's texts |
| `src/collector/src/index.ts`, `src/collector/README.md` | edit — `counts` per video in `GET /api/videos` |
| `src/web/src/main.tsx` | edit — route `/<lang>/` to the list |
| `src/web/src/List.tsx` | new — the lead, the rows and their ledger, density meter and mix bar, the sort sentence and heads, loading and empty |
| `src/web/src/style.css` | edit — the list on laptop and phone, from the canvas |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Move the verdict kind into `src/shared/kinds.ts` and add `counts` to `GET /api/videos`, in `src/collector/src/index.ts`, `src/collector/README.md` and `src/web/src/marks.ts` → A1
- [X] T002 Build the list (lead, rows, ledger, density and level meter, mix bar, loading, empty) and route `/<lang>/` to it, in `src/web/src/List.tsx`, `src/web/src/main.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T003 Add the seven sort orders to the sentence menu and the column heads, kept in `?orden=` and the browser history, in `src/web/src/List.tsx` → A2
- [X] T004 Show the language note on the viewer when the served language is not the asked one, in `src/web/src/Viewer.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A3
- [X] T005 Draw Puntualización as the outline mark in the viewer and the list, build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **Counts come from the API, density from the client** (default) — `counts` is the only new field; density is avisos ÷ (duration ÷ 600), so no second field can disagree with it.
- **Density levels are absolute: below 4,0, up to 5,9, from 6,0** (owner, after real data: 2,5 and 4,0 put 6 of 7 videos high) — a video keeps its colour as the list grows.
- **The lead's lane reads the newest video's flags from the existing flags route** (default) — no lane field in the list API.
- **Sort orders: recientes (default), densidad, antiguos, avisos, graves (Falso and Engañoso), falso, largos; ties go to the newest** (canvas).

## Out of scope

- Type chips, language, channel and guest filters, the search and the phone's filter sheet: S8.
- The grid view, Nuevo, Visto, Empezado, the watched bar and dimmed thumbnails: S9.
