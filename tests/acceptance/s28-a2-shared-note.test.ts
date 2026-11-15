// S28 A2 (extension part) · A second viewer gets the shared flags at once and for free
//
// Story: The collector holds a Spanish analysis of a video with 2 flags. A second tester with a Spanish browser opens
// that video: the 2 flags show at once, with no LLM reading, no "Analizar este vídeo" button and the note "Análisis
// compartido · gratis" ("Shared analysis · free" in English); the helper keeps the file with `"source": "shared"`. A
// tester with an English browser opens the same video, gets no shared flags and sees "Analyze this video".
//
// Setup: a jsdom watch page with a player and a video, fake timers, the browser language set per case, and a stub
// `chrome` whose service worker answers the first poll with a shared flag file (or "no flag file" for the English
// viewer) and records each message. The content script runs as on YouTube. Then the real service worker gets a poll
// with a language while a stub `fetch` records the request address. The download is checked in
// test_s28_a2_shared_flags_at_once.py.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

const flag = (id: string, t: number, type: string, label: string, quote: string) => ({
  id, t, speaker: "Invitado", quote, type, label, reason: "Motivo inventado.", confidence: 0.9, related: null,
  sources: [], note: null, on_player: true,
});
const SHARED = {
  video_id: "abc123", status: "done", published_at: "2026-11-10", lang: "es", spoken: "es", source: "shared",
  flags: [flag("ad_hominem-3.0", 3, "fallacy", "ad_hominem", "mi rival es un mentiroso"),
    flag("straw_man-9.0", 9, "fallacy", "straw_man", "ustedes quieren cerrar todas las empresas")],
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });
});

async function open(language: "es-ES" | "en-US", known: object | null) {
  vi.useFakeTimers();
  Object.defineProperty(navigator, "language", { value: language, configurable: true });
  const sendMessage = vi.fn(async (req: any) => {
    if (req.kind === "flags") return { ok: true, data: known };
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
  await vi.advanceTimersByTimeAsync(1000);
  // The player fires timeupdate while it plays; the panel redraws on it.
  document.querySelector("video")!.dispatchEvent(new Event("timeupdate"));
  const buttons = () => [...document.querySelectorAll("button")].map((b) => b.textContent!);
  const messages = () => sendMessage.mock.calls.map(([req]) => req);
  return { buttons, messages };
}

describe("S28 A2 · the shared flags show at once with a note", () => {
  // Case 1 · a Spanish browser, a shared file → the note, no analyse button, the 2 flags in the panel tab
  it("Case 1 · Spanish browser → \"Análisis compartido · gratis\", no \"Analizar este vídeo\", \"Avisos (2)\"", async () => {
    const { buttons, messages } = await open("es-ES", SHARED);
    expect(document.body.textContent).toContain("Análisis compartido · gratis");
    expect(buttons()).not.toContain("Analizar este vídeo");
    expect(document.querySelector(".fc-panel-tab")!.textContent).toBe("Avisos (2)");
    expect(messages().some((req: any) => req.kind === "analyze")).toBe(false);
    vi.clearAllTimers();
  });

  // Case 2 · the first poll → it carries the interface language
  it("Case 2 · the poll carries lang \"es\"", async () => {
    const { messages } = await open("es-ES", SHARED);
    expect(messages().find((req: any) => req.kind === "flags")).toMatchObject({ kind: "flags", videoId: "abc123", lang: "es" });
    vi.clearAllTimers();
  });

  // Case 3 · an English browser, a shared file → the note in English
  it("Case 3 · English browser → \"Shared analysis · free\"", async () => {
    await open("en-US", { ...SHARED, lang: "en" });
    expect(document.body.textContent).toContain("Shared analysis · free");
    vi.clearAllTimers();
  });

  // Case 4 · an English browser, no shared file in English → the analyse button and no note
  it("Case 4 · English browser, nothing shared → \"Analyze this video\" and no note", async () => {
    const { buttons } = await open("en-US", null);
    expect(buttons()).toContain("Analyze this video");
    expect(document.body.textContent).not.toContain("Shared analysis");
    vi.clearAllTimers();
  });

  // Case 5 · a local file the person analysed → no note
  it("Case 5 · a file analysed on this laptop → no note", async () => {
    const { source: _, ...own } = SHARED;
    await open("es-ES", own);
    expect(document.body.textContent).not.toContain("Análisis compartido");
    vi.clearAllTimers();
  });

  // Case 6 · the service worker → the poll request carries at and lang
  it("Case 6 · the service worker asks /videos/<id>?at=12&lang=en", async () => {
    let listener: any;
    const urls: string[] = [];
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } } });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return { ok: true, json: async () => ({}) }; }));
    vi.resetModules();
    await import("../../src/extension/src/sw");
    await new Promise((done) => listener({ kind: "flags", videoId: "abc123", at: 12.7, lang: "en" }, {}, done));
    expect(urls).toEqual(["http://127.0.0.1:8765/videos/abc123?at=12&lang=en"]);
  });
});
