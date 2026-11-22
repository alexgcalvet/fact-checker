# CALVET brand for the public web (2026-11-21)

Sources:
- A message from the brand repo session, 2026-11-21 (chat).
- Later messages from the brand repo session, 2026-11-21 (chat): f6, then f7, replace f5.
- Brand files on the owner's machine, outside this repo: `frontend-design/.calvet-work/calvet-final/sketches/f7/tokens.css` (CSS custom properties, Evasiva included), `…/f7/spec.md` (rules, components, verdict code, charts; §17 and §18 have the f6 and f7 rules, §18.6 the Evasiva SVG recipe), `…/logo/calvet-quilla*.svg` (wordmark, redrawn in f6).

## Conclusion

- The web takes the CALVET **brand** from the brand repo: its tokens, fonts, wordmark and verdict marks. The layout and the screens are designed here (chat: "the brand, not the design").
- Use the token names, never hard-coded hex: a later fix pass may change a few hexes, and the swap must be one file.

## Brand rules

| Item | Rule |
|---|---|
| Ground | Pure black `#000` |
| Bone `#E6DCC4` | Titles and the wordmark |
| Text | `--t1`…`--t4`; never information in `--t4` |
| Fonts | Newsreader for the work (titles, quotes), Host Grotesk for the tool (UI), JetBrains Mono for the measure (times, numbers, counts) |
| Glass | Each nav, tab strip, filter and toolbar is one glass pill (`--glass-*`, `--r-pill`); at most one bone primary button per screen |
| Calm | No bouncing motion, candy colours or decorative gradients |
| Amber `#D99A2B` (`--amber`) | The one amber on night (f6; `#C48725` retired). Two shapes only: filled for the beat (playhead, "verificando", live); ring with "!" for misleading and system errors. Never for counts, progress or decoration |
| Gold `#F2D9A6` | One key datum per screen, and only on a screen with no amber at all; where any amber shows (playhead, Engañoso ring), the featured datum is bone (f7 §18.3) |
| Wordmark | The SVG as it is; never CALVET typed in a font |
| Verdict marks | Colour, shape and word together, in a fixed order: Falso (oxide disc ×), Engañoso (amber ring !), Retórica (bone hollow diamond ~), Evasiva (dusty-lilac half-filled disc ?), Contexto (grey rounded square i), Correcto (lens-blue seal ✓). Hexes in `--st-*`. Oxide red is only for Falso. Glyph from 14 px; lane marks 10 px with a 2 px night halo, never smaller |
| Evasiva | Added by the brand repo for this web (2026-11-21): word es "Evasiva", en "Evasive"; subtype line es "Pregunta esquivada" / "Respondida a medias", en "Question dodged" / "Partly answered". Tokens `--st-evasiva` (mark on night), `--st-evasiva-text` (word on night), `--st-evasiva-bone` (on bone paper); never a chart series, a link or decoration |
| Charts | Categorical slots `--ch-1…5` in fixed order, one axis, legend and direct labels; a delta is arrow, sign and value. A comparison or average line is bone dashed, never a colour. A chart sits in its own framed card, at least 24 px from any Engañoso mark; never recolour it (f6) |
