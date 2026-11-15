// S33 A4 · The side panel lists the speakers and switches a role
//
// Story: The person opens the side panel of the interview. Under the filters it lists "Presentador · Host" and
// "Ana Ruiz · Invitada". A click on the role of the host turns it into Invitada, and the helper is told.
//
// Setup: a jsdom watch page with a player and a video, fake timers, the browser language set per case, and a stub
// `chrome` whose service worker answers with an analysed flag file: one flag, the voices "Presentador" (people: host)
// and "Ana Ruiz (invitada)" (people: guest, person "Ana Ruiz"); it records each message. The content script runs as on
// YouTube and the test opens the side panel. Then the real service worker gets a `role` message while a stub `fetch`
// records each request. What the helper does with it is checked in test_s33_a3_role_set_by_person.py.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

const FILE = {
  video_id: "abc123", published_at: "2026-11-10", status: "done", stop_reason: null, analysed_until: 3720,
  speakers: { SPEAKER_00: "Presentador", SPEAKER_01: "Ana Ruiz (invitada)" },
  people: {
    Presentador: { role: "host", person: "Presentador", spoken_s: 1260, set_by: "llm" },
    "Ana Ruiz (invitada)": { role: "guest", person: "Ana Ruiz", spoken_s: 2460, set_by: "llm" },
  },
  flags: [{ id: "fallacy-30.0", t: 30, speaker: "Presentador", quote: "la oposición no tiene autoridad", type: "fallacy",
    label: "ad_hominem", reason: "Ataca.", confidence: 0.9, related: null, sources: [], note: null, on_player: true }],
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });
});

async function watch(language: "es-ES" | "en-US", file: object = FILE) {
  vi.useFakeTimers();
  Object.defineProperty(navigator, "language", { value: language, configurable: true });
  const sendMessage = vi.fn(async (req: any) => {
    if (req.kind === "flags") return { ok: true, data: structuredClone(file) };
    if (req.kind === "share") return { ok: true, data: { share: true } };
    return { ok: true, data: null };
  });
  vi.stubGlobal("chrome", {
    runtime: { id: "x", sendMessage, onMessage: { addListener: () => {} } },
    storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
  });
  vi.resetModules();
  history.pushState({}, "", "/watch?v=abc123");
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  await import("../../src/extension/src/content");
  await vi.advanceTimersByTimeAsync(0);
  document.querySelector<HTMLElement>(".fc-panel-tab")!.click();
  await vi.advanceTimersByTimeAsync(0);
  const panel = () => document.querySelector<HTMLElement>(".fc-panel")!;
  // The smallest element of the panel whose text is the line.
  const line = (text: string) => [...panel().querySelectorAll<HTMLElement>("*")]
    .filter((el) => el.textContent!.replace(/\s+/g, " ").trim() === text).pop();
  const roles = () => sendMessage.mock.calls.map(([req]) => req).filter((req: any) => req.kind === "role");
  return { panel, line, roles };
}

describe("S33 A4 · the speakers and their roles in the side panel", () => {
  // Case 1 · a file with people → "Presentador · Host" and "Ana Ruiz · Invitada", under the filters
  it("Case 1 · Spanish → \"Presentador · Host\" and \"Ana Ruiz · Invitada\" under the filters", async () => {
    const { panel, line } = await watch("es-ES");
    const host = line("Presentador · Host");
    const guest = line("Ana Ruiz · Invitada");
    expect(host, `no host line in ${panel().textContent}`).toBeDefined();
    expect(guest, `no guest line in ${panel().textContent}`).toBeDefined();
    const filters = panel().querySelector(".fc-flt")!;
    expect(filters.compareDocumentPosition(host!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    vi.clearAllTimers();
  });

  // Case 2 · a click on the host's role → the line says Invitada, and a role message goes to the helper
  it("Case 2 · click \"Host\" → \"Presentador · Invitada\" and {kind: role, name: Presentador, role: guest}", async () => {
    const { line, roles } = await watch("es-ES");
    expect(line("Presentador · Host"), "no host line").toBeDefined();
    const role = [...line("Presentador · Host")!.querySelectorAll("button")].find((b) => b.textContent === "Host");
    expect(role, "the host's role is not a button").toBeDefined();
    role!.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(roles()).toEqual([{ kind: "role", videoId: "abc123", name: "Presentador", role: "guest" }]);
    expect(line("Presentador · Invitada")).toBeDefined();
    expect(line("Presentador · Host")).toBeUndefined();
    vi.clearAllTimers();
  });

  // Case 3 · an English browser → "Presentador · Host" and "Ana Ruiz · Guest"
  it("Case 3 · English → \"Presentador · Host\" and \"Ana Ruiz · Guest\"", async () => {
    const { line } = await watch("en-US");
    expect(line("Presentador · Host")).toBeDefined();
    expect(line("Ana Ruiz · Guest")).toBeDefined();
    vi.clearAllTimers();
  });

  // Case 4 · a file with no people (no voices) → no speakers list
  it("Case 4 · no people in the file → no speakers list", async () => {
    const { panel } = await watch("es-ES", { ...FILE, people: undefined });
    expect(panel().textContent).not.toContain("· Host");
    expect(panel().textContent).not.toContain("· Invitada");
    vi.clearAllTimers();
  });

  // Case 5 · the service worker → POST /videos/abc123/people with {"name", "role"}
  it("Case 5 · the service worker posts {name, role} to /videos/<id>/people", async () => {
    let listener: any;
    const requests: { url: string; method: string; body?: string }[] = [];
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } } });
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      requests.push({ url, method: init?.method ?? "GET", ...(init?.body ? { body: String(init.body) } : {}) });
      return { ok: true, json: async () => ({ ok: true }) };
    }));
    vi.resetModules();
    await import("../../src/extension/src/sw");
    const send = (req: unknown) => new Promise((done) => { if (listener(req, {}, done) !== true) done(undefined); });
    expect(await send({ kind: "role", videoId: "abc123", name: "Presentador", role: "guest" }))
      .toEqual({ ok: true, data: { ok: true } });
    expect(requests).toEqual([{ url: "http://127.0.0.1:8765/videos/abc123/people", method: "POST",
      body: JSON.stringify({ name: "Presentador", role: "guest" }) }]);
  });
});
