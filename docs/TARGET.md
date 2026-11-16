# Target: fact-checker

## In one paragraph

A viewer watches a YouTube video and sees, at the exact second, short flags on what is said: a claim that the data contradicts, a speaker who contradicts themselves, a fallacy or a bias. Each flag quotes the words, gives a reason, a confidence and a source. Step 1 runs on each person's own machine (the person and beta testers on macOS or Linux), with their own Claude or ChatGPT subscription or an API key, on recorded videos in Spanish and English. With consent, testers' marks and whole analyses go to the owner's collector; an analysis the owner approves is served free to the next viewer in the same language. Step 2 moves the pipeline to a server, so every video is analysed once for every viewer, and adds a web page and a shareable report next to the extension (chat, docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/research/interview-youtube-fact-checker.md, docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/021-beta-install/spec.md, docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/026-spanish-and-english/spec.md, docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/028-shared-analyses/spec.md, docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/030-ready-to-publish/spec.md).

## Components

| Component | Job | When |
|---|---|---|
| Extension | Shows flags on the YouTube player at their second, in Spanish or English | today |
| Helper | Local server on each person's machine: runs the pipeline, serves flags | today |
| Pipeline | Transcript in, flags out. No I/O of its own | today |
| Transcript source | Captions and publish date of a video; audio and local Whisper when captions are missing | today |
| LLM provider | One port; adapters for Claude Code, Codex CLI, the Anthropic API, OpenAI-compatible APIs and any chat API, one per role | today |
| Fact-check source | Published fact-checks first, then web search | today |
| Golden dataset | Synthetic dialogues with expected flags; scores precision and recall | today |
| Install | One script and `setup`/`doctor` on macOS and Linux | today |
| Collector | The owner's Cloudflare Worker + D1: testers' marks and shared analyses, served after the owner approves them | today |
| Backend | Runs the pipeline on a server; analyses each video once for every viewer | Step 2 |
| Web player page | Embedded player with the flags beside it, each lit at its second; works on mobile; the profile card links here (2026-11-16, chat) | Step 2 |
| Report page | One shareable page per analysed video | Step 2 |
| Caption upload | The extension sends the captions that the player loads to the backend | Step 2 |
| Live mode | Streaming transcription and an API with streaming; fallacy flags within about 5–10 s of the utterance | Step 3 |

## Steps

| Step | Name | Delivers | Depends on | Status |
|---|---|---|---|---|
| Step 1 | Personal fact-checker for recorded YouTube videos | The person and beta testers see flags on youtube.com for any recorded Spanish or English video; an approved analysis is shared with later viewers | none | done ([001](archive/001-personal-fact-checker-for-recorded-youtube-videos/RFC.md)) |
| Step 2 | Shared fact-checker | Anyone sees flags in the extension, on a web page or in a shared report; each video is analysed once, on a server | Step 1 | planned |
| Step 3 | Live streams | Flags on live streams within seconds | Step 2 | planned |

## Seams to keep open

- The pipeline takes a stream of chunks, each with the text before it as context, and returns flags, with no I/O. Step 2 runs it on a server unchanged; Step 3 feeds it a live transcript.
- The LLM provider is a port. A new provider is one adapter file plus a `provider` value.
- The extension reads flags from one HTTP address. Step 2 changes only the address.
- The flag file is a public contract. The collector, the web page and the report page of Step 2 read the same format.

## Intended decisions

| Decision | Why | Revisit when |
|---|---|---|
| Recorded videos before live streams | No latency pressure, cheaper, testable (chat) | Step 1 meets its precision target |
| Flags over the player only in the extension; beside the player on the web page | YouTube API policies forbid covering an embedded player (chat) | The policy changes |
| Each person pays their own readings in Step 1; the owner pays only the collector, on the free plan (docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/021-beta-install/spec.md, docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/024-shared-feedback/spec.md) | No cost to the owner per video | A tester cannot afford a video, or the collector leaves the free plan |
| A shared analysis per video and language, served only after the owner approves it (docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/028-shared-analyses/spec.md, docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/specs/030-ready-to-publish/spec.md) | Cost is paid once per video, not per viewer; nobody can plant flags | Step 2 analyses on a server |
| Phase 2 budget ≤ €3 per video-hour (docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/research/interview-youtube-fact-checker.md) | Keeps a free tier viable | Measured cost of Step 1 differs by 2x |
