# Quality and cost of four reading setups (2026-11-15)

Sources: one 15-minute fragment of a recorded Spanish political interview, analysed four times on the same captions and voice turns, each in its own helper home; the person's marks on the 20 distinct flags of the four runs (10 marked in the player on the live analysis of the same fragment, 10 marked blind from a list). Costs are priced from tokens with `core/prices.py`, web search fees excluded. The run, its scratch homes and the quotes stay outside the repo.

## Setups

| Setup | Code | Parts | Screen | Search | Context |
|---|---|---|---|---|---|
| A0 | before S19 (`161d75b`) | Opus | none | Sonnet | window |
| A1 | S29 code, screen off | Opus | none | Sonnet | conversation |
| B | S29 defaults | Opus | Haiku | Haiku | conversation |
| C | S29 + `parts = "sonnet"` | Sonnet | Haiku | Haiku | conversation |

## Results

19 of the 20 distinct flags were marked correct; 1 was unfair (a host's words given to the guest).

| Setup | Cost | Before the judge: correct / flags | Shown after the judge: correct / flags | Correct flags the judge dropped |
|---|---|---|---|---|
| A0 | 1.56 $ | 9 / 10 | 4 / 4 | 5 |
| A1 | 1.44 $ | 11 / 11 | 4 / 4 | 7 |
| B | 0.99 $ | 10 / 11 | 5 / 6 | 5 |
| C | 0.57 $ | 9 / 9 | 3 / 3 | 6 |

## Findings

- **The judge drops correct flags.** Precision before the judge is already 90–100 %; the judge dropped 5–7 correct flags per setup and never the one unfair flag. It cuts what a person sees from about 10 correct flags to about 4.
- **Quality is about the same across setups; cost is not.** Each setup alone finds 9–11 of the 19 correct flags; the overlap between runs is low, so run-to-run variation is as large as the setup effect at this sample size.
- **S29 holds:** B finds as much as A1 for 31 % less. The screen skipped no part of this dense fragment.
- **Sonnet for parts (C) finds as much as A0 for 63 % less**, and is a candidate default once the judge stops dropping correct flags.
- The one unfair flag is a speaker attribution error, not a reasoning error.

## Limits

One fragment, one language, one marker who agreed with 19 of 20 flags. Repeat on another video and on an English video before changing defaults.
