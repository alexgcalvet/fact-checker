// S27 A3 (extension part) · With sharing off, nothing leaves the laptop: the panel line and the ⚙ box
//
// Story: The foot of the side panel says "Tus marcas se comparten con el autor para mejorar el detector · Desactivar en
// ⚙" and has no send button. In ⚙ the tester unticks "Compartir mis marcas con el autor". The foot of the panel now
// says "Tus marcas no se comparten · Activar en ⚙", and `share_marks = false` is in `~/.fact-checker/config.toml` beside
// the existing lines. The tester marks a card: after a second the collector has nothing. The tester ticks the box again
// and marks another card: only that new mark goes; the one given while sharing was off never does.
//
// Setup: a jsdom watch page with a player and a video, fake timers, the browser language set per case, and a stub
// `chrome` whose service worker answers "no flag file yet", keeps the sharing state the helper would keep, and records
// each message. The content script runs as on YouTube. Then the real service worker gets the two sharing messages while
// a stub `fetch` records each request. What the helper does is checked in test_s27_a3_sharing_off.py.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

const ON = {
  es: "Tus marcas se comparten con el autor para mejorar el detector · Desactivar en ⚙",
  en: "Your marks are shared with the author to improve the detector · Turn off in ⚙",
};
const OFF = { es: "Tus marcas no se comparten · Activar en ⚙", en: "Your marks are not shared · Turn on in ⚙" };
const TOGGLE = { es: "Compartir mis marcas y análisis", en: "Share my marks and analyses" };

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });
});

async function watch(language: "es-ES" | "en-US", shared: boolean) {
  vi.useFakeTimers();
  Object.defineProperty(navigator, "language", { value: language, configurable: true });
  let share = shared;
  const sendMessage = vi.fn(async (req: any) => {
    if (req.kind === "share") return { ok: true, data: { share } };
    if (req.kind === "set-share") { share = req.share; return { ok: true, data: { share } }; }
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
  const gear = () => [...panel().querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent === "⚙")!;
  const toggle = (text: string) =>
    [...panel().querySelectorAll("label")].find((l) => l.textContent!.includes(text))?.querySelector("input");
  const sets = () => sendMessage.mock.calls.map(([req]) => req).filter((req: any) => req.kind === "set-share");
  return { panel, gear, toggle, sets };
}

describe("S27 A3 · the panel line and the ⚙ box of sharing", () => {
  // Case 1 · sharing on → the line says so, and no send button is left
  it("Case 1 · sharing on → the foot line in Spanish; no \"Enviar mis marcas\" button", async () => {
    const { panel } = await watch("es-ES", true);
    expect(panel().textContent).toContain(ON.es);
    const buttons = [...panel().querySelectorAll("button")].map((b) => b.textContent!);
    expect(buttons.some((t) => t.startsWith("Enviar mis marcas"))).toBe(false);
    vi.clearAllTimers();
  });

  // Case 2 · ⚙, untick the box → set-share false goes out; the line says sharing is off
  it("Case 2 · ⚙ → untick \"Compartir mis marcas y análisis\" → set-share false; the line says it is off", async () => {
    const { panel, gear, toggle, sets } = await watch("es-ES", true);
    gear().click();
    await vi.advanceTimersByTimeAsync(0);
    const box = toggle(TOGGLE.es);
    expect(box, "no sharing box").toBeDefined();
    expect(box!.checked).toBe(true);
    box!.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(sets()).toEqual([{ kind: "set-share", videoId: "abc123", share: false }]);
    expect(panel().textContent).toContain(OFF.es);
    expect(panel().textContent).not.toContain(ON.es);
    vi.clearAllTimers();
  });

  // Case 3 · the helper already has sharing off → the line says off and the box is unticked; ticking turns it on
  it("Case 3 · sharing off at the helper → the box is unticked; ticking it sends set-share true", async () => {
    const { panel, gear, toggle, sets } = await watch("es-ES", false);
    expect(panel().textContent).toContain(OFF.es);
    gear().click();
    await vi.advanceTimersByTimeAsync(0);
    expect(toggle(TOGGLE.es)!.checked).toBe(false);
    toggle(TOGGLE.es)!.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(sets()).toEqual([{ kind: "set-share", videoId: "abc123", share: true }]);
    expect(panel().textContent).toContain(ON.es);
    vi.clearAllTimers();
  });

  // Case 4 · an English browser → the line and the box in English
  it("Case 4 · English browser → \"Your marks are shared…\" and \"Share my marks and analyses\"", async () => {
    const { panel, gear, toggle } = await watch("en-US", true);
    expect(panel().textContent).toContain(ON.en);
    gear().click();
    await vi.advanceTimersByTimeAsync(0);
    expect(toggle(TOGGLE.en)).toBeDefined();
    vi.clearAllTimers();
  });

  // Case 5 · the service worker → GET /share, and POST /share with {"share": false}
  it("Case 5 · the service worker asks GET /share and posts {\"share\": false} to /share", async () => {
    let listener: any;
    const requests: { url: string; method: string; body?: string }[] = [];
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } } });
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      requests.push({ url, method: init?.method ?? "GET", ...(init?.body ? { body: String(init.body) } : {}) });
      return { ok: true, json: async () => ({ share: false }) };
    }));
    vi.resetModules();
    await import("../../src/extension/src/sw");
    const send = (req: unknown) => new Promise((done) => { if (listener(req, {}, done) !== true) done(undefined); });
    expect(await send({ kind: "share", videoId: "abc123" })).toEqual({ ok: true, data: { share: false } });
    expect(await send({ kind: "set-share", videoId: "abc123", share: false })).toEqual({ ok: true, data: { share: false } });
    expect(requests).toEqual([
      { url: "http://127.0.0.1:8765/share", method: "GET" },
      { url: "http://127.0.0.1:8765/share", method: "POST", body: JSON.stringify({ share: false }) },
    ]);
  });
});
