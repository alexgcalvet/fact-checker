# Interview: public-web-frontend

**Date**: 2026-11-21 · **Questions**: 7

## Sources

- the chat
- docs/archive/003-public-web-of-approved-analyses-frontend/research/calvet-brand.md
- docs/ARCHITECTURE.md (Components, Contracts, Decisions)
- docs/archive/002-public-web-of-approved-analyses-backend-first/RFC.md and its research

## Decided

| Question | Answer | Source | Date |
|---|---|---|---|
| Where is the frontend built? | In this repo, not in the brand repo; the brand repo gives only the brand (tokens, fonts, wordmark, verdict marks). Replaces the decision of RFC 002 that the frontend is its own RFC in the brand repo | person | 2026-11-21 |
| Who designs the screens? | The owner and the agent, here; the brand repo's screen brief is not followed | person | 2026-11-21 |
| One language or two? | Bilingual, Spanish and English, as the API serves them | person | 2026-11-21 |
| How does a viewer say a flag is right or wrong? | Through the existing contracts, no API change: the web marks (correct, unfair) and the method feedback (unfair flag plus rule; a comment anchored to the flag's quote, which is "Matizar"). The frontend only presents them | person (delegated to the agent's recommendation) | 2026-11-21 |
| Are the guest profile and the comparison screens in scope? | Yes, designed here | person | 2026-11-21 |
| Which technology? | React with Vite and TypeScript, built to static files that the collector Worker serves (same origin as the API, one deploy). The Worker injects per-video share meta with `HTMLRewriter`. The web panel is written in React; the pure logic (active flag by second, order) moves to a module that the extension shares; the extension does not change. Rejected: server rendering (Next, Astro), plain TypeScript | accepted recommendation | 2026-11-21 |
| Which CALVET verdict mark does each flag get? | inaccuracy `false` → Falso; `misleading`, `definition_swap`, `plan_as_fact` → Engañoso; fallacy, bias, contradiction → Retórica (as the profile card counts them); `context` and a judge's nitpick (puntualización) → Contexto; Correcto is no flag, only the summary's correct claims. Dodged and partial questions → Evasiva, the sixth mark that the brand repo added (docs/archive/003-public-web-of-approved-analyses-frontend/research/calvet-brand.md) | accepted recommendation | 2026-11-21 |
| What are the web's addresses? | On the collector Worker: `/` picks `/es/` or `/en/` from the browser; `/<lang>/` the video list; `/<lang>/v/<video>` the viewer; `/<lang>/v/<video>/<guest>` a guest's profile; `/es/v/<video>/comparar` and `/en/v/<video>/compare` the comparison; `/es/como-funciona` and `/en/how-it-works`. `/admin`, `/api/*` and `/try/*` stay. A custom domain waits until the web goes public | accepted recommendation | 2026-11-21 |
| What happens to the test page `/try/`? | It stays while the new viewer is built. Once the viewer works, `/try/<video>` redirects to `/<lang>/v/<video>`, its page and script go, and its tests move to the viewer | accepted recommendation | 2026-11-21 |
| How is each screen designed? | First in Claude Design, with the CALVET brand and real API data; once the owner approves the design, it is built in React with its tests | person | 2026-11-21 |
| Do we count visits? | Yes, as aggregate counters in the Worker: visits per video and language and clicks on "go to the moment", summed per day in D1; no cookie, no per-person id, no third party; shown in `/admin` | accepted recommendation | 2026-11-21 |
| In what order are the screens built? | 1 the viewer of one video; 2 the video list; 3 a guest's profile (the profile card of a person who speaks in the video, as a page; no viewer login) and the comparison; 4 how it works, with method feedback; 5 visits in `/admin` and the `/try/` redirect | accepted recommendation | 2026-11-21 |
| Which verdict mark does a disputed claim ("Dato discutido": the sources disagree) get? | Engañoso, with the sub-label "Dato discutido · las fuentes no coinciden" and every source that disagrees; no new mark. Dissent (editorial lens): Contexto, because Engañoso is a verdict that the sources do not back | design panel of three agents, 2 to 1, delegated by the person | 2026-11-21 |
| How does the web disclose that the analysis is automated? | One line under the title on every viewer screen, and on every shared card: "Análisis automático con IA · revisado por una persona antes de publicarse · <fecha> · Las marcas son señales, no veredictos" with a link to how it works; not on each flag | design panel, unanimous on the line, delegated by the person | 2026-11-21 |
| How are flags counted on the viewer? | Context notes apart: "74 avisos · 70 notas de contexto"; a per-speaker count and a speaker filter, shown neutrally, never as a ranking. Dissent (editorial lens): no speaker split or filter until counts are normalised by speaking time | design panel, 2 to 1, delegated by the person | 2026-11-21 |
| How are flags under 60 % confidence shown? | Shown and counted, with the verdict word dimmed and the label "confianza baja · NN %". Dissent (editorial lens): hidden by default, and no public Falso or Engañoso under 70 % | design panel, 2 to 1, delegated by the person | 2026-11-21 |
| Panel open and a card over the video at once? | No: with the panel open nothing shows over the video; the card shows only with the panel hidden or in full screen; a context flag shows as a folded pill, never a card | design panel review (three reviewers agreed), accepted by the person | 2026-11-21 |

## Open

| # | Question | Blocks | Owner |
|---|---|---|---|
