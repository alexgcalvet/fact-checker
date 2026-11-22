# Validation quality: lessons from other fact-checkers

Living file. Each source that the owner shares is read once, and its problems and ideas land here. Add a row, never a section per source.

Sources are paraphrased. Handles and names are removed, and the raw text is not kept.

## Sources

| ID | Origin | What it says | Read on |
|---|---|---|---|
| A | Owner's message | The verifier misses nuance, half-truths and deception by omission. Example: the growth of the pension reserve, shown with no debt and no state transfers to the pension system. | 2026-11-21 |
| B | Public post, observer of a verified debate | Verification needs tuning. Official sources are not always trustworthy (a polling institute is the example). The verifier struggles with nuance, with links between answers given at different moments, and with inconsistencies that a person who knows the backstory sees. It matched a human expert on a vacation contradiction and a changed definition of "homes delivered", and found many disputable claims on one topic. It missed a quantitative argument (rail investment x20), hypotheses about a phone hack, and the links between alleged plots. | 2026-11-21 |
| C | Public reply, evaluation specialist | Owner is the only annotator, so more interviews of one speaker add volume, not evidence. Fix: independent judges on the same clips with an agreement score, plus 5 runs of the judge for variance. Part of the install friction comes from an audience that wants binary verdicts. Fix: the two axes of ICD 203 (likelihood on a bounded verbal scale, confidence in the evidence base). One "60 %" mixes both, and the model uses its self-reported confidence as the likelihood of the verdict. | 2026-11-21 |
| D | Public reply, viewer | A serious-insinuation flag on a question about alleged rigging in a party primary biases the measure. The question has a public basis (videos, statements of witnesses). The owner agreed: the item should be a context flag, or a lower severity, because a case with no ruling exists. | 2026-11-21 |
| E | Public article, behavioural analysis of a 1 h 43 min interview | Not a fact-checker: it measures pauses, voice, face and rhetoric with software, and links each finding to a published study. It states no intent, labels facial emotions as "suggested", compares the speaker with his own other interviews, and lists its limits. It also counts how many delicate questions got a full, partial or no answer (13, 6, 3 of 22). It ends on why the same interview pleases one half of the audience and irritates the other. | 2026-11-21 |
| F | Public article, same author, analysis of a 96 min debate between two leaders | Same method on both sides with one rule. Adds a figure-by-figure fact-check: 67 verdicts (24 and 43) on a five-level scale (true, true with nuance, misleading, false) plus 20 figures left unverifiable. Each verdict has at least 2 sources, official first. It tests viral claims against measurements, runs two independent passes on the discourse labels (kappa 0.72–1.0), and states that 88 % of the words have a verified speaker and that no full human review was done. Its own counts do not agree with each other (see P14). | 2026-11-21 |
| G | Public reply, same specialist as C, second message | Calibration rests on one interview and on the model's self-reported confidence. At the edge (the insinuation case) the rule does not decide. Several annotators and variance between runs would move the result from promising to citable. | 2026-11-21 |
| H | Video interview (1 h 8 min) of the author of E and F, with a channel host | Method: an LLM classifies each question by written criteria (hardness, assertiveness, dominance) and the author corrects its drafts; face and voice software; a public site with the per-minute data and an interactive timeline. Findings that matter to us: the speaker who answers most is also the one asked to repeat most; the speaker who gives exact figures has the most checkable errors, as a striker who shoots most misses most; a fluent answer that stays on the surface is easy to agree with and hard to check; the interviews differ in length and in the topics asked, so the author warns that the picture depends on the question set; the host adds that topics left unasked bias any comparison. Answer types: full, partial, another question, topic change, attack on the question, not allowed to answer. | 2026-11-21 |

## Problem catalogue

One row per problem. "Ours" links to a `docs/BACKLOG.md` item when we already know it.

| # | Problem | Seen in | Ours | Status |
|---|---|---|---|---|
| P1 | Inflated "correct" count: unchecked or unverifiable claims count as true | F (reports unverifiable apart) | BACKLOG 15 | known |
| P2 | Unstable flags: two runs of one video share about half of their flags | C (judge variance) | BACKLOG 2 | known |
| P3 | Fallacy flags run no search, so a reported fact reads as insinuation | D | BACKLOG 17 | known, confirmed by an outside viewer |
| P4 | No external baseline for recall | F (a published set of 67 verdicts on the same debate) | BACKLOG 16 | known; a second reference exists |
| P5 | "Correct" verdicts keep no quote or reason, so they cannot be audited | — | BACKLOG 5 | known |
| P6 | Omission: a true figure with no context is not flagged (reserve growth with no debt, no transfers) | A, F | none | new |
| P7 | Links between answers of different moments, and backstory inconsistencies, are found less often than by a person | B | partly: the judge keeps self-contradictions | new |
| P8 | A single official source, or an interested party's own count, can decide a verdict | B, F | partly: producer tiers 1–5; "false" needs every credible measure against it, one of them tier 1–3 (`core/factcheck.py`) | partly known |
| P9 | Arguments are missed: a quantitative claim chain (x20), hypotheses, alleged connections | B | none | new |
| P10 | One annotator: more videos scale the volume, not the evidence | C, G; F has two model passes but no full human review; H, the author corrects an LLM draft alone | none | new, flagged twice from outside |
| P11 | One confidence number mixes the likelihood of the claim with the strength of the evidence | C, G | none | new |
| P12 | The audience wants binary verdicts, and reads the same verdict by its prior view | C, E | none | new |
| P13 | The browser extension is hard to install, so feedback is scarce | D | the web (RFC S1–S7) | being fixed |
| P14 | Moving denominators: one report gives "4 false of 13", "9 of 43" and "19 claims" for the same check | F | none | new, a lesson for our cards and web |
| P15 | The side that attacks or cites more figures gets more false verdicts, so raw counts read as a scoreboard | F | BACKLOG 3 and 17 | partly known |
| P16 | Speaker attribution is weaker in overlapping speech (88 % of words verified) | F | BACKLOG 7 | partly known |
| P17 | The same claim gets different values by base period or definition (752,000 against 719,602 homes) | F | none | new |
| P18 | A false attribution: a quote given to a third party that no source records | F | none | new |
| P19 | Speakers are compared across different question sets, lengths and topics left unasked, so the comparison is not fair | H | none | new |
| P20 | The verdict depends on the exact wording, and third-party summaries drift ("does not know them" becomes "little relation") | H | covered by the rule "a flag quotes the exact utterance" | known |
| P21 | Calibration bars come from one interview, so at the edge (insinuation with a public basis, a true figure with a missing context) the rule does not decide | G | BACKLOG 17 is one such case | new |
| P22 | A question can carry a premise (a loaded question) and no check looks at the premise | H, D | none | new |

## Ideas

One row per idea. Evidence says what we know, not what the source claims.

| # | Idea | Solves | Source | Cost | Evidence it works |
|---|---|---|---|---|---|
| I1 | Two-axis verdict (ICD 203): likelihood on a bounded verbal scale, and confidence from the evidence base (independent sources, corroboration, gaps) | P11, P12 | C | Contract change; slice | Standard in intelligence analysis. Not tested on our flags |
| I2 | Independent judges on the same clips, with an agreement score | P10 | C | Annotation time of other people; no model cost | None here yet |
| I3 | 5 runs of the judge on one clip, and the variance of its verdicts | P2, P10 | C | About 5 judge runs per clip | None here yet |
| I4 | Omission pass: for a true claim, ask what a fair reader would need to add and flag it as context. Uses the checklist of I11 | P6 | A, F | One more model call per true claim; cap it | None here yet. Risk: more small flags, see the flag materiality rule. Test case: the pension reserve figure, which F rated misleading |
| I5 | Ledger of each speaker's claims over the whole video, compared across moments | P7 | B | Memory per video; no search | Partly built: the judge keeps self-contradictions |
| I6 | Source tier on each source (primary, official, press, advocacy, party's own count) and a visible note when one source alone backs a verdict | P8 | B, F | A field per source | Partly built: the model gives each measure of an inaccuracy flag a tier 1–5. Missing: a fixed domain table in place of the model's choice, tiers on the other flag types, and a visible note in the viewer |
| I7 | Route an insinuation about a concrete fact through the claim search; output context or a lower severity | P3 | D | One search per such flag | The owner's own check on one case |
| I8 | Argument pass: split a quantitative or causal argument into premises and check each one | P9 | B | One model call per argument; cap it | None here yet |
| I9 | Publish approved videos on the web and collect marks from many people | P13, P10 | C, D | RFC S1–S7 | In progress |
| I10 | Five-level verdict scale (true, true with nuance, misleading, false, unverifiable). Count only "true" as correct and show "unverifiable" apart | P1, P12 | F | The contract change of BACKLOG 15; slice | Used by F on 67 figures. Not tested here |
| I11 | Checklist of nuance patterns, each seen in F's verdicts: nominal against real; total against increase; peak year against base year; forecast against result; promise against delivered; a different measure (rebates against releases); a portal or party count in place of the official one; who decided (a former government, the courts, the regions) | P6, P17 | F | Prompt text only | Each pattern is a real case in F. Not tested here |
| I12 | Per verdict: at least 2 sources, official first. A near-exact figure is "true with nuance" and says the nuance. State the period and definition | P8, P17 | F | Check whether the search role enforces it | Unknown; read the code first |
| I13 | Rates, not counts, to compare speakers: false verdicts per figure checked and per minute spoken, always with N. Split also by question type (premise against, neutral), and refuse a comparison when the question sets differ widely | P15 | F | None; a formula | None here yet |
| I14 | One table feeds every number of a card or page, and no text states a number by hand | P14 | F | Low; part of the web | None needed |
| I15 | Two independent model passes on the classification, with kappa per category. Model-to-model agreement checks stability, not truth, so it does not replace I2 | P2, P10 | F | One more pass | F reports 0.72–1.0. Not tested here |
| I16 | A reliability tag on speaker attribution; a quote from overlapping speech carries a caution | P16 | F | A field on the flag | None here yet |
| I17 | A cross-video ledger: compare what one speaker says in different videos | P7 | F | Needs several videos of one speaker | None here yet |
| I18 | Quote-attribution check: search the exact quote given to a third party and say "no record" when none exists | P18 | F | One search per such quote | One real case in F. Not tested here |
| I19 | Use F's published verdict set on the 19 November debate as a second external reference beside the three media of BACKLOG 16. Keep only ids and links in the repo, and run it in `evals/` | P4 | F | Reading time; no paid run if `--no-run` | None yet |
| I20 | Edge-case suite: collect the borderline cases (insinuation with a public basis, true figure with missing context, small slip) from several speakers and formats, label each with at least 2 independent annotators, and test every rule on that suite, not on the average | P21, P10 | G | Annotation time; no model cost beyond the runs | None here yet. Both outside analysts ask for it |
| I21 | Premise check: extract the claim that a question presupposes, run it through the claim search, and label the question as context when a public basis exists | P22, P3 | H, D | One search per loaded question | The owner's own check on one case. Extends I7 |
| I22 | Answer taxonomy with six types (full, partial, another question, topic change, attack on the question, not allowed to answer) in place of one "dodged" count | P15 | H | A schema change on the dodged-question flag | In use by H. Not tested here. Touches BACKLOG 14 |

## Not to copy

| Practice in E, F, H | Why it does not fit |
|---|---|
| Ranking people on clinical traits (a "psychopathy" score from behaviours such as flattery or a neutral voice) | It scores the person, and our domain rule says a flag is a signal on an utterance. The proxies are weak |
| Facial emotion or lie cues | Weak evidence. F itself labels them "suggested" |
| Per-speaker tallies read as a winner | See P15. Keep rates and N, never a scoreboard |
| Reading "answers with exact figures" as "says the truth" | An exact figure is easier to check, not truer. Keep the answer axis and the truth axis apart |

## Priorities

Rank after each new source. Rule: an idea ranks high if it solves a known problem, costs little and can be measured in `evals/`.

| Rank | Idea | Why | Route |
|---|---|---|---|
| 1 | I7 | A known bug, confirmed from outside; small cost | slice (BACKLOG 17) |
| 2 | I10 | The concrete form of BACKLOG 15, and a real tool uses it | slice (contract change) |
| 3 | I13 and I14 | Zero model cost; stop the scoreboard reading and the moving counts before the web goes public | inline (with BACKLOG 3) |
| 4 | I20, I2, I3, I19 | Two outside analysts (C, G) ask for the same thing: several annotators, variance between runs, calibration beyond one interview. The edge-case suite (I20) is what makes a rule "citable". Without it no later gain is real | evals |
| 5 | I21 and I22 | I21 extends I7 with the premise of a loaded question; I22 is a schema change on a flag we already have | slice with I7 and BACKLOG 14 |
| 6 | I11 then I4 | The owner's own example (A). The checklist is cheap, but the added flags are noise until rank 4 exists | slice after rank 4 |
| 7 | I1 | Adds the evidence axis on top of I10, and answers the self-reported confidence problem (C, G) | slice after I10 |
| 8 | I16, I12, I18, I5 and I17, I15 | Smaller or needs a code read first | inline or slice |
| 9 | I6, I8 | Low proof | explore first |
