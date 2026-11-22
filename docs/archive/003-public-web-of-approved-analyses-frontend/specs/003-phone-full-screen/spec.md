# S3 Full screen on a phone

**Implements**: [RFC Specs S3](../../RFC.md) · [ARCHITECTURE Decisions: the viewer's own bar and full screen](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

A viewer on a phone can turn it sideways and watch the video across the whole screen, with the flag being said on a small card over the video and the list of flags one tap away, as on a laptop in full screen. Today a phone held sideways gets the laptop page squeezed into a short screen, and the full screen button on a phone hides the flags. This follows the approved landscape board of the viewer canvas.

## Acceptance

- [X] A1 · Turning a phone sideways fills the screen with the video
  - **Story:** A viewer watches `/es/v/debate01` on a phone held upright and turns it sideways. The video fills the screen with the bar over it; the header, the title and the panel are gone. At second 1215 the card of the flag said at 20:10 shows top right over the video. They turn the phone upright again: the page shows the video, the "Ahora" strip and the panel, and the video keeps playing from the same second.
  - **Test:** `tests/web/viewer-sideways-fills.test.ts`
- [X] A2 · The flags open as a side sheet over the video
  - **Story:** With the phone sideways, the viewer taps "Avisos" on the bar. A sheet slides over the right of the video with every flag, the one at 20:10 marked as now; the card over the video hides while the sheet is open. A tap on a flag's time jumps the video there; "Cerrar" closes the sheet and the card comes back.
  - **Test:** `tests/web/viewer-side-sheet.test.ts`
- [X] A3 · The full screen button turns the phone sideways
  - **Story:** With the phone upright, the viewer taps the full screen button. The browser goes full screen and turns the video sideways, and the flag being said shows on its card, not in the strip. A tap on "Salir de pantalla completa" lets the phone turn back.
  - **Edge case:** WHEN the browser refuses full screen or turning (an iPhone) THEN the page still fills the screen with the video, its bar and its card.
  - **Test:** `tests/web/viewer-full-button.test.ts`
- [X] A4 · The owner watches a real debate sideways
  - **Story:** After deploy, the owner opens a real approved debate on a phone, turns it sideways and uses the full screen button: cards show, the side sheet opens, a tap seeks, and upright the phone layout comes back.
  - **Test:** `review: the deployed viewer on a phone, sideways and with the full screen button`

## Files

| Path | Change |
|------|--------|
| `src/web/src/Viewer.tsx` | edit — a phone held sideways uses the full screen layout; the card shows in full screen on a phone; the button asks the browser to turn sideways and lets go on exit |
| `src/web/src/style.css` | edit — the sideways layout from the canvas board: card 300 px top right, bar low, side sheet 360 px |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Treat a phone held sideways as full screen (no header, title or panel), and keep the second across the turn, in `src/web/src/Viewer.tsx` and `src/web/src/style.css` → A1
- [X] T002 Show the card, not the strip, in full screen on a phone, and size the side sheet and the card from the canvas board, in `src/web/src/Viewer.tsx` and `src/web/src/style.css` → A1, A2
- [X] T003 Ask the browser to turn sideways after it goes full screen, let go on exit, and fill the page when it refuses, in `src/web/src/Viewer.tsx` → A3
- [X] T004 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **A phone held sideways is a coarse pointer with a screen at most 500 px high in landscape** (default) — a short laptop window keeps its page; rejected: width alone.
- **Turning sideways fills the page, not the browser's full screen** (default) — the browser allows full screen only from a tap, so the turn fills the window and the button adds the browser's full screen; rejected: full screen only from the button.
- **The same player across the turn** (default) — the layout changes around the embed, so the video never reloads; rejected: a second player for landscape.

## Out of scope

- Full screen on a tablet: it keeps the laptop layout.
- The video list and the note for the other language: S4.
