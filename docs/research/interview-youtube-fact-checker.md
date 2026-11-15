# Interview: youtube-fact-checker

**Date**: 2026-11-13 · **Questions**: 12

## Sources

- The chat of 2026-11-13
- `docs/RFC.md` (blank template)
- `docs/ARCHITECTURE.md` (blank template)

## Decided

| Question | Answer | Source | Date |
|---|---|---|---|
| Recorded videos or live streams first? | Recorded videos first. Live streams later | person | 2026-11-13 |
| Which flag types go in the first version? | Internal contradiction, inaccurate claim (fact check), fallacy or bias | person | 2026-11-13 |
| Which language first? | Spanish. Other languages later | person | 2026-11-13 |
| Which LLM access in phase 1? | The person's own Claude subscription, through a local helper on the laptop that the extension connects to | person | 2026-11-13 |
| Where do flags show on youtube.com? | On top of the YouTube player, through the browser extension | person | 2026-11-13 |
| Who uses phase 1? | Only the person, on their own laptop with their own Claude subscription | person | 2026-11-13 |
| How is each utterance attributed to a speaker? | Start with the LLM inferring the speaker from context, and hide a contradiction flag when the speaker is uncertain. Switch to local voice diarization (pyannote) only if tests show attribution errors | person | 2026-11-13 |
| Which flags show on top of the video? | Two levels: confidence ≥ 80% shows on the player; 50–79% goes to a collapsed side panel and the progress-bar marks; below 50% shows nowhere. Tune 80% with data later | accepted recommendation | 2026-11-13 |
| Which sources count for a fact check? | Official and primary sources first (INE, Eurostat, BOE, Banco de España, ministries, OECD, wire agencies such as EFE and Reuters, accredited fact-checkers such as Maldita, Newtral, EFE Verifica). Other sources lower the confidence, so the flag usually goes to the side panel. Each flag shows its source and date | accepted recommendation | 2026-11-13 |
| Against data of which date is a claim checked? | Against the data available on the video's publish date (from YouTube). If the data changed since, the claim is not flagged as false; the flag adds a note with the updated value | accepted recommendation | 2026-11-13 |
| What is the budget per video? | Phase 1: no extra cost; hard stop at 60 Claude tool calls per video-hour, then the run stops and reports it; if the API is ever used, hard stop at €5 per video. Phase 2: target ≤ €3 per video-hour, paid once per video through the shared cache | accepted recommendation | 2026-11-13 |
| How is flag quality measured? | A synthetic golden dataset: Spanish dialogues with planted contradictions, inaccurate claims and fallacies, plus the expected flags. Generated with stronger models than the pipeline uses, and reviewed by the person | person | 2026-11-13 |
| Which score on the golden dataset makes phase 1 good enough? | Precision ≥ 80% for flags shown on the player; recall ≥ 50% of the planted errors | accepted recommendation | 2026-11-13 |
| Are published fact-checks consulted before a web search? | Yes, as the first step: query the Google Fact Check Tools API (ClaimReview data from Maldita, Newtral, EFE Verifica and others). A matching fact-check is cited with high confidence. Without a match, fall back to web search on official sources | accepted recommendation | 2026-11-13 |
| Which language for the local helper and the extension? | Python for the helper (yt-dlp, Whisper, pyannote are Python). TypeScript for the Chrome extension | accepted recommendation | 2026-11-13 |
| What does the first RFC cover? | The target is phase 1 + phase 2, written in `docs/TARGET.md`. The first RFC builds phase 1 as step 1 toward it | person | 2026-11-13 |
| Which fallacies are in scope for S1? | A closed list of 8: ad hominem, tu quoque ("y tú más"), false dilemma, straw man (only when the distorted statement is in the same video), evasion (red herring: the answer dodges the question), false cause, hasty generalization, vague authority. Later: cherry picking, false equivalence, slippery slope. Out: appeal to emotion, loaded language, cognitive biases | person | 2026-11-13 |
| What happens to a fallacy outside the list? | It is not shown; it is written to a local log for the person to review, so new types enter with data | accepted recommendation | 2026-11-13 |
| Which speakers are analysed? | All speakers alike, the interviewer included | accepted recommendation | 2026-11-13 |
| Which test doubles, since no system has a sandbox? | Cleaned responses of read-only production calls for Claude Code and the Fact Check Tools API. For YouTube, never a real transcript: a `json3` file with the same structure and invented sentences | accepted recommendation | 2026-11-13 |
| How does the analysis keep ahead of playback? | Start at the playback second (sent by the extension), analyse forward, then the earlier part; first chunk 30 s, then 2 min; up to 3 Claude calls at once; start when the page loads; log the lead per chunk | accepted recommendation | 2026-11-13 |
| How is the pipeline shaped for live streams later? | As a stream: each chunk with the text before it as context. Live mode changes only the text source and the LLM provider | accepted recommendation | 2026-11-13 |
| What enters scope after reading a real interview? | Fact checks first (moved to S2); unanswered questions as their own feature, with `evasion` leaving the fallacy list; contradictions with the speaker's record (was a non-goal); context cards; new rhetoric labels only after measurement | accepted recommendation | 2026-11-14 |
| Where does a source date come from? | The date of a published fact-check when one matches; otherwise the source page is fetched for its date | accepted recommendation | 2026-11-14 |
| Are official figures the ground truth? | No. A documented controversy on a metric is of vital importance: a claim one credible measure supports is "disputed", not "false"; the card shows each measure and the controversy; sources weigh by independence. Built as S6, before unanswered questions (docs/research/official-data-controversies.md) | person | 2026-11-14 |
| How are false positives found on real videos? | Show many flags for now (bars from the golden dataset) and add "correct" / "unfair" buttons on each card; the marks, kept locally, give the real precision in the eval. Built as S4 (chat) | person | 2026-11-14 |
| How is the speaker attributed now? | Changed: 4 of 6 unfair marks on a real interview came from a wrong speaker. Voices are separated from the audio; the LLM names them from the whole interview; a stronger model analyses with a longer context; quotes and rhetorical self-questions are not claims. Built as S5 | person | 2026-11-14 |
| Which misleading patterns must be caught beyond false figures? | Four, from the 112-minute interview: a wider definition than the one asked ("entregadas o en proceso" = mobilised, not delivered), a plan told as the present (Casa 47), a promise and its status (184,000 homes), and an answer with another figure than the one asked. Each claim keeps its question, metric and tense (S5); verdicts in S6; dodged-with-figures in S7; promises in S9 | person | 2026-11-14 |
| Google Fact Check Tools API: how do we log in? | An API key from a Google Cloud project that the person creates (an S0 item). The person stores the key from their own terminal, never in chat | person | 2026-11-13 |

## Open

| # | Question | Blocks | Owner |
|---|---|---|---|
| 1 | Google Fact Check Tools API: which endpoint and parameters, where the contract is written, quotas and errors? | Fact-check step of phase 1 | team |
| 2 | YouTube through yt-dlp: which captions and metadata (publish date) can we fetch, what fails (missing captions, blocks, rate limits), and how do we fall back to audio + local Whisper? | Transcript step of phase 1 | team |
| 3 | Claude Code (`claude -p`) with the subscription: structured JSON output, web search inside a headless run, usage limits per hour, and errors when a limit is hit? | Analysis step of phase 1 | team |
| 4 | Web search for fact checks: does the search inside `claude -p` let us prefer official domains, and does it return the source date? | Fact-check step of phase 1 | team |
