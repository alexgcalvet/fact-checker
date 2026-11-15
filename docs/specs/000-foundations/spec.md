# S0 Foundations

**Implements**: [RFC › S0 checklist](../../RFC.md#s0-checklist), [ARCHITECTURE › External systems](../../ARCHITECTURE.md#external-systems)
**Approval**: person · approved 2026-11-13

## Summary

Before any code exists, the laptop gets the tools that Step 1 needs, and each outside system is tried once by hand with a real result. What each try shows is written down, so the external contracts in the architecture move from unknown to confirmed and the first real slice is no longer blocked.

## Acceptance

- [X] A1 · Tools are installed
  - **Story:** The person opens a terminal and asks each tool for its version. They see a version for Python (3.12 or later), Node.js, yt-dlp and Claude Code, and no "command not found".
  - **Test:** `check: python3 -c 'import sys; assert sys.version_info >= (3, 12)' && node --version && yt-dlp --version && claude --version`
- [X] A2 · YouTube gives Spanish captions and the publish date
  - **Story:** The person picks one public Spanish interview on YouTube and asks yt-dlp for its captions and date, without downloading the video. They see a caption file with timestamps in a temporary folder outside the repo, and a date such as 20261113.
  - **Edge case:** WHEN the video has only automatic captions THEN they count, and the research file says so.
  - **Test:** `check: yt-dlp --no-simulate --skip-download --write-subs --write-auto-subs --sub-langs es --sub-format json3 --print upload_date -o "$TMPDIR/s0/%(id)s" "$S0_VIDEO_URL" && ls "$TMPDIR"/s0/*.es.json3`
- [X] A3 · Claude Code answers in JSON from a script
  - **Story:** The person runs Claude Code headless with a short Spanish sentence and asks for a JSON answer that names a fallacy. They see valid JSON with the result, run on their own subscription.
  - **Test:** `check: claude -p 'Return only JSON {"fallacy": string|null} for: "Lo dice él, que es un corrupto, así que es mentira."' --output-format json | python3 -c 'import json,sys; json.load(sys.stdin)'`
- [X] A4 · The Fact Check Tools API returns a published fact-check
  - **Story:** The person stores their Google API key in their own terminal, then searches for a well-known Spanish claim. They see at least one fact-check with a publisher such as Maldita or Newtral and a verdict.
  - **Test:** `check: curl -sf -H "X-goog-api-key: $FACT_CHECK_API_KEY" "https://factchecktools.googleapis.com/v1alpha1/claims:search?languageCode=es&query=paro%20juvenil" | python3 -c 'import json,sys; assert json.load(sys.stdin).get("claims")'`

## Files

| Path | Change |
|------|--------|
| `docs/research/external-contracts.md` | new — sources first, then per system: what we call, auth, contract source, limits, errors, a sanitized sample |
| `docs/ARCHITECTURE.md` | edit — External systems rows set to `confirmed` with their contract source, through `/rfc sync` |
| `docs/RFC.md` | edit — Open questions 1–4 move to Resolved, through `/rfc sync` |

## Tasks

- [X] T001 Install yt-dlp and check the versions of every tool → A1
- [X] T002 Try yt-dlp on one public Spanish video; record caption formats, the date field and the failures it reports in `docs/research/external-contracts.md` → A2
- [X] T003 Try `claude -p` with JSON output and a web search; record the output shape, the web search behaviour and the limit errors in `docs/research/external-contracts.md` → A3
- [X] T004 Person creates the Google Cloud key and stores it; try one search; record endpoint, parameters, quotas and errors in `docs/research/external-contracts.md` → A4
- [X] T005 Run `/rfc sync` to confirm the contracts in `docs/ARCHITECTURE.md` and resolve the questions in `docs/RFC.md` → A2, A3, A4

## Requirements

- [X] FR-001 — The research file MUST hold no API key, no account detail and no full transcript; samples are cut to a few lines.

## Decisions

- **The API key lives in `FACT_CHECK_API_KEY` in the gitignored `.env` at the repo root** (person) — the helper reads one variable; git ignores the file.
- **S0 is not blocked by unknown contracts** (default) — confirming them is the job of this slice.

## Out of scope

- Loading the extension in Chrome: S1 creates it.
- The question on which fallacies and biases are in scope: the person answers it before S1.
