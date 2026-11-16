# S33 Who is who

**Implements**: [RFC › Specs](../../RFC.md#specs), [ARCHITECTURE › Contracts](../../../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

Today the summary image of an interview puts the host's flags beside the guest's, which sets one against the other. After this slice, the reading that names the voices also says who is the host and who is the guest, with the guest's full name and how long each one speaks. The image then shows the guests only, and the person can fix a wrong role from the side panel.

## Acceptance

- [X] A1 · Each voice gets a role, a person and its seconds of speech
  - **Story:** The person analyses an invented interview where the host opens with "Buenos días, hoy está con nosotros Ana Ruiz". The flag file lists the host as `host` and Ana Ruiz as `guest` with the person "Ana Ruiz", and the seconds each one speaks, for example 1260 and 2460.
  - **Edge case:** WHEN the voices cannot be separated THEN the file has no people, and the export gives a card for every speaker (S35).
  - **Test:** `test_s33_a1_people_in_flag_file.py`
- [X] A2 · The summary image leaves out the host
  - **Story:** In the invented interview, the person marks correct one flag of the host and two of Ana Ruiz, then exports the summary. The export has one card, Ana Ruiz's (S35); the card and its alt text show her two flags, and nothing of the host.
  - **Test:** `test_s33_a2_guests_only.py`
- [X] A3 · A role the person sets holds, and the image follows
  - **Story:** The reading took a guest for the host. The person sets that speaker to guest from the side panel and exports the summary again. The export now has a card for that speaker (S35). When the analysis later names the voices again, the role the person set stays.
  - **Test:** `test_s33_a3_role_set_by_person.py`
- [X] A4 · The side panel lists the speakers and switches a role
  - **Story:** The person opens the side panel of the interview. Under the filters it lists "Presentador · Host" and "Ana Ruiz · Invitada". A click on the role of the host turns it into Invitada, and the helper is told.
  - **Test:** `s33-a4-roles-in-panel.test.ts`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/core/speakers.py` | edit — the speaker reading answers a role and a person per voice; seconds of speech from the voice turns |
| `src/helper/fact_checker/server.py` | edit — `people` written with the voices, keeping `set_by: person`; `POST /videos/<id>/people` |
| `src/helper/fact_checker/core/summary.py` | edit — with `people`, only guests get a box |
| `src/helper/fact_checker/analyses.py` | edit — `people` in a shared analysis |
| `src/extension/src/flags.ts` | edit — the `people` type |
| `src/extension/src/panel.ts` | edit — the speakers list with a role switch |
| `src/extension/src/texts.ts` | edit — host and guest in Spanish and English |
| `src/extension/src/content.ts` | edit — the panel sends a role change |
| `src/extension/src/sw.ts` | edit — the `role` request to the helper |
| `tests/acceptance/` | new — the tests |

## Tasks

- [X] T001 Add role and person to the speaker reading, and seconds of speech per voice, in `speakers.py` → A1
- [X] T002 Write `people` with the voices in `server.py`; add `people` to `SHARED` in `analyses.py` → A1
- [X] T003 [P] Give a box only to guests when the file has `people` in `summary.py` → A2
- [X] T004 Add `POST /videos/<id>/people` and keep a person's role on a later naming in `server.py` → A3
- [X] T005 Add the people type, the speakers list, the texts, the request and its wiring in `flags.ts`, `panel.ts`, `texts.ts`, `content.ts`, `sw.ts` → A4

## Requirements

- [X] FR-001 — `POST /videos/<id>/people` MUST answer 400 for a name not in `speakers` or a role other than `host` or `guest`.

## Decisions

- **The person comes from the conversation, else from the video title** (default) — a guest is often named only in the title; a name never said or written stays the speaker's label.
- **No `people` without separated voices** (default) — the speakers told apart from the text (S31) are too rough for a role; the image falls back to every speaker.
- **A voice under 5 % of the talk gets no entry** (default) — it is already noise for the voice turns.

## Out of scope

- The profile card and its layout: S35. Severity: S34. Matching one person across videos: S36.
