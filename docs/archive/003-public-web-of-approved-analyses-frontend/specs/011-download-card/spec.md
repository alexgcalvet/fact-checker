# S11 Download a guest's card

**Implements**: [RFC Specs S11](../../RFC.md) · [ARCHITECTURE Contracts: `/es/*`, `/en/*`, `GET /api/videos`, `GET /api/videos/<id>?lang=`, `/admin/*`; Components: Web app, Collector, Review page](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-22

## Summary

A reader of a guest's profile can take the guest's figures with them: a square or vertical image to post, or a printed sheet with every aviso and its reason. Every card carries the line that says the analysis is automatic and that marks are signals, not verdicts, and the reader cannot remove it, so a card never travels without that warning. The design is the approved canvas page "S5 · Perfil y comparación" (board S5Export).

## Acceptance

- [X] A1 · The reader downloads a square or vertical card as an image
  - **Story:** On Ana Pérez's profile, a reader presses "Descargar ficha". A sheet opens (from the right on a laptop, from the bottom on a phone) with the formats "Cuadrada 1:1", "Vertical 4:5" and "Para imprimir", and ES · EN. They pick 4:5 and see the owner's InterviewCard: the video's thumbnail on the plate, cut by the Fault, with the CALVET wordmark (in a debate, her half of the thumbnail, the first guest's half mirrored); "DEBATE · 10 NOV 2026"; her name; «the title» · how long she spoke of the video; the big "3 de 10" with "datos, falsos o engañosos"; the verdict bar with "2 falsos · 1 engañoso · 1 puntualiz. · 6 correctos"; "Peso: 2 altos · 1 medio · 2 bajos"; "Retórica y falacias" with each device ×n; "Esquivó 0 de 4 preguntas"; and under "Destacados" her two gravest avisos, each with its quote, minute, a verdict such as "Falso, peso alto.", its reason and, for a figure, its source. If the thumbnail cannot load, the plate is the night band. "Descargar PNG" saves a 1080 × 1350 image named after her and the video. Picking 1:1 gives a 1080 × 1080 image with no quote. Picking EN gives the same card in English. Every card ends with "Análisis automático con IA · 19 nov 2026 · Las marcas son señales, no veredictos." and no control removes it.
  - **Test:** `tests/web/card-image.test.ts`
- [X] A2 · The reader prints the full sheet and copies the alt text
  - **Story:** In the same sheet the reader picks "Para imprimir", then A4 or Letter. The preview shows the paper sheet: the wordmark, her name, six figures, who speaks when, the mix bar, every aviso with its reason (her two gravest marked "destacados"), a QR code to her profile and the disclosure line. "Imprimir o PDF" opens the browser's print dialog with only that sheet on the page. For each format, "Texto alternativo" shows a description of the card written from the same figures, under 1000 characters, with "Copiar". "Compartir…" opens the device's share menu with the image and the profile link where the device has one.
  - **Test:** `tests/web/card-print-alt.test.ts`
- [X] A3 · The owner downloads a real guest's card
  - **Story:** After deploy, the owner downloads a guest's 4:5 card and prints the A4 sheet on a laptop and a phone, against the board S5Export.
  - **Test:** `review: the downloaded 4:5 PNG and the A4 print preview of a real guest, against the board S5Export`
- [X] A4 · The owner swaps a debate's halves
  - **Story:** In a real debate the thumbnail shows the second guest on the left, so each guest's card shows the other's face. In /admin, on an approved debate of two guests, the owner flips the "Caras: intercambiar izquierda/derecha" switch. After that, each guest's card face in the viewer, 4:5 plate and profile cover use the other half: Ana, the first guest, gets the right half and Luis the left one. Flipping it back restores the speaker order. An interview, and a debate whose switch is never touched, keep the speaker order.
  - **Test:** `tests/collector/faces-swap.test.ts` (the route and the `swap` field) and `tests/web/faces-swap.test.ts` (the face, the plate and the cover)

## Files

| Path | Change |
|------|--------|
| `src/web/src/Card.tsx` | new — the sheet, the 1:1, 4:5 and paper cards, the alt text, the PNG export and print |
| `src/web/src/Profile.tsx` | edit — "Descargar ficha" opens the sheet; the cover shows the guest's image (her half in a debate), plan C when it cannot load |
| `src/web/src/faces.ts` | new — a guest's half of the thumbnail from `guests` and `swap`, and the thumbnail's maxres-then-hq fallback |
| `src/web/src/Viewer.tsx` | edit — `swap` in `Meta`; the guest cards' face from `faces.ts` |
| `src/collector/schema.sql`, `src/collector/src/index.ts` | edit — the `faces` table, `POST /admin/videos/<id>/faces/swap\|keep`, `swap` in `GET /api/videos`, `GET /api/videos/<id>` and `/admin/approved` |
| `src/collector/web/admin/index.html` | edit — the switch "Caras: intercambiar izquierda/derecha" on an approved debate of two guests |
| `src/collector/README.md`, `docs/ARCHITECTURE.md` | edit — the new route and field |
| `src/web/src/texts.ts`, `src/web/src/style.css` | edit — the texts in both languages, the cards' styles and the print stylesheet |
| `src/web/package.json` | edit — a library that draws a page element into a PNG, and one that draws a QR code |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Draw the 1:1 card from the profile's figures and the 4:5 InterviewCard ported from the helper, with the locked disclosure, and export them as PNG, in `src/web/src/Card.tsx`, `src/web/package.json`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T002 Open the sheet from the profile with its formats, languages and actions, in `src/web/src/Card.tsx`, `src/web/src/Profile.tsx`, `src/web/src/style.css` → A1
- [X] T003 Draw the A4 and Letter sheet with its QR code and print stylesheet, and write the alt text with "Copiar" and "Compartir…", in `src/web/src/Card.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A2
- [X] T004 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A3
- [X] T005 Keep the owner's swap per video in a `faces` table, served as `swap` by `GET /api/videos`, `GET /api/videos/<id>` and `/admin/approved`, set by `POST /admin/videos/<id>/faces/swap|keep` behind Access, with the switch on the review page, in `src/collector/schema.sql`, `src/collector/src/index.ts`, `src/collector/web/admin/index.html`, `src/collector/README.md`, `docs/ARCHITECTURE.md` → A4
- [X] T006 Decide a guest's half in one helper from `guests` and `swap`, used by the viewer's face, the 4:5 plate and the profile's cover, in `src/web/src/faces.ts`, `src/web/src/Viewer.tsx`, `src/web/src/Card.tsx`, `src/web/src/Profile.tsx` → A4
- [X] T007 Show the guest's image on the profile's cover (her half mirrored as on the plate in a debate, the whole thumbnail in an interview, dimmed, with the plate's fades), plan C when it cannot load, in `src/web/src/Profile.tsx`, `src/web/src/style.css` → A4
- [X] T008 Apply `schema.sql` to the remote database, build, and deploy → A4

## Decisions

- **The PNG is drawn in the browser from the same components, through a small library** (design, default library) — no server image route; rejected: drawing each card twice by hand on a canvas.
- **Paper is printed by the browser's print dialog; there is no server PDF** (design).
- ~~**The toggle reads "Frase destacada", on by default in 4:5**~~ — superseded 2026-11-22: the toggle is dropped, as the InterviewCard always shows the featured avisos.
- **The 4:5 card is the owner's InterviewCard, ported from the helper** (owner review, 2026-11-22) — `summary.html` and `summary.py` `page()`: the plate with the video's YouTube thumbnail (`i.ytimg.com`, loaded with `crossOrigin` so the PNG can draw it; maxres, else hq, else the plan C night band), the Fault, the wordmark, every block, every text ≥ 30 px. In a debate the first guest of `guests` takes the left half, mirrored, the second the right half. Two changes to the old card: the footer is the locked disclosure, never "no revisado por humanos"; until the owner answers, «Lo más grave» reads «Destacados», the severity line reads «Peso: 2 altos · 1 medio · 2 bajos», and an aviso's verdict reads "Falso, peso alto.". Rejected: the S5Export 4:5 with four figures and a "Frase destacada" toggle.
- **The card's ES · EN changes only its own words** (agent) — quotes and reasons stay in the language of the profile's analysis.
- **The owner swaps a debate's halves per video, in /admin** (owner, 2026-11-22) — the speaker order cannot tell which side of the thumbnail a guest sits on. One row of a `faces` table per swapped video, for every language, kept like `hidden` (no row: the speaker order); `swap` is a boolean of the public API, so the viewer, the plate and the cover read one rule in `src/web/src/faces.ts`. A debate of two guests only: with three or more there are no halves. Rejected: a per-guest side, and guessing the side from the image.

## Out of scope

- **The profile's share image** (a 1080 × 1080 card as `og:image` of a profile link): it needs storage for images in the collector and a headless renderer in the helper, a new contract. Proposed as its own RFC row; until then a profile link shows the video thumbnail.
- The "Careo" and comparison cards of S10's page.
