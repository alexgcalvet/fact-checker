# S6 How it works

**Implements**: [RFC Specs S6](../../RFC.md) · [ARCHITECTURE Contracts: `GET /`, `/es/*`, `/en/*`, `GET /api/prompts/<version>`, `POST /api/feedback`; Components: Web app](../../../../ARCHITECTURE.md)
**Approval**: agent · approved 2026-11-21

## Summary

A reader opens one page that shows how a video becomes avisos: the eight steps with the model each one uses, the open loop through which people's corrections change the instructions, where each mark comes from, how severity, confidence and sources work, and the instructions themselves. The technical detail hides until the reader asks for it, and the reader can comment on any rule or send a general correction. The design is the approved canvas page `s6-como`, inside the shared reading-page frame.

## Acceptance

- [X] A1 · The page explains the method in diagrams, with details on demand
  - **Story:** A reader opens `/es/como-funciona` from the header's "Cómo funciona", which is lit. They see the route of eight steps (Transcribir to Publicar), each with its model ("Haiku · barato", "Opus · caro", "Persona" on Aprobar, "Sin IA" on Publicar), the loop back with "Se mide" marked "Planeado", the tree from which each mark comes (Falso, Engañoso, Retórica, Evasiva, Puntualización, Contexto), the severity scale (leve up to 1,4×, moderada to 2×, grave over 2×) and the confidence and sources blocks. Hovering, tabbing or tapping a box opens its detail beside it, never over it: plain text with no heading, and no `</>` marker or details switch anywhere (owner, after review). `/en/how-it-works` shows the same in English.
  - **Test:** `tests/web/how-method.test.ts`
- [X] A2 · A reader comments on a rule of the instructions
  - **Story:** In "Las instrucciones" the reader sees the version of the newest approved analysis's prompts and one closed block per component. They open "judge", select words of one of its rules, press "Comentar esta frase", accept the consent once, write "Esta regla es demasiado estricta" and send it. The owner sees in `/admin` a prompt comment with that version, component, rule, the selected words and the text.
  - **Test:** `tests/web/how-rule-comment.test.ts`
- [X] A3 · A reader sends a general correction
  - **Story:** A reader follows "Corrígenos" in the footer and lands on the form at `#feedback`. They pick the step their comment is about, write a comment and send it with the bone button; the page says it was sent and reads "Anónimo: sin tu nombre, tu correo ni tu IP.". The owner sees it in `/admin`. With no step picked, the button stays disabled.
  - **Test:** `tests/web/how-general-comment.test.ts`
- [X] A4 · The owner reads the page
  - **Story:** After deploy, the owner reads `/es/como-funciona` and `/en/how-it-works` on a laptop against the canvas, opens a detail and sends a comment that shows in `/admin`.
  - **Test:** `review: the deployed page in both languages on a laptop, against the canvas page s6-como, and the comment in /admin`

## Files

| Path | Change |
|------|--------|
| `src/web/src/How.tsx` | new — the page: hero, route and loop, marks tree, severity, confidence and sources, instructions, the comment form |
| `src/web/src/main.tsx`, `src/web/src/Footer.tsx` | edit — route `/es/como-funciona` and `/en/how-it-works`; "Cómo funciona" lit in the pill bar |
| `src/web/src/Feedback.tsx` | edit — a prompt comment with the consent the viewer uses |
| `src/web/src/texts.ts`, `src/web/src/style.css` | edit — the page's texts in both languages and its styles under `.how` |
| `src/collector/web/app/` | edit — the rebuilt app |

## Tasks

- [X] T001 Route the page, light its pill item, and draw the hero, switch, route and loop with their details, in `src/web/src/How.tsx`, `src/web/src/main.tsx`, `src/web/src/Footer.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T002 Draw the marks tree, severity, confidence and sources with their details, in `src/web/src/How.tsx`, `src/web/src/texts.ts`, `src/web/src/style.css` → A1
- [X] T003 Load the newest approved prompts and comment on selected words of a rule, in `src/web/src/How.tsx` and `src/web/src/Feedback.tsx` → A2
- [X] T004 Add the general comment form at `#feedback`, in `src/web/src/How.tsx`, `src/web/src/texts.ts` → A3
- [X] T005 Build into `src/collector/web/app/`, deploy, and hand the owner the review → A4

## Decisions

- **The models shown are the defaults of the Claude provider, marked as defaults** (default) — the API serves no model per step; rejected: a new API field.
- **The instructions shown are those of the newest approved video's prompts version** (default) — the collector has no "latest version" route.
- **A general comment names the step it is about, from the prompts' components** (default) — `POST /api/feedback` needs a component; rejected: a new feedback kind.
- **"Usada en N vídeos" and "en prueba: sonnet" are left out** (design) — the API does not give the first, and no step uses Sonnet.

## Out of scope

- The phone layout: not designed yet; the sections stack and a tap opens a detail.
- The visible copy (lede, box lines, definitions) follows the design session's cleaned board when it arrives; details already live in popovers.
