// @vitest-environment jsdom
// The start of an analysis: the start button and its spend line, the link to the helper, and the shared flags.
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

// After the extension is reloaded, the old copy of the content script in an open tab fails quietly: no unhandled
// error, its layer goes, and it no longer reacts to the next video. Vitest fails a test on an unhandled rejection.
describe("After the extension is reloaded, the old content script of an open tab fails quietly.", () => {
  // First in this file: a content script loaded by a later group would still listen to the page.
  it("an invalidated extension context leaves no unhandled error and stops the old script", async () => {
    history.pushState({}, "", "/watch?v=abc123");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const sendMessage = vi.fn(async () => { throw new Error("Extension context invalidated."); });
    // Chrome may keep the id on an orphaned script, so the error itself has to tell.
    (globalThis as any).chrome = {
      runtime: { id: "x", sendMessage },
      storage: { local: { get: vi.fn(async () => { throw new Error("Extension context invalidated."); }),
                          set: vi.fn(async () => { throw new Error("Extension context invalidated."); }) } },
    };
    await import("../../src/extension/src/content");
    await new Promise((r) => setTimeout(r, 0));
    expect(document.querySelector(".fc-layer")).toBeNull();

    const { setSettings } = await import("../../src/extension/src/overlay");
    setSettings({ quiet: true }, document.createElement("div"));

    const calls = sendMessage.mock.calls.length;
    document.dispatchEvent(new Event("yt-navigate-finish"));
    await new Promise((r) => setTimeout(r, 0));
    expect(sendMessage.mock.calls.length).toBe(calls);
    expect(document.querySelector(".fc-layer")).toBeNull();
  });
});

// S21 A4 · The extension says when the helper is down
//
// Story: A tester opens a YouTube video with the helper stopped. Instead of the "Analizar este vídeo" button, the
// player shows "El ayudante de fact-checker no responde", how to install it and to run `fact-checker doctor`. When the
// helper comes back, the message goes and the button shows. If the helper stops during an analysis, the message shows
// again.
//
// Setup: a jsdom watch page with a player and a video, and fake timers. The content script talks to a fake service
// worker whose answer the test sets: "down" (what the service worker answers when it cannot reach the helper), "no
// file yet" or "running". Then the real service worker gets a request while the helper's address refuses the
// connection (fetch rejects with a TypeError, as Chrome does).
describe("S21 A4 · The extension says when the helper is down", () => {
  // A fresh copy of the extension modules, as when this group ran in a file of its own.
  beforeAll(() => {
    vi.resetModules();
  });

  const DOWN = { ok: false, down: true };
  const RUNNING = { video_id: "abc123", status: "running", stop_reason: null, analysed_until: 0, flags: [] };

  describe("S21 A4 · The extension says when the helper is down", () => {
    let answer: object = DOWN;
    let listener: any;
    const sendMessage = vi.fn(async (_req: any) => answer);
    const message = () => document.querySelector<HTMLElement>(".fc-down");
    const startButton = () => [...document.querySelectorAll("button")].find((b) => b.textContent === "Analizar este vídeo");
    beforeAll(() => { vi.useFakeTimers(); });
    afterAll(() => { vi.useRealTimers(); });

    // Case 1 · the helper is down when the video opens → the message with install and doctor hints, no button
    it("Case 1 · helper down on open → the message, with install and doctor hints, and no button", async () => {
      history.pushState({}, "", "/watch?v=abc123");
      document.body.innerHTML = '<div id="movie_player"><video></video></div>';
      (globalThis as any).chrome = {
        runtime: { id: "x", sendMessage, onMessage: { addListener: (f: any) => { listener = f; } } },
        storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
      };
      await import("../../src/extension/src/content");
      await vi.advanceTimersByTimeAsync(0);
      expect(message()?.textContent).toContain("El ayudante de fact-checker no responde");
      expect(message()?.textContent).toContain("instal");
      expect(message()?.textContent).toContain("fact-checker doctor");
      expect(startButton()).toBeUndefined();
    });

    // Case 2 · the helper comes back → the message goes and the button shows
    it("Case 2 · the helper comes back → no message, the button shows", async () => {
      expect(message()).not.toBeNull();
      answer = { ok: true, data: null };
      await vi.advanceTimersByTimeAsync(3000);
      expect(message()).toBeNull();
      expect(startButton()).toBeDefined();
    });

    // Case 3 · the helper stops during an analysis → the message shows again
    it("Case 3 · the helper stops during an analysis → the message shows again", async () => {
      expect(startButton()).toBeDefined();
      answer = { ok: true, data: RUNNING };
      startButton()!.click();
      await vi.advanceTimersByTimeAsync(3000);
      expect(message()).toBeNull();
      answer = DOWN;
      await vi.advanceTimersByTimeAsync(3000);
      expect(message()?.textContent).toContain("El ayudante de fact-checker no responde");
    });

    // Case 4 · the service worker cannot reach the helper → it answers "down"
    it("Case 4 · the connection to the helper is refused → the service worker answers down", async () => {
      (globalThis as any).fetch = vi.fn(async () => { throw new TypeError("Failed to fetch"); });
      await import("../../src/extension/src/sw");
      const reply = await new Promise<any>((done) => listener({ kind: "flags", videoId: "abc123", at: 3 }, {}, done));
      expect(reply).toEqual(DOWN);
    });
  });
});

// S26 A3 (extension part) · Reasons come in the viewer's language: the analyze request carries it
//
// Story: A person with a Spanish browser clicks "Analizar este vídeo" on an English interview: the extension sends its
// language with the request. A person with an English browser clicks "Analyze this video" and sends "en". What the
// helper does with it is checked in tests/helper/test_reading.py (S26 A3).
//
// Setup: a jsdom watch page with a player and a video, fake timers, the browser language set per case, and a stub
// `chrome` whose service worker answers "no flag file yet" and records each message. Then the real service worker gets
// an analyze message while a stub `fetch` records the request address.
describe("S26 A3 (extension part) · Reasons come in the viewer's language: the analyze request carries it", () => {
  // A fresh copy of the extension modules, as when this group ran in a file of its own.
  beforeAll(() => {
    vi.resetModules();
  });

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
});

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
// tests/helper/test_sharing.py (S28 A2).
describe("S28 A2 (extension part) · A second viewer gets the shared flags at once and for free", () => {
  // A fresh copy of the extension modules, as when this group ran in a file of its own.
  beforeAll(() => {
    vi.resetModules();
  });

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
});

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
describe("S30 A3 · The player says \"signals, not verdicts\" and what an analysis spends", () => {
  // A fresh copy of the extension modules, as when this group ran in a file of its own.
  beforeAll(() => {
    vi.resetModules();
  });

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
    // Case 1 · a card → its confidence "90%": S1 A4 Case 2 (card.test.ts)

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
});

// S38 A2 · A taken port moves the helper and the extension follows (the extension side)
//
// Story: Another program holds port 8765. The helper starts at login on 8766 instead, and on YouTube the "Analizar
// este vídeo" button starts an analysis whose flag file appears in the helper home. With all five ports 8765–8769
// taken, the helper log says so in one line and the helper stops; it does not restart in a loop.
//
// Setup: the real service worker with a stub `chrome` and a stub `fetch` that plays the local ports. Another program
// answers every address on its port with an HTML 404. The helper answers `/health` with its name, and the analyse
// request with "running". A port with nothing on it refuses the connection (fetch rejects with a TypeError, as Chrome
// does). The helper side is checked in tests/helper/test_server.py (S38 A2).
describe("S38 A2 · A taken port moves the helper and the extension follows (the extension side)", () => {
  // A fresh copy of the extension modules, as when this group ran in a file of its own.
  beforeAll(() => {
    vi.resetModules();
  });

  const RUNNING = { video_id: "abc123", status: "running" };
  const ports: Record<number, "foreign" | "helper"> = { 8765: "foreign", 8766: "helper" };
  const urls: string[] = [];
  let listener: any;

  beforeAll(() => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url);
      const { port, pathname } = new URL(url);
      const holder = ports[Number(port)];
      if (!holder) throw new TypeError("Failed to fetch");
      if (holder === "foreign") return { ok: false, status: 404, json: async () => { throw new SyntaxError("HTML"); } };
      return { ok: true, status: 200, json: async () => (pathname === "/health" ? { app: "fact-checker" } : RUNNING) };
    }));
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } } });
  });
  afterAll(() => { vi.unstubAllGlobals(); });

  const send = (req: object) => new Promise<any>((done) => listener(req, {}, done));

  describe("S38 A2 · the extension finds the helper on the next port", () => {
    // Case 1 · another program holds 8765, the helper is on 8766 → the analyse request reaches 8766 and answers running
    it("Case 1 · a foreign program on 8765 → the analyse request goes to the helper on 8766", async () => {
      vi.resetModules();
      await import("../../src/extension/src/sw");
      const reply = await send({ kind: "analyze", videoId: "abc123", from: 0, lang: "es" });
      expect(reply).toEqual({ ok: true, data: RUNNING });
      expect(urls).toContain("http://127.0.0.1:8766/health");
      expect(urls.at(-1)).toBe("http://127.0.0.1:8766/videos/abc123?from=0&lang=es");
    });

    // Case 2 · the next request → straight to 8766, with no new search
    it("Case 2 · the next request → straight to the kept port 8766", async () => {
      urls.length = 0;
      const reply = await send({ kind: "flags", videoId: "abc123", at: 5 });
      expect(reply).toEqual({ ok: true, data: RUNNING });
      expect(urls).toEqual(["http://127.0.0.1:8766/videos/abc123?at=5"]);
    });

    // Case 3 · the helper moves to 8767 → the failed request looks again and reaches 8767
    it("Case 3 · the helper moves to 8767 → the extension looks again and follows", async () => {
      urls.length = 0;
      delete ports[8766];
      ports[8767] = "helper";
      const reply = await send({ kind: "flags", videoId: "abc123", at: 6 });
      expect(reply).toEqual({ ok: true, data: RUNNING });
      expect(urls.at(-1)).toBe("http://127.0.0.1:8767/videos/abc123?at=6");
    });

    // Case 4 · no helper on any of the five ports → the service worker answers down
    it("Case 4 · no helper on 8765–8769 → down", async () => {
      delete ports[8767];
      const reply = await send({ kind: "flags", videoId: "abc123", at: 7 });
      expect(reply).toEqual({ ok: false, down: true });
    });
  });
});

// The extension spends nothing until the person turns it on for a video; a video already analysed shows at once.
describe("The extension spends nothing until the person turns it on for a video; a video already analysed shows at once.", () => {
  // A fresh copy of the extension modules, as when this group ran in a file of its own.
  beforeAll(() => {
    vi.resetModules();
  });

  function page(known: object | null) {
    history.pushState({}, "", "/watch?v=abc123");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const sent: any[] = [];
    (globalThis as any).chrome = {
      runtime: {
        id: "x",
        sendMessage: vi.fn(async (m: any) => {
          sent.push(m);
          return { ok: true, data: m.kind === "flags" ? known : null };
        }),
      },
      storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
    };
    return sent;
  }

  const start = () => document.querySelector<HTMLButtonElement>(".fc-start");
  const flush = () => new Promise((r) => setTimeout(r, 0));

  beforeEach(() => vi.resetModules());

  it("a new video asks for nothing until the person clicks the start button", async () => {
    const sent = page(null);
    await import("../../src/extension/src/content");
    await flush();
    expect(sent.some((m) => m.kind === "analyze")).toBe(false);
    start()!.click();
    await flush();
    expect(sent.filter((m) => m.kind === "analyze")).toEqual([expect.objectContaining({ videoId: "abc123" })]);
    expect(start()).toBeNull();
  });

  it("a video already analysed shows its flags with no start button", async () => {
    const sent = page({ video_id: "abc123", status: "done", flags: [] });
    await import("../../src/extension/src/content");
    await flush();
    expect(sent.some((m) => m.kind === "analyze")).toBe(false);
    expect(start()).toBeNull();
  });
});

// The poll of the flag file tells the helper where the person is, so the analysis follows what they watch.
describe("The poll of the flag file tells the helper where the person is, so the analysis follows what they watch.", () => {
  // A fresh copy of the extension modules, as when this group ran in a file of its own.
  beforeAll(() => {
    vi.resetModules();
  });

  it("the poll sends the playback second, and the service worker puts it on the request", async () => {
    history.pushState({}, "", "/watch?v=abc123");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const video = document.querySelector("video")!;
    Object.defineProperty(video, "currentTime", { value: 754.6, writable: true });
    const sendMessage = vi.fn(async () => ({ ok: true, data: null }));
    let listener: any;
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).chrome = {
      runtime: { id: "x", sendMessage, onMessage: { addListener: (f: any) => { listener = f; } } },
      storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
    };
    await import("../../src/extension/src/content");
    await new Promise((r) => setTimeout(r, 0));
    expect(sendMessage).toHaveBeenCalledWith({ kind: "flags", videoId: "abc123", at: 754.6, lang: "es" });

    await import("../../src/extension/src/sw");
    await new Promise<void>((done) => listener({ kind: "flags", videoId: "abc123", at: 754.6 }, {}, () => done()));
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8765/videos/abc123?at=754");
  });
});

// Inline 2026-11-22 · A new video never shows the flags of the one before
//
// Story: The person opens video A, whose analysis is running, and moves to video B before the helper answers for A.
// A's late answer arrives while B is on screen. B shows its own state (no file yet: the start button), and the
// extension stops asking about A.
//
// Setup: a jsdom watch page with a player and a video, fake timers, and a stub `chrome` whose service worker holds the
// first flag answer for A until the test releases it; B has no flag file.
describe("A new video never shows the flags of the one before", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  it("A's late answer after a move to B → B shows its start button, and nobody asks about A again", async () => {
    vi.useFakeTimers();
    const RUNNING_A = { video_id: "aaa111", status: "running", stop_reason: null, analysed_until: 0, flags: [] };
    let release: (value: object) => void = () => {};
    const held = new Promise<object>((done) => { release = done; });
    const sendMessage = vi.fn(async (req: any) =>
      req.kind === "flags" && req.videoId === "aaa111" ? held : { ok: true, data: null });
    vi.stubGlobal("chrome", {
      runtime: { id: "x", sendMessage, onMessage: { addListener: () => {} } },
      storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
    });
    vi.resetModules();
    history.pushState({}, "", "/watch?v=aaa111");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    await import("../../src/extension/src/content");
    await vi.advanceTimersByTimeAsync(0);

    history.pushState({}, "", "/watch?v=bbb222");
    document.dispatchEvent(new Event("yt-navigate-finish"));
    await vi.advanceTimersByTimeAsync(0);
    release({ ok: true, data: RUNNING_A });
    const before = sendMessage.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10_000);

    const asked = sendMessage.mock.calls.slice(before).map(([req]) => req);
    expect(asked.filter((req) => req.videoId === "aaa111")).toEqual([]);
    expect([...document.querySelectorAll("button")].some((b) => b.textContent === "Analizar este vídeo")).toBe(true);
    vi.clearAllTimers();
  });
});

// Inline 2026-11-22 · A flag that arrives while the video is paused shows at once
//
// Story: The person pauses the video while its analysis runs. The next poll brings a new flag. The panel lists it
// without waiting for playback to resume.
//
// Setup: a jsdom watch page with a paused video (no timeupdate fires), fake timers, and a stub `chrome` whose service
// worker answers a running analysis with no flag, then the same analysis with one invented flag.
describe("A flag that arrives while the video is paused shows at once", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  it("the poll brings a flag while paused → the panel lists its quote with no timeupdate", async () => {
    vi.useFakeTimers();
    const QUOTE = "una cifra inventada en pausa";
    const flag = { id: "false-1.0", t: 0.5, speaker: "Ana", quote: QUOTE, type: "inaccuracy", label: "false",
      reason: "Motivo inventado.", confidence: 0.9, related: null, sources: [], note: null, on_player: true };
    let file: object = { video_id: "ccc333", status: "running", stop_reason: null, analysed_until: 0, flags: [] };
    vi.stubGlobal("chrome", {
      runtime: { id: "x", sendMessage: vi.fn(async (req: any) => (req.kind === "flags" ? { ok: true, data: file } : { ok: true })),
                 onMessage: { addListener: () => {} } },
      storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
    });
    vi.resetModules();
    history.pushState({}, "", "/watch?v=ccc333");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    await import("../../src/extension/src/content");
    await vi.advanceTimersByTimeAsync(0);
    expect(document.body.textContent).not.toContain(QUOTE);
    file = { ...file, flags: [flag] };
    await vi.advanceTimersByTimeAsync(3000);
    expect(document.body.textContent).toContain(QUOTE);
    vi.clearAllTimers();
  });
});
