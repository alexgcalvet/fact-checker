# S38 Install with no terminal

**Implements**: [ARCHITECTURE · Hosting (Helper process, Install)](../../ARCHITECTURE.md#hosting), [Contracts · Helper API](../../ARCHITECTURE.md#contracts)
**Approval**: agent · approved 2026-11-15

## Summary

A field test on a second Mac failed: Codex runs its commands in a sandbox, so the person had to type commands in Terminal, and another program on the helper's port made every analysis vanish while the health check said all was fine. After this slice, the helper proves who it is and moves to a free port by itself, setup replaces an old helper, and the check tells an agent in a sandbox to run outside it. The only manual step left is loading the extension in Chrome.

## Acceptance

- [X] A1 · The check knows the helper by its answer
  - **Story:** The person's agent runs `fact-checker doctor` while another program answers on port 8765. The helper line says "another program holds port 8765" and is not ok. With the real helper running and its home writable, it says "running on port 8766" (the port it found) and is ok.
  - **Test:** `test_s38_a1_doctor_knows_helper.py`
- [X] A2 · A taken port moves the helper and the extension follows
  - **Story:** Another program holds port 8765. The helper starts at login on 8766 instead, and on YouTube the "Analizar este vídeo" button starts an analysis whose flag file appears in the helper home. With all five ports 8765–8769 taken, the helper log says so in one line and the helper stops; it does not restart in a loop.
  - **Test:** `test_s38_a2_port_fallback.py`, `s38-a2-extension-finds-helper.test.ts`
- [X] A3 · Setup replaces an old helper
  - **Story:** A fact-checker helper started by hand (for example by an agent) holds port 8765. The person's agent runs `fact-checker setup`. The old helper stops, the login helper answers on 8765, and doctor's helper line is ok.
  - **Test:** `test_s38_a3_setup_replaces_helper.py`
- [X] A4 · A sandboxed check says to step out
  - **Story:** Codex runs `fact-checker doctor --json` inside its sandbox, where a local connection fails with "Operation not permitted". The helper check is not ok, says "blocked by the agent's sandbox", and its fix says to run `fact-checker setup` and `doctor` outside the sandbox with the person's approval.
  - **Test:** `test_s38_a4_doctor_sandbox.py`

## Files

| Path | Change |
|------|--------|
| `src/helper/fact_checker/server.py` | edit — `GET /health` `{app, version, pid, home, writable}`; serve on the first free port of 8765–8769, one log line and exit 0 when none |
| `src/helper/fact_checker/cli.py` | edit — `serve` without `--port` uses the range |
| `src/helper/fact_checker/install.py` | edit — doctor finds the helper by `/health` over the range, tells a foreign program and a sandbox apart; setup stops fact-checker helpers in the range before it starts the login helper, then waits for `/health` |
| `src/extension/src/sw.ts` | edit — find the helper over 8765–8769 by `/health`, keep the port, look again when a call fails |
| `src/helper/fact_checker/extension/` | edit — rebuilt extension |
| `INSTALL-AGENT.md` | edit — the agent runs every step itself; a sandboxed command runs again outside the sandbox with the person's approval; never `fact-checker serve` |
| `README.md` | edit — a first line that sends an agent with only the URL to `INSTALL-AGENT.md` |
| `docs/ARCHITECTURE.md`, `docs/RFC.md` | edit — `/health`, the port range, S38 row |

## Tasks

- [X] T001 `/health` and the port range in `server.py` and `cli.py` → A2
- [X] T002 Helper found by `/health`, foreign program and sandbox told apart in `install.py` (doctor) → A1, A4
- [X] T003 Setup stops fact-checker helpers in the range and waits for `/health` in `install.py` → A3
- [X] T004 Find the helper over the range in `src/extension/src/sw.ts`, rebuild the shipped extension → A2
- [X] T005 [P] Agent steps and the URL-only line in `INSTALL-AGENT.md` and `README.md` → FR-001
- [X] T006 [P] `/health`, port range and S38 row in `docs/ARCHITECTURE.md` and `docs/RFC.md` → A1

## Requirements

- [X] FR-001 — `INSTALL-AGENT.md` MUST tell the agent to run every command itself, to re-run a command that fails with "Operation not permitted" outside its sandbox after the person approves, and never to start `fact-checker serve`; the README MUST say on its first lines that an agent given only the repo URL follows `INSTALL-AGENT.md`.

## Decisions

- **Five fixed ports, found by `/health`** — the extension needs no settings and no native messaging; beat a port file (the extension cannot read disk) and a random port.
- **Setup stops only processes whose `/health` says fact-checker with the same home** — never kills another program or another install; beat freeing 8765 by force.
- **Claude stays first when both are logged in** (default) — the field test worked on Claude; choosing the installing agent is out of scope.

## Out of scope

- Loading the extension without the 3 clicks: needs the Chrome Web Store, a later row.
- `setup --provider` to pick Codex when Claude is also logged in.
- Windows.
