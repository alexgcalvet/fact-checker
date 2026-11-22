# S1 Watch a video with its flags

**Implements**: [RFC S1](../../RFC.md#specs) · [ARCHITECTURE Components: Web app, Panel logic](../../../../ARCHITECTURE.md) · [Contracts: `GET /`, `/es/*`, `/en/*`](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

Anyone with the link opens an approved video on the public web, in the CALVET look, in Spanish or English: the video plays with a timeline of its flags under it and a panel beside it, the flag being said lights up, and a click on a flag jumps the video there. A link shared in a chat shows the video's thumbnail and title. This is the first screen of the web and replaces the plain test page as the way to watch an analysis.

## Acceptance

- [X] A1 · The viewer follows the player
  - **Story:** A viewer opens `/es/v/debate01` (the invented debate) and plays it. At second 80 the panel lights the flag said at second 75 and no later one; the viewer taps the time 20:10 of a flag and the video jumps to 1210 and keeps playing; tapping the flag's text does the same and also opens its reason (owner decision after the second review, 2026-11-21).
  - **Test:** `tests/web/viewer-follows-player.test.ts`
- [X] A2 · Each flag shows its CALVET verdict mark
  - **Story:** In the same viewer, on the timeline and in the panel, a false claim shows "Falso", a misleading one "Engañoso", an ad hominem "Retórica", a dodged question "Evasiva", a disputed claim "Engañoso" with "Dato discutido" under it; a context flag shows "Contexto" and a judge's nitpick "Puntualización" with the context mark, both in the panel only, with no mark on the timeline; a flag at 55 % shows its word dimmed with "confianza baja"; in English the words are False, Misleading, Rhetoric, Evasive, Context, Nitpick.
  - **Test:** `tests/web/viewer-verdict-marks.test.ts`
- [X] A3 · A shared link previews the video
  - **Story:** A chat app fetches `/en/v/debate01`; the page it gets is the web app, marked noindex, with the title "Invented debate" and the video's YouTube thumbnail in its share tags. For a video that is not approved, the tags keep the web's neutral title.
  - **Edge case:** WHEN the title holds `"` and `<` THEN the share tags show them as text and the page stays valid.
  - **Test:** `tests/collector/share-meta.test.ts`
- [X] A4 · The owner watches a real debate on a laptop and a phone
  - **Story:** The owner approves the viewer's design in Claude Design ([canvas](https://claude.ai/artifact/EwgFmpq5FYjNXnpNjf6qZr)), then opens a real approved debate after deploy on a laptop and a phone, in Spanish and English: flags light, a click seeks, and a link pasted in a chat shows its thumbnail and title.
  - **Test:** `review: the deployed viewer on a laptop and a phone, both languages`

## Files

| Path | Change |
|------|--------|
| `src/shared/panel.ts` | new — the flag lit at a second and the flag order, moved from the extension's panel |
| `src/extension/src/panel.ts` | edit — import the lit-flag rule from `src/shared/` |
| `src/web/` (`package.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/Viewer.tsx`, `src/marks.ts`, `src/texts.ts`) | new — the React app: router by path, the viewer, the verdict-mark mapping, es/en texts, the brand from `src/web/brand/` |
| `src/collector/web/app/` | new — the committed Vite build |
| `src/collector/src/index.ts` | edit — `/` redirects by language; `/es/*`, `/en/*` serve `/app/` with the share tags rewritten |
| `src/collector/wrangler.toml` | edit — `run_worker_first` adds `/`, `/es/*`, `/en/*` |
| `src/extension/vitest.config.ts` | edit — resolve `react` and `react-dom` from `src/web/` for the web tests |
| `.github/workflows/checks.yml`, `.claude/mini-spec.yml` | edit — web typecheck, build-matches-commit check, brand check |

## Tasks

- [X] T001 Design the viewer (laptop and phone) in Claude Design with the CALVET brand and the real API answer of an approved debate; the owner approves it → A4
- [X] T002 [P] Move the lit-flag and order rule into `src/shared/panel.ts` and import it in `src/extension/src/panel.ts` → A1
- [X] T003 Scaffold the Vite React app with base `/app/`, noindex and neutral share tags in `src/web/`, and resolve React for the tests in `src/extension/vitest.config.ts` → A1
- [X] T004 Build the viewer from the approved design: embed, timeline with clustered marks, panel (counts, speaker filter, legend, expand vs seek, back to now), card and pill over the video when the panel is hidden, the AI line, the states, phone layouts, both languages, in `src/web/src/Viewer.tsx` → A1
- [X] T005 Map each flag to its verdict mark and word in `src/web/src/marks.ts` → A2
- [X] T006 Serve `/`, `/es/*`, `/en/*` and replace the share-tag placeholders with escaped values (no `HTMLRewriter`) in `src/collector/src/index.ts` and `src/collector/wrangler.toml` → A3
- [X] T007 Add the web checks to `.github/workflows/checks.yml` and `.claude/mini-spec.yml`, build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **Tests mount the app into jsdom through its own `mount` export** (default) — as the test page tests do with the fake player and the invented API; no Testing Library.
- **The Worker reads the title from the stored approved analysis** (default) — the API already serves it; no YouTube call from the Worker.
- **The app is a dependency-light React app: React, ReactDOM, Vite, no router library** (default) — five path patterns; a router library earns its place later if at all.

## Out of scope

- The review date in the AI line: the API serves none; the line shows no date until BACKLOG item 18.
- Phone landscape full screen (the canvas board PhoneFull): S3.

- The note when only the other language exists: proposed for S4, where the list shows each video's languages.
- Marks and comments from the viewer (S2), full screen (S3), visits and the `/try/` redirect (S7).
