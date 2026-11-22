# Interview: public-web-page-for-approved-analyses

**Date**: 2026-11-17 · **Questions**: 8

## Sources

- The chat (2026-11-16)
- docs/RFC.md
- docs/ARCHITECTURE.md
- docs/research/ (abc-quality-2026-11-15.md, codex-cli.md, faster-whisper.md, one-step-install.md: none on this work)
- src/collector/src/index.ts

## Decided

| Question | Answer | Source | Date |
|---|---|---|---|
| An approved analysis exists only in the other language: does the video page show it, or answer 404? | It shows the analysis in the language that exists, with a note on top that names that language | accepted recommendation | 2026-11-16 |
| Anonymous web ids can rotate past the hard stop of 20 mark requests a day: is that acceptable in the beta? | Yes. The collector adds a global hard stop on web marks per UTC day (about 2,000), then refuses web marks until the next day. Marks never change what the page shows | accepted recommendation | 2026-11-16 |
| A video with several guests: which profile card is the share preview? | With one guest, that guest's profile card. With several guests, or before the card is uploaded, the video's YouTube thumbnail: one guest's card on a debate would look like picking a side. This replaces the earlier answer "the guest's profile card" (chat, 2026-11-16) | person | 2026-11-17 |
| When does precision come first again? | When the RFCs that improve the verifier are done (reviewed with an outside expert) | person | 2026-11-17 |
| Does recall first also lower the extension's player bars, or only change the web page? | Only the web page. The extension's player bars stay; its side panel already lists every flag. The verifier RFCs decide the bars | accepted recommendation | 2026-11-17 |

## Open

| # | Question | Blocks | Owner |
|---|---|---|---|
| 4 | Where does the card PNG live: a D1 row or R2? Decide from the measured card size against the D1 row limit, in the S0 research | S3 | team |
| 7 | ARCHITECTURE External systems: YouTube IFrame Player API · What does the page call, where is the contract written, and what do the terms allow beside an embed? Researched in S0 (`docs/research/youtube-embed.md`) | S1 | user |
| 8 | ARCHITECTURE External systems: Cloudflare Workers + D1 · How does the Worker serve the page files next to its routes (static assets), and where is that contract written? Researched in S0 (`docs/research/youtube-embed.md` or its own file) | S1 | team |
