# S31 First flags fast

**Implements**: [ARCHITECTURE › One run](../../ARCHITECTURE.md#one-run), [ARCHITECTURE › Contracts](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

A person who clicks "Analizar este vídeo" at the start of a 15-minute interview sees no flag until about minute 2, because the analysis waits about two minutes for the speaker separation before it reads anything. This slice starts reading at once with the speakers told apart from the text, runs the speaker separation in the background, and fixes the names of the flags already shown once the voices are known, so the first flags arrive within about 30 seconds of the click. Meanwhile the panel says the analysis is being prepared, and an analysis that stops says why in one line.

## Acceptance

- [X] A1 · The first part is read before the voices are known
  - **Story:** The helper analyses an invented 12-minute interview from second 0, with a speaker separation that takes 5 seconds and part readings that take 0.2 seconds. The flag of the first 30 seconds is in the flag file before the speaker separation ends. When the person reaches minute 7, the part at minute 11 is read with the voice names ("[Invitado]") in its text.
  - **Test:** `tests/acceptance/test_s31_a1_first_part_first.py`
- [X] A2 · A flag shown before the voices are known gets the voice's name
  - **Story:** In the same interview, the reading of the first part pins the host's ad hominem at second 1 on "Invitado". Once the voices are known, the flag file names "Presentadora" for that flag, with the same id; a flag whose name already matches its voice keeps it.
  - **Edge case:** WHEN there is no Hugging Face token (no speaker separation) THEN the flags keep the names from the text and no speakers reading runs.
  - **Test:** `tests/acceptance/test_s31_a2_names_corrected.py`
- [X] A3 · The panel says the analysis is being prepared, or why it stopped
  - **Story:** A person clicks "Analizar este vídeo". Until the first part is read, the panel tab says "Preparando el análisis…" ("Preparing the analysis…" in English), then "Avisos (1)". If the analysis stops because YouTube gave no captions, the player shows "El análisis se paró: YouTube no dio los subtítulos. Vuelve a intentarlo en unos minutos." and the "Analizar este vídeo" button shows again.
  - **Edge case:** WHEN the analysis stopped because it spent its budget THEN the button does not show again.
  - **Test:** `tests/acceptance/s31-a3-preparing-and-stopped.test.ts`
- [X] A4 · The time to the first part is logged
  - **Story:** After an analysis with part readings of 0.2 seconds, the flag file holds `first_flags_s`, the seconds from the start of the analysis to the first part written, such as 0.4; later parts do not change it, and a shared copy of the analysis leaves it out.
  - **Test:** `tests/acceptance/test_s31_a4_first_flags_logged.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/server.py` | edit — `run_analysis`: voices in a background thread, later parts read with them, names corrected, `first_flags_s` |
| `src/helper/fact_checker/core/speakers.py` | edit — the name of the voice heard at a second |
| `src/extension/src/panel.ts`, `texts.ts`, `flags.ts`, `content.ts` | edit — "Preparando el análisis…", the stop line, the button after an error stop |
| `src/helper/fact_checker/extension/` | edit — the rebuilt bundle |
| `docs/ARCHITECTURE.md` | edit — One run and the flag file's `first_flags_s` |
| `tests/acceptance/` | new — the tests and `s31_fakes.py` |

## Tasks

- [X] T001 Voices in the background, later parts with voices, names corrected in `server.py` and `core/speakers.py` → A1, A2
- [X] T002 `first_flags_s` in the flag file in `server.py` → A4
- [X] T003 [P] The preparing tab, the stop line and the button after an error stop in `panel.ts`, `texts.ts`, `flags.ts`, `content.ts`; restart an error-stopped analysis in `server.py`; rebuild the bundle → A3, FR-001
- [X] T004 One run and the flag file in `docs/ARCHITECTURE.md` → A1, A4

## Requirements

- [X] FR-001 — `POST /videos/<id>` MUST start again an analysis whose `stop_reason` starts with `error`; a `budget` stop or a done analysis is served as it is.

## Decisions

- **The analysis waits at most 1 s for the voices after the captions** (default) — voices that are ready at once (a cached separation) name the first part too; rejected: never waiting, which reads the first part without voices even then.
- **Correction rule: a flag takes the name of the voice heard at its second, if the voices give one and it differs; its id and everything else stay** (default) — the rule that S21 measures; rejected: dropping a shown flag whose words cross voices.
- **The analysis says done only after the voices are known and the names corrected** (default) — a whole, shared analysis carries the voice names.
- **A failed or over-budget speaker separation writes a `speakers` usage line with the reason; the analysis keeps the text names** (default) — a lost voice is no reason to stop.
- **The first part keeps the screen** (default) — the screen adds about 4 s and the target stays under 30 s; skipping it would read every opening greeting in full.
- **`first_flags_s` goes in the flag file, not the usage log** (default) — the panel reads it to leave "Preparando"; the shared copy drops it.
- **The stop line maps the reason to five kinds: captions, speech engine, budget, provider, other** (default) — the raw reason stays in the flag file.

## Out of scope

- A real-run measurement of `first_flags_s` on the person's laptop: the lead, later.
- The positions list of earlier parts keeps the text names.
