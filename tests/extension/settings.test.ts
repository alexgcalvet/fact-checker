// @vitest-environment jsdom
// The ⚙ settings and the viewer's controls: language, sharing and its consent question, quiet mode, pin, pause and text size.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../src/extension/src/guard";
import { mountOverlay, settings } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

// S26 A1 · The player and the panel speak the browser's language
//
// Story: A person with an English Chrome opens a video with a false figure and 2 unsent marks. The card says "False
// claim" with "✓ Agree" and "✗ Disagree", the tab says "Flags (1)" and the panel button "Send my marks (2)"; the
// "helper does not answer" notice is in English only. With a Spanish Chrome the same screens say "Dato falso",
// "✓ De acuerdo", "Avisos (1)" and "Enviar mis marcas (2)". In ⚙ the person clicks "ES": the texts turn Spanish at
// once and the choice is kept with the other settings.
//
// Setup: a jsdom page with a player and a 100-second video at second 11, the browser language set per case
// (navigator.language), a stub `chrome` whose storage records what is saved. The overlay and the panel are mounted as
// the content script mounts them, with one false-figure flag at second 10 and a fake helper with 2 unsent marks. For
// the notice, the content script itself runs against a service worker that answers "down", and the locale files of
// the manifest are read.
describe("S26 A1 · The player and the panel speak the browser's language", () => {
  const EXTENSION = join(__dirname, "../../src/extension");
  const flagFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{ id: "false-10.0", t: 10, speaker: "Guest", quote: "unemployment fell by half in one year", type: "inaccuracy",
      label: "false", reason: "It fell from 12 % to 11 %.", confidence: 0.9, on_player: true, related: null,
      sources: [{ publisher: "BLS", url: "https://www.bls.gov/x", date: "2026-10-01" }], note: null }],
  } as any;
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  let saved: any[] = [];

  function browser(language: string, stored: object = {}) {
    Object.defineProperty(navigator, "language", { value: language, configurable: true });
    saved = [];
    vi.stubGlobal("chrome", {
      runtime: { id: "x", sendMessage: vi.fn(async () => ({ ok: false, down: true })), onMessage: { addListener: () => {} } },
      storage: { local: { get: vi.fn(async () => stored), set: vi.fn(async (v: any) => { saved.push(structuredClone(v)); }) } },
    });
  }

  async function page(language: string, stored: object = {}) {
    browser(language, stored);
    vi.resetModules();
    const { mountOverlay } = await import("../../src/extension/src/overlay");
    const { mountPanel } = await import("../../src/extension/src/panel");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "currentTime", { value: 11, writable: true, configurable: true });
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show, () => {},
      { get: async () => true, set: async (on: boolean) => on });
    await settle();
    player.querySelector<HTMLElement>(".fc-panel-tab")!.click();
    await settle();
    video.dispatchEvent(new Event("timeupdate"));
    const buttons = () => [...player.querySelectorAll<HTMLButtonElement>("button")].map((b) => b.textContent!.trim());
    const card = () => player.querySelector<HTMLElement>(".fc-card")!.textContent!;
    const tab = () => player.querySelector<HTMLElement>(".fc-panel-tab")!.textContent!;
    return { player, video, buttons, card, tab };
  }

  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  describe("S26 A1 · The player and the panel speak the browser's language", () => {
    // Case 1 · an English browser → the card, its buttons, the tab and the panel button in English, no Spanish
    it("Case 1 · English browser → \"False claim\", \"✓ Agree\", \"✗ Disagree\", \"Flags (1)\"", async () => {
      const { card, buttons, tab } = await page("en-US");
      expect(card()).toContain("False claim");
      expect(buttons()).toEqual(expect.arrayContaining(["✓ Agree", "✗ Disagree", "Export summary"]));
      expect(tab()).toContain("Flags (1)");
      expect(card()).not.toContain("Dato falso");
      expect(buttons()).not.toContain("✓ De acuerdo");
    });

    // Case 2 · a Spanish browser → the same screens in Spanish
    it("Case 2 · Spanish browser → \"Dato falso\", \"✓ De acuerdo\", \"Avisos (1)\"", async () => {
      const { card, buttons, tab } = await page("es-ES");
      expect(card()).toContain("Dato falso");
      expect(buttons()).toEqual(expect.arrayContaining(["✓ De acuerdo", "✗ No"]));
      expect(tab()).toContain("Avisos (1)");
    });

    // Case 3 · an English browser, ⚙ then "ES" → Spanish at once, kept in the settings; "EN" → English again
    it("Case 3 · ⚙ → ES switches to Spanish at once and saves lang \"es\"; EN switches back", async () => {
      const { player, video, card, buttons, tab } = await page("en-US");
      const click = (text: string) => {
        const found = [...player.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent!.trim() === text);
        expect(found, `no "${text}" button`).toBeDefined();
        found!.click();
      };
      click("⚙");
      click("ES");
      video.dispatchEvent(new Event("timeupdate"));
      expect(card()).toContain("Dato falso");
      expect(buttons()).toEqual(expect.arrayContaining(["✓ De acuerdo"]));
      expect(tab()).toContain("Avisos (1)");
      expect(saved.at(-1)?.settings?.lang).toBe("es");
      click("EN");
      video.dispatchEvent(new Event("timeupdate"));
      expect(card()).toContain("False claim");
      expect(saved.at(-1)?.settings?.lang).toBe("en");
      // The kept choice wins over the browser's language when the page opens again.
      const again = await page("en-US", { settings: { lang: "es" } });
      expect(again.card()).toContain("Dato falso");
      expect(again.tab()).toContain("Avisos (1)");
    });

    // Case 4 · the helper is down → the notice in the browser's language only
    it("Case 4 · helper down → the notice in English only for an English browser, in Spanish only for a Spanish one", async () => {
      vi.useFakeTimers();
      for (const [language, own, other] of [["en-GB", "The fact-checker helper does not answer.", "El ayudante"],
        ["es-MX", "El ayudante de fact-checker no responde.", "does not answer"]]) {
        browser(language);
        vi.resetModules();
        history.pushState({}, "", "/watch?v=abc123");
        document.body.innerHTML = '<div id="movie_player"><video></video></div>';
        await import("../../src/extension/src/content");
        await vi.advanceTimersByTimeAsync(0);
        const notice = document.querySelector<HTMLElement>(".fc-down")?.textContent ?? "";
        expect(notice, language).toContain(own);
        expect(notice, language).not.toContain(other);
        vi.clearAllTimers();
      }
    });

    // Case 5 · the manifest → its description from the locale files, in Spanish and in English
    it("Case 5 · the manifest description comes from _locales/es and _locales/en", () => {
      const manifest = JSON.parse(readFileSync(join(EXTENSION, "manifest.json"), "utf8"));
      expect(manifest.default_locale).toBe("en");
      expect(manifest.description).toBe("__MSG_description__");
      for (const lang of ["es", "en"]) {
        const messages = JSON.parse(readFileSync(join(EXTENSION, "_locales", lang, "messages.json"), "utf8"));
        expect(messages.description?.message, lang).toBeTruthy();
      }
    });
  });
});

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
// a stub `fetch` records each request. What the helper does is checked in tests/helper/test_sharing.py (S27 A3).
describe("S27 A3 (extension part) · With sharing off, nothing leaves the laptop: the panel line and the ⚙ box", () => {
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
});

// S30 A2 (extension part) · Nothing is shared before the person says yes
//
// Story: A new tester has never answered. They click "✓ De acuerdo" on a card: a box asks "¿Compartir tus marcas y
// análisis con el autor para mejorar el detector? Se envían el aviso, la frase, tu motivo y el vídeo; nada de tu
// equipo." with "Sí, compartir", "No" and a link to the privacy notice (in English with an English browser). Until they
// answer, the collector gets nothing. "Sí, compartir" sends that mark and later whole analyses; "No" keeps them on the
// laptop. The next mark or analysis asks nothing.
//
// Setup: a jsdom watch page with a player and a video at second 43, fake timers, the browser language set per case,
// and a stub `chrome` whose service worker answers the poll with a done flag file of two flags (or "no flag file yet"
// for the analyse case), keeps the sharing answer as the helper would (null until answered), and records each message.
// The content script runs as on YouTube. What the helper shares is checked in tests/helper/test_sharing.py (S30 A2).
describe("S30 A2 (extension part) · Nothing is shared before the person says yes", () => {
  const QUESTION = {
    es: "¿Compartir tus marcas y análisis con el autor para mejorar el detector? Se envían el aviso, la frase, tu motivo y el vídeo; nada de tu equipo.",
    en: "Share your marks and analyses with the author to improve the detector? The flag, the quote, your reason and the video are sent; nothing from your computer.",
  };
  const YES = { es: "Sí, compartir", en: "Yes, share" };

  const flag = (id: string, t: number) => ({
    id, t, speaker: "Invitado", quote: `frase inventada ${id}`, type: "fallacy", label: "ad_hominem", reason: "Ataca.",
    confidence: 0.9, on_player: true, related: null, sources: [], note: null,
  });
  const FILE = { video_id: "abc123", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [flag("ad_hominem-42.0", 42), flag("ad_hominem-43.0", 43)] };

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });
  });

  async function watch(language: "es-ES" | "en-US", known: object | null = FILE, answered: boolean | null = null) {
    vi.useFakeTimers();
    Object.defineProperty(navigator, "language", { value: language, configurable: true });
    let share = answered;
    const sendMessage = vi.fn(async (req: any) => {
      if (req.kind === "flags") return { ok: true, data: structuredClone(known) };
      if (req.kind === "share") return { ok: true, data: { share } };
      if (req.kind === "set-share") { share = req.share; return { ok: true, data: { share } }; }
      if (req.kind === "provider") return { ok: true, data: { provider: "claude" } };
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
    const buttons = (text: string) =>
      [...document.querySelectorAll<HTMLButtonElement>("button")].filter((b) => b.textContent!.trim() === text);
    const click = async (text: string, i = 0) => {
      const b = buttons(text)[i];
      expect(b, `no button "${text}"`).toBeDefined();
      b.click();
      await vi.advanceTimersByTimeAsync(0);
    };
    const sent = (kind: string) => sendMessage.mock.calls.map(([req]) => req).filter((req: any) => req.kind === kind);
    const asked = () => document.body.textContent!.includes(QUESTION.es) || document.body.textContent!.includes(QUESTION.en);
    return { buttons, click, sent, asked };
  }

  describe("S30 A2 · the consent question before the first share", () => {
    // Case 1 · a first vote, never answered → the question in Spanish, its two buttons and the privacy link; no mark sent
    it("Case 1 · ✓ De acuerdo → the Spanish question, \"Sí, compartir\", \"No\", a PRIVACY.md link; no mark yet", async () => {
      const { buttons, click, sent } = await watch("es-ES");
      await click("✓ De acuerdo");
      expect(document.body.textContent).toContain(QUESTION.es);
      expect(buttons(YES.es)).toHaveLength(1);
      expect(buttons("No")).toHaveLength(1);
      expect(document.querySelector<HTMLAnchorElement>('a[href$="PRIVACY.md"]')).not.toBeNull();
      expect(sent("mark")).toEqual([]);
      expect(sent("set-share")).toEqual([]);
      vi.clearAllTimers();
    });

    // Case 2 · "Sí, compartir" → set-share true, then that mark; the next vote asks nothing
    it("Case 2 · Sí, compartir → set-share true, the mark goes, the box goes; a second vote asks nothing", async () => {
      const { click, sent, asked } = await watch("es-ES");
      await click("✓ De acuerdo");
      await click(YES.es);
      expect(sent("set-share")).toEqual([{ kind: "set-share", videoId: "abc123", share: true }]);
      expect(sent("mark").map((m: any) => m.flagId)).toEqual(["ad_hominem-42.0"]);
      expect(asked()).toBe(false);
      await click("✓ De acuerdo");
      expect(asked()).toBe(false);
      expect(sent("mark")).toHaveLength(2);
      expect(sent("set-share")).toHaveLength(1);
      vi.clearAllTimers();
    });

    // Case 3 · "No" → set-share false; the mark stays on the laptop (the helper keeps it unshared); no second question
    it("Case 3 · No → set-share false, then the mark; a second vote asks nothing", async () => {
      const { click, sent, asked } = await watch("es-ES");
      await click("✓ De acuerdo");
      await click("No");
      expect(sent("set-share")).toEqual([{ kind: "set-share", videoId: "abc123", share: false }]);
      expect(sent("mark")).toHaveLength(1);
      expect(asked()).toBe(false);
      await click("✓ De acuerdo");
      expect(asked()).toBe(false);
      vi.clearAllTimers();
    });

    // Case 4 · an English browser → the question and the buttons in English
    it("Case 4 · English browser → the English question with \"Yes, share\" and \"No\"", async () => {
      const { buttons, click } = await watch("en-US");
      await click("✓ Agree");
      expect(document.body.textContent).toContain(QUESTION.en);
      expect(document.body.textContent).not.toContain(QUESTION.es);
      expect(buttons(YES.en)).toHaveLength(1);
      expect(buttons("No")).toHaveLength(1);
      vi.clearAllTimers();
    });

    // Case 5 · "Analizar este vídeo" before any mark → the question first; the analysis starts after the answer
    it("Case 5 · Analizar este vídeo, never answered → the question; analyze only after Sí, compartir", async () => {
      const { click, sent } = await watch("es-ES", null);
      await click("Analizar este vídeo");
      expect(document.body.textContent).toContain(QUESTION.es);
      expect(sent("analyze")).toEqual([]);
      await click(YES.es);
      expect(sent("set-share")).toEqual([{ kind: "set-share", videoId: "abc123", share: true }]);
      expect(sent("analyze")).toHaveLength(1);
      vi.clearAllTimers();
    });

    // Case 6 · already answered (yes or no) → a vote asks nothing and the mark goes at once
    it("Case 6 · the helper already has an answer → no question, the mark goes", async () => {
      for (const answered of [true, false]) {
        const { click, sent, asked } = await watch("es-ES", FILE, answered);
        await click("✓ De acuerdo");
        expect(asked()).toBe(false);
        expect(sent("mark")).toHaveLength(1);
        expect(sent("set-share")).toEqual([]);
        vi.clearAllTimers();
      }
    });
  });
});

// S34 A3 · Quiet mode shows serious flags only
//
// Story: The person turns on quiet mode, now called "Solo graves", on the same video. The serious card shows; the
// moderate one does not. While the analysis is still running and nothing is judged yet, a flag shows only with a
// confidence of 90 % or more, as before.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel mounted as the content script
// mounts them. A judged file holds a serious false figure at second 10 (confidence 0.85) and a moderate misleading
// figure at second 30 (confidence 0.95). A running file holds two unjudged false figures: second 10 (confidence 0.92)
// and second 30 (confidence 0.85). The person turns quiet mode on with its box in ⚙ of the side panel. Playback moves
// to one second after each flag.
describe("S34 A3 · Quiet mode shows serious flags only", () => {
  const flag = (t: number, label: string, confidence: number, judge?: object) => ({
    id: `${label}-${t}.0`, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type: "inaccuracy", label,
    reason: `Motivo del segundo ${t}.`, confidence, on_player: true, related: null, sources: [], note: null,
    ...(judge ? { judge } : {}),
  });
  const judgedFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [flag(10, "false", 0.85, { verdict: "keep", reason: "Bajó del 12 % al 11 %.", severity: "serious" }),
      flag(30, "misleading", 0.95, { verdict: "keep", reason: "Cuenta solo un año.", severity: "moderate" })],
  } as any;
  const runningFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "running", stop_reason: null,
    flags: [flag(10, "false", 0.92), flag(30, "false", 0.85)],
  } as any;

  function page(flagFile: object, lang: "es" | "en" = "es") {
    settings.lang = lang;
    settings.quiet = false;
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    let now = 0;
    Object.defineProperty(video, "currentTime", { get: () => now, set: (t) => { now = t; }, configurable: true });
    const overlay = mountOverlay(player, video, () => flagFile as any, () => {});
    mountPanel(overlay.layer, video, () => flagFile as any, overlay.show);
    // The person opens the side panel and its ⚙; the quiet box is the one checkbox before the language choice.
    player.querySelector<HTMLElement>(".fc-panel-tab")!.click();
    [...player.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent === "⚙")!.click();
    const quietBox = () => player.querySelector<HTMLLabelElement>(".fc-settings label")!;
    const quietOn = () => quietBox().querySelector("input")!.click();
    const at = (t: number) => {
      now = t;
      video.dispatchEvent(new Event("timeupdate"));
      return [...player.querySelectorAll<HTMLElement>(".fc-card")];
    };
    return { at, quietBox, quietOn };
  }

  afterEach(() => { settings.lang = null; settings.quiet = false; });

  describe("S34 A3 · Quiet mode shows serious flags only", () => {
    // Case 1 · the quiet box in ⚙ → it reads "Solo graves" ("Serious only" in English)
    it("Case 1 · the quiet box → \"Solo graves\" / \"Serious only\"", () => {
      expect(page(judgedFile).quietBox().textContent!.trim()).toBe("Solo graves");
      expect(page(judgedFile, "en").quietBox().textContent!.trim()).toBe("Serious only");
    });

    // Case 2 · quiet mode on a judged file → the serious card shows, even below 90 %
    it("Case 2 · quiet mode, the serious flag at 85 % → its card shows", () => {
      const { at, quietOn } = page(judgedFile);
      quietOn();
      expect(settings.quiet).toBe(true);
      const cards = at(11);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Dato falso");
    });

    // Case 3 · quiet mode on a judged file → the moderate card does not show, even at 95 %
    it("Case 3 · quiet mode, the moderate flag at 95 % → no card", () => {
      const { at, quietOn } = page(judgedFile);
      quietOn();
      expect(at(31).length).toBe(0);
    });

    // Case 4 · quiet mode while the analysis runs, nothing judged → a flag at 92 % shows, a flag at 85 % does not
    it("Case 4 · quiet mode, unjudged flags → only the one at 90 % or more shows", () => {
      const { at, quietOn } = page(runningFile);
      quietOn();
      expect(at(11).length).toBe(1);
      expect(at(31).length).toBe(0);
    });

    // Case 5 · quiet mode off → both judged cards show as usual
    it("Case 5 · quiet mode off → both judged cards show", () => {
      const { at } = page(judgedFile);
      expect(at(11).length).toBe(1);
      expect(at(31).length).toBe(1);
    });
  });
});

// The viewer controls on the mimic player: pin, pause while the person writes a reason, and quiet mode.
describe("The viewer controls on the mimic player: pin, pause while the person writes a reason, and quiet mode.", () => {
  const flag = (id: string, t: number, confidence: number) => ({
    id, t, speaker: "Invitado", quote: `frase ${t}`, type: "fallacy", label: "ad_hominem", reason: "Ataca.",
    confidence, related: null, sources: [], note: null,
  });

  function page(flags: object[], paused = true) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "paused", { value: paused, configurable: true });
    video.pause = vi.fn();
    video.play = vi.fn();
    const file = { video_id: "abc", published_at: null, status: "done", stop_reason: null, flags } as any;
    const overlay = mountOverlay(player, video, () => file, () => {});
    mountPanel(overlay.layer, video, () => file, overlay.show);
    const playTo = (t: number) => {
      Object.defineProperty(video, "currentTime", { value: t, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));
    };
    const cards = () => [...player.querySelectorAll<HTMLElement>(".fc-card")];
    const button = (text: string) => [...player.querySelectorAll("button")].find((b) => b.textContent!.includes(text))!;
    return { player, video, playTo, cards, button };
  }

  describe("pin", () => {
    it("a pinned card stays past its seconds; its ✕ closes it", () => {
      const { playTo, cards } = page([flag("a", 10, 0.9)]);
      playTo(11);
      cards()[0].querySelector<HTMLElement>(".fc-pin")!.click();
      playTo(60);
      expect(cards().length).toBe(1);
      cards()[0].querySelector<HTMLElement>(".fc-pin")!.click();
      expect(cards().length).toBe(0);
    });

    it("P pins the newest card and never reaches YouTube", () => {
      const { playTo, cards } = page([flag("a", 10, 0.9), flag("b", 12, 0.9)]);
      const reached = vi.fn();
      window.addEventListener("keydown", reached, true);
      playTo(13);
      document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "p", bubbles: true }));
      expect(reached).not.toHaveBeenCalled();
      playTo(60);
      expect(cards().map((c) => c.textContent)).toEqual([expect.stringContaining("frase 12")]);
    });
  });

  describe("pause on ✗", () => {
    it("a playing video pauses for the reason and plays on after Guardar", () => {
      const { video, playTo, button } = page([flag("a", 10, 0.9)], false);
      playTo(11);
      button("✗ No").click();
      expect(video.pause).toHaveBeenCalledOnce();
      button("Guardar").click();
      expect(video.play).toHaveBeenCalledOnce();
    });

    it("a paused video stays paused after Cancelar", () => {
      const { video, playTo, button } = page([flag("a", 10, 0.9)], true);
      playTo(11);
      button("✗ No").click();
      button("Cancelar").click();
      expect(video.play).not.toHaveBeenCalled();
      expect(button("✗ No")).toBeDefined();
    });
  });

  it("quiet mode hides a 0.85 card on the player and keeps it in the panel", () => {
    const { player, playTo, cards, button } = page([flag("a", 10, 0.85)]);
    button("⚙").click();
    const quiet = player.querySelector<HTMLInputElement>(".fc-settings input[type=checkbox]")!;
    quiet.checked = true;
    quiet.dispatchEvent(new Event("change"));
    playTo(11);
    expect(cards().length).toBe(0);
    expect(player.querySelectorAll(".fc-row").length).toBe(1);
  });
});

// The ✕ closes a card under the mouse, the text size also sizes the feed, and the strip and the Avisos button
// hide with YouTube's controls.
describe("The ✕ closes a card under the mouse; the text size also sizes the feed; the strip hides with the controls.", () => {
  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    const file = { video_id: "x", status: "done", flags: [{ id: "a", t: 10, speaker: "s", quote: "q", type: "fallacy",
      label: "ad_hominem", reason: "r", confidence: 0.9, on_player: true, related: null, sources: [], note: null }] } as any;
    const overlay = mountOverlay(player, video, () => file, () => {});
    mountPanel(overlay.layer, video, () => file, overlay.show);
    Object.defineProperty(video, "currentTime", { value: 11, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    return player;
  }

  it("the ✕ closes a card that is under the mouse", () => {
    const player = page();
    const card = player.querySelector(".fc-card")!;
    card.dispatchEvent(new Event("pointerenter", { bubbles: true }));
    card.querySelector<HTMLElement>(".fc-close")!.click();
    expect(player.querySelectorAll(".fc-card").length).toBe(0);
  });

  it("the text size also sizes the feed", () => {
    const player = page();
    [...player.querySelectorAll("button")].find((b) => b.textContent === "⚙")!.click();
    [...player.querySelectorAll<HTMLButtonElement>(".fc-settings button")].find((b) => b.textContent === "L")!.click();
    expect(player.querySelector<HTMLElement>(".fc-panel")!.style.zoom).toBe("1.25");
  });

  it("the strip and the Avisos button hide while YouTube hides its controls", () => {
    const style = page().querySelector(".fc-layer style")!.textContent!;
    expect(style).toMatch(/\.ytp-autohide [^{]*\.fc-strip/);
    expect(style).toMatch(/\.ytp-autohide [^{]*\.fc-panel-tab/);
  });

  it("the cards move to the left while the Avisos panel is open on the right", () => {
    const player = page();
    const cards = () => player.querySelector<HTMLElement>(".fc-card")!.parentElement!;
    const tab = player.querySelector<HTMLElement>(".fc-panel-tab")!;
    expect(cards().style.right).toBe("12px");
    tab.click();
    expect([cards().style.left, cards().style.right]).toEqual(["12px", ""]);
    tab.click();
    expect(cards().style.right).toBe("12px");
  });
});

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
describe("S40 A3 · ⚙ → Claves opens the helper's key page", () => {
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
