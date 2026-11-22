# S2 Mark and comment from the viewer

**Implements**: [RFC Specs S2](../../RFC.md) · [ARCHITECTURE Contracts: `POST /marks`, `POST /api/feedback`](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

A viewer of the public web can now say whether a flag is right, unfair or needs nuance, from the flag itself, and the owner reads it on the review page. The viewer is asked once to agree that their marks are sent anonymously; nothing leaves the browser before that. This closes the loop the test page had: the owner learns where the flags are wrong.

## Acceptance

- [X] A1 · The viewer agrees once before anything is sent
  - **Story:** On `/es/v/debate01`, a viewer opens the flag at 20:10 and taps "Correcto". A question asks whether to send their marks anonymously, with a link to the privacy page. They answer "Sí": the mark is sent, and a later mark on another flag is sent with no question. Another viewer answers "No": nothing is sent, and they are not asked again on that browser.
  - **Test:** `tests/web/viewer-consent-once.test.ts`
- [X] A2 · A mark from the panel or the card reaches the review page
  - **Story:** After agreeing, a viewer taps "Injusto" on the card over the video for the flag at 20:10, writes "La cifra es del INE de 2024" and saves. The owner's review page lists a web mark "unfair" on that flag with that reason, and a flag comment naming the flag's rule. A mark "Correcto" from an open row of the panel shows there as "correct". The flag then shows the viewer's mark.
  - **Edge case:** WHEN the collector's daily stop refuses the mark THEN the viewer reads that marks are closed for today, and the flag keeps their mark.
  - **Test:** `tests/web/viewer-mark-reaches-review.test.ts`
- [X] A3 · "Matizar" sends a comment on the flag
  - **Story:** After agreeing, a viewer taps "Matizar" on the flag at 20:10, writes "Falta decir que es interanual" and sends it. The owner's review page lists a flag comment on that flag with that text and no rule, and no mark.
  - **Test:** `tests/web/viewer-nuance-comment.test.ts`
- [X] A4 · The owner sees a real mark and comment
  - **Story:** The owner opens a real approved debate on the deployed viewer on a phone, gives one mark and one "Matizar" comment, and sees both on `/admin`.
  - **Test:** `review: the deployed viewer and /admin after one mark and one comment`

## Files

| Path | Change |
|------|--------|
| `src/shared/feedback.ts` | new — the browser's anonymous id, the stored consent answer, and sending a web mark and a flag comment |
| `src/extension/src/try.ts` | edit — use the shared client instead of its own copy |
| `src/web/src/Feedback.tsx` | new — the three actions on a flag, the consent question and the reason or comment box |
| `src/web/src/Viewer.tsx` | edit — the actions on the card over the video and in an open row of the panel |
| `src/web/src/texts.ts` | edit — the Spanish and English texts |
| `src/web/src/style.css` | edit — the actions and the box, on the CALVET brand |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Move the anonymous id, the consent answer and the mark and comment sends into `src/shared/feedback.ts`, and import them in `src/extension/src/try.ts` → A1, A2
- [X] T002 Ask consent once and send nothing on "No", in `src/web/src/Feedback.tsx` → A1
- [X] T003 Add "Correcto", "Injusto" with a reason, and the daily-stop note on the card and the open row, in `src/web/src/Feedback.tsx`, `src/web/src/Viewer.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A2
- [X] T004 Add "Matizar" with its comment box in `src/web/src/Feedback.tsx` and `src/web/src/texts.ts` → A3
- [X] T005 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **The viewer and the test page share one id and one consent answer** (default) — same origin, so a viewer who agreed on `/try/` is not asked again; rejected: separate keys.
- **"Matizar" is a flag comment with no rule; "Injusto" sends a mark and a flag comment with the flag's rule, as the test page does** (default) — the existing contracts, no API change (docs/archive/003-public-web-of-approved-analyses-frontend/research/interview-public-web-frontend.md).
- **The actions sit on the card and in an open row only** (default) — a closed row stays one tap to seek; rejected: actions on every row.

## Out of scope

- A general comment on the method and quotes of the prompts: S6.
- Undoing or changing a sent mark: the collector replaces a mark sent again; no undo button.
