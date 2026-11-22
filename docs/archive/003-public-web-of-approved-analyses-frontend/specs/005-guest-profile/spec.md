# S5 A guest's profile

**Implements**: [RFC Specs S5](../../RFC.md) · [ARCHITECTURE Contracts: `GET /api/videos/<id>?lang=`, `PUT /analyses/<video_id>`; Components: Shared analyses, Web app](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

Each guest of a video gets a page of their own: how long they spoke, how many avisos they got for each 10 minutes of their own speech, and every aviso by kind, each one linking to its moment in the video. Measuring against a guest's own speaking time is what makes two guests fair to look at side by side. The design is the approved canvas page `s5-perfil`, without the parts the RFC parks (the topic and question of a flag, the cover photo).

## Acceptance

- [X] A1 · The helper shares each person's speaking time and turns
  - **Story:** The owner runs `fact-checker shared upload debate01 es` for an analysis whose voice turns are on the machine. The uploaded analysis carries, per person, their role, seconds spoken, number of turns and longest turn, and the list of voice turns by person; two turns of one voice with no other voice between them count as one. For an analysis with no voice turns on the machine, those fields are absent and the upload still succeeds.
  - **Test:** `tests/helper/test_speech_upload.py`
- [X] A2 · A guest's profile shows their own-speech figures and their avisos
  - **Story:** A reader opens `/es/v/debate01/ana` (Ana spoke 28:40 of the debate's voices). The page reads Ana's share of speaking time, her turns, her longest turn, her avisos per 10 minutes of her own speech with its level marked provisional ("pocos avisos" under 5, "bastantes" to 8,9, "muchos" from 9), and the whole debate's figure beside it, never another person's. Her two gravest avisos are pinned first, then the rest by time; a filter bar over the list counts each kind ("–" for a kind she has none of, which cannot be tapped); a tap on "Retórica" lists only those, and the address becomes `?tipo=retorica`; a tap on one of her devices in "Lo que más repite" narrows the list to it (`&recurso=<rule id>`), a second tap clears it. Each aviso's time opens the viewer at that second. In the viewer, Ana's name on a flag links to this page.
  - **Test:** `tests/web/profile.test.ts`
- [X] A3 · A profile says what it cannot show
  - **Story:** For a video uploaded before speaking time existed, Ana's profile counts avisos per 10 minutes of video, says so, shows no level and reads "Tiempo de palabra: sin datos". For a video with no summary it reads "Esta ficha aún no existe" with a link to watch the video. In an interview, the host has no page of their own: `/es/v/intervw1/marta` shows the interview's guest list instead.
  - **Test:** `tests/web/profile-states.test.ts`
- [X] A4 · The owner reads a real guest's profile
  - **Story:** After deploy and after sharing a real debate again, the owner opens a guest's profile from the viewer on a laptop and a phone, checks it against the canvas, taps a kind, and jumps from an aviso to its moment.
  - **Test:** `review: the deployed profile of a real debate guest on a laptop and a phone, against the canvas page s5-perfil`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/analyses.py`, `src/helper/fact_checker/core/speakers.py` | edit — each person's speaking time and turns, and the voice turns by person, from the local voice turns |
| `src/collector/src/index.ts`, `src/collector/README.md`, `docs/api-examples/debate.json` | edit — serve `people` and `turns` |
| `src/web/src/Profile.tsx` | new — the profile: header, figures, voice lane, turns table, avisos explorer, states |
| `src/web/src/main.tsx`, `src/web/src/Viewer.tsx` | edit — route `/<lang>/v/<id>/<guest>`; the speaker's name links to it; `?t=` opens the viewer at a second |
| `src/web/src/texts.ts`, `src/web/src/style.css` | edit — the profile's texts and styles, laptop and phone |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Add each person's speech and the voice turns to the shared analysis, in `src/helper/fact_checker/analyses.py` and `src/helper/fact_checker/core/speakers.py` → A1
- [X] T002 Serve `people` and `turns` in the video route, in `src/collector/src/index.ts`, `src/collector/README.md`, `docs/api-examples/debate.json` → A2, A3
- [X] T003 Build the profile page and its route, in `src/web/src/Profile.tsx`, `src/web/src/main.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A2
- [X] T004 Link the speaker's name in the viewer and open the viewer at `?t=`, in `src/web/src/Viewer.tsx` → A2
- [X] T005 Add the states with no speaking time, no summary and a host, in `src/web/src/Profile.tsx` and `src/web/src/texts.ts` → A3
- [X] T006 Build into `src/collector/web/app/`, deploy, share the real debates again, and hand the owner the review → A4

## Decisions

- **A guest's slug is computed in the browser from their name** (canvas, A7 not needed) — "Ana Pérez (candidata)" → `ana-perez`.
- **The voice turns of the whole video go with the profile, not only the comparison** (default) — the profile's voice lane needs them; S10 reuses them.
- **Consecutive turns of one voice merge into one turn** (default) — the diarizer splits a voice at short pauses; rejected: raw diarizer turns.
- **Per-person levels are provisional: under 5, to 8,9, from 9** (owner) — tuned once real guests exist.

## Out of scope

- The comparison of a debate's guests and the "Comparar" link: S10.
- The "Descargar ficha" sheet and the share image: S11.
- The topic and question of a flag, and the face-centred cover: parked (RFC Open questions 2 and 3); the profile uses the canvas fallbacks.
