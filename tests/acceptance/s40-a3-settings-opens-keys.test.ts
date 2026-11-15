// S40 A3 · A key saved from the extension (the extension side)
//
// Story: The provider is `anthropic` and no key is set. On YouTube, the person opens ⚙ and clicks "Claves". A helper
// page lists `ANTHROPIC_API_KEY` as "falta". The person pastes the key in a hidden field and saves. The page says
// "guardada", never shows the value, the key file is readable only by the person, and the next analysis reads with
// that key with no restart.
//
// Setup: a jsdom watch page with a player and a video, fake timers, the browser language set per case, and a stub
// `chrome` whose service worker answers "no flag file yet" and records each message. The content script runs as on
// YouTube. Then the real service worker gets the keys message with a stub `chrome.tabs` and a stub `fetch` that plays
// the local ports: another program on 8765, the helper on 8766. The helper page is checked in test_s40_a3_key_page.py.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });
});

async function watch(language: "es-ES" | "en-US") {
  vi.useFakeTimers();
  Object.defineProperty(navigator, "language", { value: language, configurable: true });
  const sendMessage = vi.fn(async (req: any) =>
    req.kind === "share" ? { ok: true, data: { share: true } } : { ok: true, data: null });
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
  const panel = document.querySelector<HTMLElement>(".fc-panel")!;
  [...panel.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent === "⚙")!.click();
  await vi.advanceTimersByTimeAsync(0);
  const keys = (text: string) => [...panel.querySelectorAll<HTMLButtonElement>(".fc-settings button")]
    .find((b) => b.textContent === text);
  const sent = () => sendMessage.mock.calls.map(([req]) => req).filter((req: any) => req.kind === "keys");
  return { keys, sent };
}

describe("S40 A3 · ⚙ → Claves opens the helper's key page", () => {
  // Case 1 · a Spanish browser, ⚙ → a "Claves" button; a click asks the service worker for the key page in Spanish
  it("Case 1 · ⚙ → \"Claves\" → the keys message, in Spanish", async () => {
    const { keys, sent } = await watch("es-ES");
    expect(keys("Claves"), "no Claves button in ⚙").toBeDefined();
    keys("Claves")!.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent()).toEqual([{ kind: "keys", videoId: "abc123", lang: "es" }]);
    vi.clearAllTimers();
  });

  // Case 2 · an English browser → the button says "Keys" and asks for the page in English
  it("Case 2 · English browser → \"Keys\" → the keys message, in English", async () => {
    const { keys, sent } = await watch("en-US");
    expect(keys("Keys"), "no Keys button in ⚙").toBeDefined();
    keys("Keys")!.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent()).toEqual([{ kind: "keys", videoId: "abc123", lang: "en" }]);
    vi.clearAllTimers();
  });

  // Case 3 · the service worker, the helper on 8766 → a new tab on http://127.0.0.1:8766/keys?lang=es, and no key
  // crosses the extension: only /health is fetched
  it("Case 3 · the service worker opens the key page on the port where the helper answers", async () => {
    let listener: any;
    const tabs: string[] = [];
    const urls: string[] = [];
    vi.stubGlobal("chrome", {
      runtime: { onMessage: { addListener: (f: any) => { listener = f; } } },
      tabs: { create: vi.fn(async ({ url }: { url: string }) => { tabs.push(url); return {}; }) },
    });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url);
      const port = Number(new URL(url).port);
      if (port === 8765) return { ok: false, status: 404, json: async () => { throw new SyntaxError("HTML"); } };
      if (port === 8766) return { ok: true, status: 200, json: async () => ({ app: "fact-checker" }) };
      throw new TypeError("Failed to fetch");
    }));
    vi.resetModules();
    await import("../../src/extension/src/sw");
    const send = (req: unknown) => new Promise((done) => { if (listener(req, {}, done) !== true) done(undefined); });
    expect(await send({ kind: "keys", videoId: "abc123", lang: "es" })).toEqual({ ok: true, data: null });
    expect(tabs).toEqual(["http://127.0.0.1:8766/keys?lang=es"]);
    expect(urls.every((u) => u.endsWith("/health"))).toBe(true);
  });

  // Case 4 · no helper on 8765–8769 → the service worker answers down and opens no tab
  it("Case 4 · no helper → down, no tab", async () => {
    let listener: any;
    const create = vi.fn(async () => ({}));
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } }, tabs: { create } });
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    vi.resetModules();
    await import("../../src/extension/src/sw");
    const send = (req: unknown) => new Promise((done) => { if (listener(req, {}, done) !== true) done(undefined); });
    expect(await send({ kind: "keys", videoId: "abc123", lang: "es" })).toEqual({ ok: false, down: true });
    expect(create).not.toHaveBeenCalled();
  });
});
