# Interview: remaining-backend

**Date**: 2026-11-21 · **Questions**: 6

## Sources

- the chat
- docs/RFC.md (Specs table, Open questions)
- docs/ARCHITECTURE.md (Components, Contracts, Decisions)
- docs/research/interview-public-web-page-for-approved-analyses.md
- src/helper/fact_checker/core/summary.py (`card`)
- git log of src/helper/fact_checker/core/ since 2026-11-16

## Decided

| Question | Answer | Source | Date |
|---|---|---|---|
| Where is the guest summary computed once the owner hides flags in `/admin`, where no Python runs? (RFC open question 1, blocks S4 and S5) | (a) The uploader's helper computes it and tags each flag with the counts it adds to (wrong kind, severity, device, gravest candidate); the Worker sums the flags that are not hidden. The card logic stays in Python | accepted recommendation | 2026-11-21 |
| When the owner hides a flag, how does its claim count in the guest summary? (S5) | As an `unfair` mark does on the card: the flag counts nowhere and the claim stays checked, so it counts as correct (3 false of 20 becomes 2 false and 18 correct of 20) | person | 2026-11-21 |
| How does a real approved video get a prompts file for the S7 and S8 reviews? | Re-upload a recent local analysis (debate B) with the current prompts, at no cost. Its prompts differ from the current ones by one line only (speakers prompt, 2026-11-20: in a debate only a moderator is host), which changes no flag; git history of `core/factcheck.py`, `judge.py`, `pipeline.py`, `speakers.py`, `flags.py` since 2026-11-16 | person | 2026-11-21 |
| When does the frontend RFC (brand repo) start? | After this RFC closes: finish all the backend first. This replaces "designed in parallel" in the RFC Decision of 2026-11-20 | person | 2026-11-21 |
| In what order are the remaining specs built? | S4 → S5. S4 is checked on an analysis already uploaded again with the current helper, with no paid run | person | 2026-11-21 |
| Do S9 and S10 stay in this RFC? | No. This RFC is the backend of the web only. S9, S10 and the new real analysis of debate B move to the next RFC (verifier quality). The rule stays: nothing goes public before S9, S10 and the Workers Paid plan; it gates going public, not closing this RFC | person | 2026-11-21 |

## Open

| # | Question | Blocks | Owner |
|---|---|---|---|
