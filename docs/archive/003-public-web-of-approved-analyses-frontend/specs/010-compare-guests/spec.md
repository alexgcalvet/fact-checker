# S10 Compare the guests

**Implements**: [RFC Specs S10](../../RFC.md) · [ARCHITECTURE Components: Web app; Contracts: `GET /api/videos/<id>?lang=`](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

A debate gets one page that sets its guests side by side: how much each one spoke, how many avisos each got per 10 minutes of their own speech, how many of their checked facts were right, how serious and how evasive they were. Each guest is measured against the whole debate on one shared scale, never ranked against another person, so a reader sees the differences without being told who "won". The design is the approved canvas board `S5Compare`.

## Acceptance

- [X] A1 · Two guests face each other on one scale
  - **Story:** A reader opens `/es/v/debate01/comparar` (Ana spoke 28:40 and Luis 24:50 of the debate's voices). Each figure is one row of a balance: Ana's value and bar on the left, the label on the spine, Luis's bar and value on the right, both bars on the same scale. The rows read speaking time (48,3 % and 41,9 %), avisos per 10 minutes of own speech with a mirrored mix bar and each one's provisional level (2,1 and 2,4), datos correctos (60 % and 50 %), graves per 10 minutes, preguntas eludidas with one cell per question, and what each one repeats most. Each row shows the debate's own figure (2,2 avisos, 56 % correct) and nothing says who speaks or errs most. Each guest's header links to their profile ("Ver su ficha"). Under the rows, "Quién habla y cuándo" shows every voice's lane, the host's included, and each voice's turns.
  - **Test:** `tests/web/compare-balance.test.ts`
- [X] A2 · Three or more guests line up in columns
  - **Story:** For a debate with 4 guests, `/es/v/<id>/comparar` shows one column per guest and one row per figure, every row on its own shared scale. With 5 guests the fifth column is reached by scrolling the table sideways inside its frame; nothing covers it. `/en/v/<id>/compare` shows the same in English.
  - **Test:** `tests/web/compare-columns.test.ts`
- [X] A3 · The comparison is reachable and says when it cannot compare
  - **Story:** In the viewer of debate01, the guest row reads "Invitados: Ana · Luis · Comparar", and the guest switcher of each profile ends with "Comparar"; both lead to the comparison. An interview shows no "Comparar", and `/es/v/intervw1/comparar` shows its guest list instead. A debate uploaded before speaking time existed shows "Sin tiempo de palabra no se puede comparar" with links to each guest's profile, and no figures.
  - **Test:** `tests/web/compare-ways-in.test.ts`
- [X] A4 · The owner compares the guests of a real debate
  - **Story:** After deploy, the owner opens the comparison of a real debate from the viewer on a laptop and a phone, checks it against the canvas, and opens a guest's profile from it.
  - **Test:** `review: the deployed comparison of a real debate on a laptop and a phone, against the canvas board S5Compare`

## Files

| Path | Change |
|------|--------|
| `src/web/src/figures.ts` | new — a guest's figures and the debate's pooled figures, moved out of the profile so both pages compute them once |
| `src/web/src/Compare.tsx` | new — the comparison: balance, columns, voice lanes and turns, states |
| `src/web/src/Profile.tsx` | edit — read its figures from `figures.ts`; "Comparar" in the guest switcher; export the voice lanes for reuse |
| `src/web/src/main.tsx`, `src/web/src/Viewer.tsx` | edit — route `/<lang>/v/<id>/comparar` and `/compare`; "Comparar" in the viewer's guest row |
| `src/web/src/texts.ts`, `src/web/src/style.css` | edit — the comparison's texts and styles, laptop and phone, inside the 1200 px page container |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Move a guest's figures and the pooled debate figures into `src/web/src/figures.ts` and read them from `src/web/src/Profile.tsx` → A1
- [X] T002 Build the balance for 2 guests, the voice lanes and turns, in `src/web/src/Compare.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T003 Add the columns for 3 or more guests with the sideways scroll, in `src/web/src/Compare.tsx` and `src/web/src/style.css` → A2
- [X] T004 Route the comparison, add "Comparar" to the viewer and the profile, and the interview and no-speech states, in `src/web/src/main.tsx`, `src/web/src/Viewer.tsx`, `src/web/src/Profile.tsx`, `src/web/src/Compare.tsx` → A3
- [X] T005 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **No API change: the page computes from `people`, `turns`, `summary` and the flags** (default) — S5 already serves them.
- **The comparison's slug is a word, `comparar` / `compare`** (canvas) — a guest whose slug is the same word loses their profile URL; accepted for the beta.
- **The phone shows one block per figure, one line per guest** (canvas) — rejected: the laptop's balance squeezed to 390 px.

## Out of scope

- The guests' names in the video list linking to profiles: S8.
- The card download and share image: S11.
- Topic grouping and the face cover: parked (RFC Open questions 2 and 3).
