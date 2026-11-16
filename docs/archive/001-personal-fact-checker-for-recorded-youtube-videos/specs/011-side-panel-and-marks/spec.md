# S11 Side panel and progress-bar marks

**Implements**: [RFC › Specs S11](../../RFC.md#specs), [ARCHITECTURE › Components](../../../../ARCHITECTURE.md#components)
**Approval**: agent · approved 2026-11-14

## Summary

The player shows only the flags that reach the bar of their type, and only for a few seconds, so the person cannot see what came before or what the tool held back. This slice adds a mark on a strip under the video for every flag, and a collapsed side panel that lists every flag, the ones under the bar too. A click on a mark or on a row of the panel jumps the video to that second and shows its card.

## Acceptance

- [X] A1 · Every flag has a mark at its second on a strip under the video
  - **Story:** On a page that mimics the YouTube player, a 100-second video has three flags at seconds 10, 50 and 90, one of them under the bar. The strip under the video shows three marks, at 10 %, 50 % and 90 % of its width, each with the color of its type.
  - **Test:** `tests/acceptance/s11-a1-progress-marks.test.ts`
- [X] A2 · The side panel lists every flag, under the bar too
  - **Story:** On the same page, the person sees a closed "Avisos (3)" tab at the side of the player and opens it. The panel lists the three flags in time order, each with its minute, its name and its quote; the one under the bar is shown greyed.
  - **Test:** `tests/acceptance/s11-a2-side-panel.test.ts`
- [X] A3 · A click on a mark or a row jumps to the flag
  - **Story:** On the same page, the person clicks the mark at 50 %. The video jumps to second 50 and the card of that flag shows, also if the flag is under the bar. A click on the row of the flag at second 90 jumps there the same way.
  - **Test:** `tests/acceptance/s11-a3-jump-to-flag.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/extension/src/panel.ts` | new — the strip of marks and the side panel |
| `src/extension/src/overlay.ts` | edit — show the card of a chosen flag, also under the bar |
| `src/extension/src/content.ts` | edit — mount the strip and the panel next to the overlay |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Draw a mark per flag on a strip under the video in `src/extension/src/panel.ts` and mount it in `content.ts` → A1
- [X] T002 List every flag in a collapsed side panel in `src/extension/src/panel.ts` → A2
- [X] T003 Jump to a flag and show its card on a click in `src/extension/src/panel.ts` and `overlay.ts` → A3

## Decisions

- **The marks sit on a strip of our own just above YouTube's progress bar, not inside it** (default) — YouTube's bar changes its markup often; our layer only needs the video's duration.
- **The panel starts closed, on the right of the player, and only exists inside our layer** (default) — the video stays clear unless the person asks.
- **A flag under the bar shows greyed in the panel and as a thinner mark** (default) — the person sees what the tool held back without confusing it with shown flags.

## Out of scope

- Filters by type in the panel: a later change.
- Marks on the YouTube progress bar itself.
