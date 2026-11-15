// S26 A3 (extension part) · Reasons come in the viewer's language: the analyze request carries it
//
// Story: A person with a Spanish browser clicks "Analizar este vídeo" on an English interview: the extension sends its
// language with the request. A person with an English browser clicks "Analyze this video" and sends "en". What the
// helper does with it is checked in test_s26_a3_reasons_in_viewer_language.py.
//
// Setup: a jsdom watch page with a player and a video, fake timers, the browser language set per case, and a stub
// `chrome` whose service worker answers "no flag file yet" and records each message. Then the real service worker gets
// an analyze message while a stub `fetch` records the request address.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

async function click(language: string, label: string) {
  vi.useFakeTimers();
  Object.defineProperty(navigator, "language", { value: language, configurable: true });
  const sendMessage = vi.fn(async (_req: any) => ({ ok: true, data: null }));
  vi.stubGlobal("chrome", {
    runtime: { id: "x", sendMessage, onMessage: { addListener: () => {} } },
    storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
  });
  vi.resetModules();
  history.pushState({}, "", "/watch?v=abc123");
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  await import("../../src/extension/src/content");
  await vi.advanceTimersByTimeAsync(0);
  const start = [...document.querySelectorAll("button")].find((b) => b.textContent === label);
  expect(start, `no "${label}" button`).toBeDefined();
  start!.click();
  await vi.advanceTimersByTimeAsync(0);
  vi.clearAllTimers();
  return sendMessage.mock.calls.map(([req]) => req).find((req) => req.kind === "analyze");
}

describe("S26 A3 · the analyze request carries the viewer's language", () => {
  // Case 1 · a Spanish browser clicks "Analizar este vídeo" → the request says lang "es"
  it("Case 1 · Spanish browser → analyze with lang \"es\"", async () => {
    expect(await click("es-ES", "Analizar este vídeo")).toMatchObject({ kind: "analyze", videoId: "abc123", lang: "es" });
  });

  // Case 2 · an English browser clicks "Analyze this video" → the request says lang "en"
  it("Case 2 · English browser → analyze with lang \"en\"", async () => {
    expect(await click("en-US", "Analyze this video")).toMatchObject({ kind: "analyze", videoId: "abc123", lang: "en" });
  });

  // Case 3 · the service worker → the helper request carries lang next to from
  it("Case 3 · the service worker posts /videos/<id>?from=12&lang=en", async () => {
    let listener: any;
    const urls: string[] = [];
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } } });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return { ok: true, json: async () => ({}) }; }));
    vi.resetModules();
    await import("../../src/extension/src/sw");
    await new Promise((done) => listener({ kind: "analyze", videoId: "abc123", from: 12.7, lang: "en" }, {}, done));
    expect(urls).toEqual(["http://127.0.0.1:8765/videos/abc123?from=12&lang=en"]);
  });
});
