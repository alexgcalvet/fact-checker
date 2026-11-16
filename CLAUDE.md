# fact-checker

A real-time conversation analyst: it listens to a live conversation and flags contradictions, biases, logical fallacies and inaccurate claims as they happen. For anyone who wants a second, critical ear in a debate, meeting or interview. Phase: idea, before the first RFC.

## Rules
<!-- mini-spec:rules:start -->
- **All documents and code artifacts are written in English**, whatever language the conversation is in. This covers docs, code comments, file names, commit messages, branch names, and pull request titles, descriptions and review comments. Chat replies can follow the user's language.
- Never read or paste secrets (credentials, tokens, session cookies, raw captures). Sanitize the data first and read only the sanitized output.
- Spend paid or rate-limited external services (APIs, LLM calls, MCP tools) purposefully.
- **Pick the route of each change first.** `/mini-spec` picks it before it writes anything:
  - **Inline**: the work fits one session. It adds no component and changes no contract in `docs/ARCHITECTURE.md`. No decision is left that another person could make differently. Fixes and small changes go here, also when a user sees them. Write no spec. If a deterministic test fits, write a failing test first.
  - **Slice**: a decision must be written down (a new capability with choices), the work spans more than one session, or a contract changes. Use `/mini-spec` to write a spec, then `/mini-implement` to build it.
  - **RFC**: several slices or a new component. Use `/rfc` first.
- **`docs/RFC.md` and `docs/ARCHITECTURE.md` are the source of truth.** Explore in chat and the explore page, then use `/rfc` to draft them (draft shown first, written only once approved). If a change contradicts them, update them in the same change, or run `/rfc sync`.
<!-- mini-spec:rules:end -->

## Code
<!-- mini-spec:code:start -->
- **The best code is no code.** Before writing anything, check whether a library, a platform feature or existing code already does it. Write the least code that solves the problem cleanly.
- **No AI-generated slop.** That means:
  - no defensive checks for cases that cannot happen
  - no wrappers that only rename things
  - no config for things that never change
  - no comments that restate the code
  - no speculative features
- **Tests earn their place.** Test behaviour that could break and would matter: parsing, scoring, business rules. Do not write tests that mirror the implementation or pad coverage.
  - Attach tests at the seams of a component: integration tests through its public interface. Write unit tests only for pure logic. Use fakes only for external systems.
  - Never edit an approved acceptance test. If one seems wrong, ask the person when the slice says `Approval: person`; with `Approval: agent`, the agent re-approves it after a fresh test review and reports the change.
- **Efficient by default.** Pick the simple, efficient approach first. Do not optimise what has not been measured.
- **Modular, built to evolve.** Think about where the repo is going. Build small modules with one job and clear interfaces, so that parts can be swapped or extended without touching the rest. Adding an adapter, a metric or a provider should be one new file, not an edit across the codebase. Modularity serves iteration, so do not add layers or abstractions before a second use exists.
<!-- mini-spec:code:end -->
- **Tests live by part, not by slice.** A slice's acceptance tests stay in `tests/acceptance/`, untouched, while the slice is open. When its last item is done, close it with `/mini-implement <id> promote`. Its tests then move into the suite of their part, where they can be merged or removed. Keep each `S<n> A<n> · <title>` header as a comment on the test that keeps it.
- **A run on a real interview or a paid model is a measurement, not a test.** Put it in `evals/` with one line in `evals/README.md`. CI never runs it.

## Documentation
<!-- mini-spec:documentation:start -->
- **Schematic, for humans.** Write short sections, tables and bullet points, not long prose. Lead with the conclusion. `/explore` pages are the exception: each tab explains its part in short, full sentences.
- **Show, don't describe.** Use a diagram (Mermaid) for any flow, architecture or relationship that takes more than a few sentences to explain.
- **Easy to scan.** A reader should get the point from the headings and tables alone. Cut anything that does not help a decision or an implementation.
- **Procedures follow STE-lite** (a light ASD-STE100), for steps, runbooks, checklists and skills. Reasoning sections (RFC, Alternatives, Decisions) and the prose of `/explore` pages are exempt.
  - One instruction per sentence, at most 20 words. Use the active voice and the present tense.
  - Use one term for one concept, and never a synonym. Write "tool call" every time, never "call" or "invocation".
  - Make conditions explicit: "If X, do Y." Do not hide them in a clause.
<!-- mini-spec:documentation:end -->

## Context
<!-- mini-spec:context:start -->
- This file loads in every session. Write here only rules that the code does not show.
- To find code, read the Components table in `docs/ARCHITECTURE.md`. Its Path column says where each component lives.
- A folder `CLAUDE.md` holds only rules of that module. Add a rule only if the code does not show it, an agent broke it once, and it applies to that folder only. Never list functions or files there.
- For a search across many files, use the Explore subagent and keep only its conclusion.
- Save research from the conversation as `docs/research/<topic>.md`. Start the file with its sources. Never write a secret in it.
<!-- mini-spec:context:end -->

## Domain
- **Every flag cites its evidence.** A flag quotes the exact utterance, names its type (contradiction, bias, fallacy, inaccuracy) and gives a short reason. A factual flag also names its source.
- **A flag is a signal, not a verdict.** Show a confidence on each flag. Never call a speaker a liar or attack the person.
- **False positives cost more than misses.** A noisy live feed gets ignored. Tune for precision first.
- **Latency is a requirement.** A flag that arrives after the topic has moved on has little value. Measure the time from utterance to flag.
- **Conversations are personal data.** Never commit real recordings or transcripts. Use synthetic or consented samples in `tests/` and research.

## Layout

<Map each top-level directory to its purpose, one line each. Note any published artifact URL next to the file it belongs to, and say to republish to that same URL when the file changes.>

- `docs/`: documentation (`RFC.md`, `ARCHITECTURE.md`, `index.html`, the living page of the project that `/explore` updates and `/rfc` reads, and `specs/` for mini-specs, with `specs/index.html`, the spec page that `/mini-spec` and `/mini-implement` update)
- `docs/research/`: research reports, one per topic, each starting with its sources. `/explore` and `/rfc` read them, and `/rfc close` archives the ones that the RFC cites
- `docs/archive/`: finished RFCs and slices, one numbered folder each (`/rfc close` creates them), listed in `docs/archive/README.md`. Read that index to find one. Do not read or edit the archive otherwise
- `src/`: source code
- `tests/`: tests, one suite per part. `tests/helper/test_<part>.py`, `tests/extension/<screen>.test.ts`, `tests/collector/<route>.test.ts`, `tests/contracts/` (one per external system), `tests/support/` (shared fakes and helpers, no test), `tests/fakes/` (recorded answers), `tests/golden/`. `tests/acceptance/` holds only the acceptance tests of the open slices
- `evals/`: measurements on real interviews or paid models, one line each in `evals/README.md`; CI never runs them
