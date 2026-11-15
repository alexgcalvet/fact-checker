// S30 A3 · The player says "signals, not verdicts" and what an analysis spends
//
// Story: A person with a Spanish browser sees a card with "90%" confidence, and the foot of the side panel reads
// "Señales automáticas, no veredictos" ("Automatic signals, not verdicts" in English). On a video not analysed yet,
// under "Analizar este vídeo" a line reads "Usa tu suscripción de Claude: un vídeo de 1 h gasta una parte notable de tu
// límite"; with Codex it names ChatGPT; with an API provider it reads "Se cobra en tu cuenta de API".
//
// Setup: a jsdom watch page with a player and a video at second 43, fake timers, the browser language set per case,
// and a stub `chrome` whose service worker answers the poll with a done flag file of one flag at second 42 (or "no
// flag file yet"), names the provider of the parts per case, and records each message. The content script runs as on
// YouTube. Then the real service worker gets a `provider` message while a stub `fetch` records the request.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

const SIGNALS = { es: "Señales automáticas, no veredictos", en: "Automatic signals, not verdicts" };
const SPEND = {
  claude: { es: "Usa tu suscripción de Claude: un vídeo de 1 h gasta una parte notable de tu límite",
    en: "Uses your Claude subscription: a 1-hour video spends a notable share of your limit" },
  codex: { es: "Usa tu suscripción de ChatGPT: un vídeo de 1 h gasta una parte notable de tu límite",
    en: "Uses your ChatGPT subscription: a 1-hour video spends a notable share of your limit" },
  api: { es: "Se cobra en tu cuenta de API", en: "Billed to your API account" },
};
const FILE = { video_id: "abc123", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "Invitado", quote: "frase inventada", type: "fallacy",
    label: "ad_hominem", reason: "Ataca.", confidence: 0.9, on_player: true, related: null, sources: [], note: null }] };

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });
});

async function watch(language: "es-ES" | "en-US", known: object | null, provider = "claude") {
  vi.useFakeTimers();
  Object.defineProperty(navigator, "language", { value: language, configurable: true });
  const sendMessage = vi.fn(async (req: any) => {
    if (req.kind === "flags") return { ok: true, data: structuredClone(known) };
    if (req.kind === "share") return { ok: true, data: { share: true } };
    if (req.kind === "provider") return { ok: true, data: { provider } };
    return { ok: true, data: null };
  });
  vi.stubGlobal("chrome", {
    runtime: { id: "x", sendMessage, onMessage: { addListener: () => {} } },
    storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
  });
  vi.resetModules();
  history.pushState({}, "", "/watch?v=abc123");
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const video = document.querySelector("video")!;
  Object.defineProperty(video, "currentTime", { value: 43, configurable: true, writable: true });
  await import("../../src/extension/src/content");
  await vi.advanceTimersByTimeAsync(0);
  video.dispatchEvent(new Event("timeupdate"));
  const text = () => document.body.textContent!;
  const openPanel = async () => {
    document.querySelector<HTMLElement>(".fc-panel-tab")!.click();
    await vi.advanceTimersByTimeAsync(0);
    return document.querySelector<HTMLElement>(".fc-panel")!;
  };
  return { text, openPanel };
}

describe("S30 A3 · signals, not verdicts, and the spend line", () => {
  // Case 1 · a card → its confidence "90%"
  it("Case 1 · the card shows 90%", async () => {
    await watch("es-ES", FILE);
    expect(document.querySelector(".fc-card")!.textContent).toContain("90%");
    vi.clearAllTimers();
  });

  // Case 2 · the side panel → its foot says "Señales automáticas, no veredictos"; in English, the English line
  it("Case 2 · the panel foot line in Spanish and in English", async () => {
    let panel = await (await watch("es-ES", FILE)).openPanel();
    expect(panel.textContent).toContain(SIGNALS.es);
    vi.clearAllTimers();
    panel = await (await watch("en-US", FILE)).openPanel();
    expect(panel.textContent).toContain(SIGNALS.en);
    expect(panel.textContent).not.toContain(SIGNALS.es);
    vi.clearAllTimers();
  });

  // Case 3 · a video not analysed, Claude → the Claude line under the analyse button, once
  it("Case 3 · Claude → \"Usa tu suscripción de Claude…\" once, beside \"Analizar este vídeo\"", async () => {
    const { text } = await watch("es-ES", null, "claude");
    expect(text()).toContain("Analizar este vídeo");
    expect(text().split(SPEND.claude.es)).toHaveLength(2);
    vi.clearAllTimers();
  });

  // Case 4 · Codex → ChatGPT; an API provider → "Se cobra en tu cuenta de API"; English for an English browser
  it("Case 4 · codex → ChatGPT; anthropic, openai, chat → API; English texts", async () => {
    expect((await watch("es-ES", null, "codex")).text()).toContain(SPEND.codex.es);
    vi.clearAllTimers();
    for (const provider of ["anthropic", "openai", "chat"]) {
      expect((await watch("es-ES", null, provider)).text()).toContain(SPEND.api.es);
      vi.clearAllTimers();
    }
    expect((await watch("en-US", null, "claude")).text()).toContain(SPEND.claude.en);
    vi.clearAllTimers();
    expect((await watch("en-US", null, "chat")).text()).toContain(SPEND.api.en);
    vi.clearAllTimers();
  });

  // Case 5 · an analysed video → no spend line
  it("Case 5 · an analysed video → no spend line", async () => {
    const { text } = await watch("es-ES", FILE, "claude");
    expect(text()).not.toContain(SPEND.claude.es);
    vi.clearAllTimers();
  });

  // Case 6 · the service worker → GET /provider
  it("Case 6 · the service worker asks GET /provider", async () => {
    let listener: any;
    const urls: string[] = [];
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } } });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return { ok: true, json: async () => ({ provider: "codex" }) }; }));
    vi.resetModules();
    await import("../../src/extension/src/sw");
    const reply = await new Promise((done) => { if (listener({ kind: "provider", videoId: "abc123" }, {}, done) !== true) done(undefined); });
    expect(urls).toEqual(["http://127.0.0.1:8765/provider"]);
    expect(reply).toEqual({ ok: true, data: { provider: "codex" } });
  });
});
