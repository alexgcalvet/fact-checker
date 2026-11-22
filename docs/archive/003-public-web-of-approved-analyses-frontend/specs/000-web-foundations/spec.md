# S0 Web foundations

**Implements**: [RFC S0 Foundations](../../RFC.md#specs) · [ARCHITECTURE External systems](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

The public web needs the CALVET brand inside this repo before any screen is built: its colours and verdict marks, its three fonts with their licences, and its wordmark. It also needs a written answer to how Cloudflare serves one page for many web addresses and how the Worker writes a video's title and thumbnail into that page for link previews. With both in place, the viewer (S1) can start without guessing.

## Acceptance

- [X] A1 · The brand files are in the repo
  - **Story:** A developer opens the web's brand folder and finds the brand's token sheet with all six verdict marks (Falso, Engañoso, Retórica, Evasiva, Contexto, Correcto), the Newsreader, Host Grotesk and JetBrains Mono fonts each beside its open font licence, and the CALVET wordmark as an SVG.
  - **Test:** `check: bash tests/web/check-brand.sh`
- [X] A2 · The two Cloudflare contracts are written with their sources
  - **Story:** The owner opens the research file on static assets and reads, each with a Cloudflare docs link, how one HTML answers `/es/v/<id>` and `/en/...` while `/api/*`, `/admin*` and `/try/*` keep their routes, and how the Worker sets the title and image meta of that HTML for one video.
  - **Test:** `review: docs/archive/003-public-web-of-approved-analyses-frontend/research/workers-spa-and-rewriter.md`

## Files

| Path | Change |
|------|--------|
| `src/web/brand/tokens.css` | new — copy of the brand repo's f6 `tokens.css` (it has the Evasiva tokens), unchanged |
| `src/web/brand/fonts/` | new — the woff2 files, their `fonts.css` (`@font-face`, relative URLs) and the three OFL licences, copied from `src/helper/fact_checker/fonts/` |
| `src/web/brand/calvet-quilla-night.svg`, `calvet-quilla-nav.svg` | new — the wordmark as the brand repo ships it |
| `tests/web/check-brand.sh` | new — fails if a token, font, licence or wordmark is missing |
| `docs/archive/003-public-web-of-approved-analyses-frontend/research/workers-spa-and-rewriter.md` | new — both contracts, sources first |

## Tasks

- [X] T001 Copy the f6 tokens.css unchanged into `src/web/brand/tokens.css` → A1
- [X] T002 [P] Copy the fonts, their `fonts.css` and the licences into `src/web/brand/fonts/` → A1
- [X] T003 [P] Copy the two wordmark SVGs unchanged into `src/web/brand/` → A1
- [X] T004 Write the brand check in `tests/web/check-brand.sh` → A1
- [X] T005 [P] Read the Cloudflare docs (static assets routing, `not_found_handling`, `run_worker_first`, `HTMLRewriter`) and write `docs/archive/003-public-web-of-approved-analyses-frontend/research/workers-spa-and-rewriter.md` → A2

## Decisions

- **Fonts from the helper, not the brand repo** (default) — the helper already ships latin and latin-ext woff2 subsets with their OFL files; the brand repo has only Newsreader as ttf.
- **Brand files under `src/web/brand/`** (default) — S1 creates the Vite app around them; a later brand hex fix replaces one file.

## Out of scope

- The React app, Vite and routes: S1.
- Setting the External systems row to `confirmed`: `/rfc sync` after A2.
