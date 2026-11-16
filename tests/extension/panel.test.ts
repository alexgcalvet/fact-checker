// @vitest-environment jsdom
// The side panel: the list of flags, the feed that follows playback, the speakers, the export and the analysis state.
import { afterEach, describe, expect, it, vi } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

// S11 A2 · The side panel lists every flag, under the bar too
//
// Story: On the same page, the person sees a closed "Avisos (3)" tab at the side of the player and opens it.
// The panel lists the three flags in time order, each with its minute, its name and its quote; the one under
// the bar is shown greyed.
//
// Setup: a jsdom page with a player element and a 100-second video; the overlay and the panel are mounted as
// the content script mounts them, with a fixed flag file of three flags out of time order: a contradiction at
// second 90, a fallacy at second 10 and an inaccuracy under the bar at second 50.
{
  const flag = (id: string, t: number, type: string, label: string, onPlayer: boolean) => ({
    id, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type, label, reason: "Motivo.", confidence: 0.85,
    on_player: onPlayer, related: null, sources: [], note: null,
  });
  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [
      flag("contradiction-90.0", 90, "contradiction", "self", true),
      flag("fallacy-10.0", 10, "fallacy", "ad_hominem", true),
      flag("inaccuracy-50.0", 50, "inaccuracy", "false", false),
    ],
  } as any;

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show);
    const tab = player.querySelector<HTMLElement>(".fc-panel-tab")!;
    const panel = player.querySelector<HTMLElement>(".fc-panel")!;
    return { tab, panel };
  }

  describe("S11 A2 · The side panel lists every flag, under the bar too", () => {
    // Case 1 · the page loads → a closed "Avisos (3)" tab inside our layer
    it("Case 1 · the page loads → a closed \"Avisos (3)\" tab inside our layer", () => {
      const { tab, panel } = page();
      expect(tab.textContent).toContain("Avisos (3)");
      expect(tab.closest(".fc-layer")).not.toBeNull();
      expect(panel.closest(".fc-layer")).not.toBeNull();
      expect(panel.style.display).toBe("none");
    });

    // Case 2 · the person opens the tab → three rows in time order with minute, name and quote
    it("Case 2 · the person opens the tab → three rows in time order with minute, name and quote", () => {
      const { tab, panel } = page();
      tab.click();
      expect(panel.style.display).not.toBe("none");
      const rows = [...panel.querySelectorAll<HTMLElement>(".fc-row")].map((r) => r.textContent!);
      expect(rows.length).toBe(3);
      expect(rows[0]).toContain("0:10");
      expect(rows[0]).toContain("Ad hominem");
      expect(rows[0]).toContain("frase del segundo 10");
      expect(rows[1]).toContain("0:50");
      expect(rows[1]).toContain("Dato falso");
      expect(rows[1]).toContain("frase del segundo 50");
      expect(rows[2]).toContain("1:30");
      expect(rows[2]).toContain("Contradicción");
      expect(rows[2]).toContain("frase del segundo 90");
    });

    // Case 3 · the flag under the bar → its row is greyed, the others are not
    it("Case 3 · the flag under the bar → its row is greyed, the others are not", () => {
      const { tab, panel } = page();
      tab.click();
      const opacity = [...panel.querySelectorAll<HTMLElement>(".fc-row")].map((r) => Number(r.style.opacity || 1));
      expect(opacity[1]).toBeLessThan(1);
      expect(opacity[0]).toBe(1);
      expect(opacity[2]).toBe(1);
    });
  });
}

// S14 A3 · The person exports the summary from the side panel
//
// Story: On a page that mimics the YouTube player, the person opens the side panel and clicks "Exportar
// resumen". The extension asks the helper for the summary of that video and opens the PNG in a new tab, with
// the alt text ready to copy under it.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel are mounted as the
// content script mounts them, with a fixed flag file of one flag and an export callback that counts its calls.
// For the service worker, a stub `chrome` global records the message listener and each tab it opens. The page
// that the new tab shows (image and alt text) is checked in tests/helper/test_summary.py.
{
  const flagFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{ id: "fallacy-10.0", t: 10, speaker: "Invitado", quote: "frase 10", type: "fallacy", label: "ad_hominem",
      reason: "Motivo.", confidence: 0.85, on_player: true, related: null, sources: [], note: null, mark: "correct" }],
  } as any;

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
    let exports = 0;
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show, () => { exports += 1; });
    player.querySelector<HTMLElement>(".fc-panel-tab")!.click();
    const exportButton = [...player.querySelectorAll<HTMLButtonElement>(".fc-panel button")]
      .find((b) => b.textContent === "Exportar resumen");
    return { exportButton, exports: () => exports };
  }

  async function serviceWorker() {
    let listener: (req: unknown, sender: unknown, respond: (r: unknown) => void) => unknown = () => {};
    const tabs: { url: string }[] = [];
    vi.resetModules();
    vi.stubGlobal("chrome", {
      runtime: { onMessage: { addListener: (fn: typeof listener) => { listener = fn; } } },
      tabs: { create: async (props: { url: string }) => { tabs.push(props); return {}; } },
    });
    await import("../../src/extension/src/sw");
    const send = (req: unknown) => new Promise((resolve) => {
      if (listener(req, {}, resolve) !== true) resolve(undefined);
    });
    return { send, tabs };
  }

  describe("S14 A3 · The person exports the summary from the side panel", () => {
    it("Case 1 · the panel is open → it shows \"Exportar resumen\"; a click asks for the summary once", () => {
      const { exportButton, exports } = page();
      expect(exportButton).toBeDefined();
      exportButton!.click();
      expect(exports()).toBe(1);
    });

    it("Case 2 · the service worker gets a summary request → it opens the helper's summary page in a new tab", async () => {
      const { send, tabs } = await serviceWorker();
      const reply = await send({ kind: "summary", videoId: "abcdefgh" });
      expect(tabs).toEqual([{ url: "http://127.0.0.1:8765/videos/abcdefgh/summary" }]);
      expect(reply).toMatchObject({ ok: true });
    });

    it("Case 3 · a summary request with a bad video id → no tab opens", async () => {
      const { send, tabs } = await serviceWorker();
      await send({ kind: "summary", videoId: "../etc" });
      expect(tabs).toEqual([]);
    });
  });
}

// S15 A2 · The player and the panel follow the judge unless the person marked the flag
//
// Story: On a page that mimics the YouTube player, the flag file has a kept fallacy, a false figure judged
// "puntualización", a dropped flag and a dropped flag the person marked correct. The fallacy shows as usual; the
// "puntualización" shows as a small grey card titled "Puntualización" with the judge's reason; the dropped flag
// never shows on the player and appears struck through in the panel as "Descartado por el juez"; the flag marked
// correct shows as found.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel mounted as the content
// script mounts them, with a fixed flag file of four flags on the player: a fallacy at second 10 (judge: keep), a
// false figure at second 30 (judge: nitpick), a false figure at second 50 (judge: drop) and a false figure at
// second 70 (judge: drop, marked correct). Playback moves to one second after each flag.
{
  const NITPICK = "49,8 M frente a 49,4 M, el fondo se sostiene";
  const flag = (id: string, t: number, type: string, label: string, judge: object, mark?: string) => ({
    id, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type, label, reason: `Motivo del segundo ${t}.`,
    confidence: 0.9, on_player: true, related: null, sources: [], note: null, judge, ...(mark ? { mark } : {}),
  });
  const flagFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [
      flag("ad_hominem-10.0", 10, "fallacy", "ad_hominem", { verdict: "keep", reason: "Se sostiene." }),
      flag("false-30.0", 30, "inaccuracy", "false", { verdict: "nitpick", reason: NITPICK }),
      flag("false-50.0", 50, "inaccuracy", "false", { verdict: "drop", reason: "El propio orador lo corrige." }),
      flag("false-70.0", 70, "inaccuracy", "false", { verdict: "drop", reason: "Error menor." }, "correct"),
    ],
  } as any;

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    let now = 0;
    Object.defineProperty(video, "currentTime", { get: () => now, set: (t) => { now = t; }, configurable: true });
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show);
    const at = (t: number) => {
      now = t;
      video.dispatchEvent(new Event("timeupdate"));
      return [...player.querySelectorAll<HTMLElement>(".fc-card")];
    };
    const row = (t: number) => [...player.querySelectorAll<HTMLElement>(".fc-row")]
      .find((r) => r.textContent!.includes(`frase del segundo ${t}`))!;
    return { at, row };
  }

  /** True when the colour is a grey: its red, green and blue are within 24 of each other. */
  function grey(css: string): boolean {
    const hex = css.match(/#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i);
    const dec = css.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    const rgb = hex ? hex.slice(1).map((h) => parseInt(h, 16)) : dec ? dec.slice(1).map(Number) : null;
    if (!rgb) return false;
    return Math.max(...rgb) - Math.min(...rgb) <= 24;
  }

  describe("S15 A2 · The player and the panel follow the judge unless the person marked the flag", () => {
    // Case 1 · the kept fallacy at its second → its usual card
    it("Case 1 · the kept fallacy at its second → its usual card", () => {
      const { at } = page();
      const cards = at(11);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Ad hominem");
      expect(cards[0].textContent).toContain("Motivo del segundo 10.");
    });

    // Case 2 · the false figure judged "puntualización" → a grey card titled "Puntualización" with the judge's reason
    it("Case 2 · the \"puntualización\" → a grey card titled \"Puntualización\" with the judge's reason", () => {
      const { at } = page();
      const cards = at(31);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Puntualización");
      expect(cards[0].textContent).toContain(NITPICK);
      expect(cards[0].textContent).not.toContain("Dato falso");
      expect(grey(cards[0].style.borderLeft || cards[0].style.borderColor)).toBe(true);
    });

    // Case 3 · the dropped flag at its second → no card on the player
    it("Case 3 · the dropped flag at its second → no card on the player", () => {
      const { at } = page();
      expect(at(51).length).toBe(0);
    });

    // Case 4 · the dropped flag in the panel → struck through, with "Descartado por el juez"
    it("Case 4 · the dropped flag in the panel → struck through, with \"Descartado por el juez\"", () => {
      const { row } = page();
      const dropped = row(50);
      expect(dropped.textContent).toContain("Descartado por el juez");
      const struck = [dropped, ...dropped.querySelectorAll<HTMLElement>("*")]
        .some((el) => el.style.textDecoration.includes("line-through") && el.textContent!.includes("frase del segundo 50"));
      expect(struck).toBe(true);
    });

    // Case 5 · the dropped flag the person marked correct → its card as found, and a plain row in the panel
    it("Case 5 · the dropped flag marked correct → its card as found, and a plain row", () => {
      const { at, row } = page();
      const cards = at(71);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Dato falso");
      expect(cards[0].textContent).toContain("Motivo del segundo 70.");
      const plain = row(70);
      expect(plain.textContent).not.toContain("Descartado por el juez");
      expect([plain, ...plain.querySelectorAll<HTMLElement>("*")].some((el) => el.style.textDecoration.includes("line-through"))).toBe(false);
    });
  });
}

// S31 A3 · The panel says the analysis is being prepared, or why it stopped
//
// Story: A person clicks "Analizar este vídeo". Until the first part is read, the panel tab says "Preparando el
// análisis…" ("Preparing the analysis…" in English), then "Avisos (1)". If the analysis stops because YouTube gave no
// captions, the player shows "El análisis se paró: YouTube no dio los subtítulos. Vuelve a intentarlo en unos minutos."
// and the "Analizar este vídeo" button shows again.
// Edge case: WHEN the analysis stopped because it spent its budget THEN the button does not show again.
//
// Setup: a jsdom page with a player element and a 100-second video; the browser language set per case
// (navigator.language). The overlay and the panel are mounted as the content script mounts them, with a flag file that
// the test changes between the cases, as the poll of the content script does: a running analysis with no part read
// yet (no `first_flags_s`), then one flag and `first_flags_s`, then an analysis stopped by a failed captions download
// (the helper's `stop_reason` from yt-dlp). For the button, the content script itself runs on a watch page against a
// fake service worker that answers with a stopped flag file, with fake timers.
describe("S31 A3 · The panel says the analysis is being prepared, or why it stopped", () => {
  const FLAG = { id: "ad_hominem-10.0", t: 10, speaker: "Invitado", quote: "usted miente siempre", type: "fallacy",
    label: "ad_hominem", reason: "Ataca.", confidence: 0.9, on_player: true, related: null, sources: [], note: null };
  const WAITING = { video_id: "abcdefgh", published_at: null, status: "running", stop_reason: null, analysed_until: 0,
    flags: [] };
  const YT_DLP = "error: Command '['yt-dlp', '--no-simulate', '--skip-download']' returned non-zero exit status 1.";

  afterEach(() => { vi.unstubAllGlobals(); });

  async function page(language: string) {
    Object.defineProperty(navigator, "language", { value: language, configurable: true });
    vi.stubGlobal("chrome", { storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } } });
    vi.resetModules();
    const { mountOverlay } = await import("../../src/extension/src/overlay");
    const { mountPanel } = await import("../../src/extension/src/panel");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
    let flagFile: any = { ...WAITING };
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show);
    const poll = (change: object) => {
      flagFile = { ...flagFile, ...change };
      video.dispatchEvent(new Event("timeupdate"));
    };
    const tab = () => player.querySelector<HTMLElement>(".fc-panel-tab")!.textContent!;
    return { player, poll, tab };
  }

  describe("S31 A3 · The panel says the analysis is being prepared, or why it stopped", () => {
    // Case 1 · running, no part read yet → "Preparando el análisis…", not "Avisos (0)"
    // Case 2 · the first part is read, with one flag → "Avisos (1)"
    it("Case 1-2 · Spanish: \"Preparando el análisis…\" until the first part, then \"Avisos (1)\"", async () => {
      const { tab, poll } = await page("es-ES");
      expect(tab()).toContain("Preparando el análisis…");
      expect(tab()).not.toContain("(0)");
      poll({ first_flags_s: 12.3, analysed_until: 30, flags: [FLAG] });
      expect(tab()).toContain("Avisos (1)");
      expect(tab()).not.toContain("Preparando");
    });

    // Case 3 · an English browser → "Preparing the analysis…"
    it("Case 3 · English: \"Preparing the analysis…\"", async () => {
      const { tab } = await page("en-US");
      expect(tab()).toContain("Preparing the analysis…");
    });

    // Case 4 · the analysis stops because yt-dlp failed → the player shows the reason in one Spanish line
    it("Case 4 · stopped by a failed captions download → the Spanish reason line on the player", async () => {
      const { player, poll } = await page("es-ES");
      poll({ status: "stopped", stop_reason: YT_DLP });
      const line = player.querySelector<HTMLElement>(".fc-stopped")?.textContent;
      expect(line).toBe("El análisis se paró: YouTube no dio los subtítulos. Vuelve a intentarlo en unos minutos.");
    });

    // Case 5 · a running or done analysis → no stop line
    it("Case 5 · running or done → no stop line", async () => {
      const { player, poll } = await page("es-ES");
      expect(player.querySelector(".fc-stopped")).toBeNull();
      poll({ status: "done", first_flags_s: 3, flags: [FLAG] });
      expect(player.querySelector(".fc-stopped")).toBeNull();
    });

    // Case 6 · a done analysis with no first_flags_s (a shared copy drops it) → "Avisos (1)", never "Preparando"
    it("Case 6 · done, no first_flags_s → \"Avisos (1)\"", async () => {
      const { tab, poll } = await page("es-ES");
      poll({ status: "done", source: "shared", flags: [FLAG] });
      expect(tab()).toContain("Avisos (1)");
      expect(tab()).not.toContain("Preparando");
    });

    // Case 7 · the video opens with an analysis stopped by an error → the button shows again; a click asks to analyse
    // Case 8 · stopped because the budget ran out → no button
    it("Case 7-8 · stopped by an error → the button shows again and analyses; stopped by the budget → no button", async () => {
      Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });
      vi.useFakeTimers();
      try {
        for (const [reason, shows] of [[YT_DLP, true], ["budget", false]] as const) {
          const sent: any[] = [];
          const file = { ...WAITING, status: "stopped", stop_reason: reason };
          const reply = (m: any) => (m.kind === "share" || m.kind === "set-share" ? { share: false } : file);
          vi.stubGlobal("chrome", {
            runtime: { id: "x", sendMessage: vi.fn(async (m: any) => { sent.push(m); return { ok: true, data: reply(m) }; }),
              onMessage: { addListener: () => {} } },
            storage: { local: { get: vi.fn(async () => ({ share: false })), set: vi.fn(async () => {}) } },
          });
          vi.resetModules();
          history.pushState({}, "", "/watch?v=abcdefgh");
          document.body.innerHTML = '<div id="movie_player"><video></video></div>';
          await import("../../src/extension/src/content");
          await vi.advanceTimersByTimeAsync(0);
          const button = [...document.querySelectorAll("button")].find((b) => b.textContent === "Analizar este vídeo");
          expect(Boolean(button), reason).toBe(shows);
          if (!button) continue;
          button.click();
          await vi.advanceTimersByTimeAsync(0);
          expect(sent.some((m) => m.kind === "analyze" && m.videoId === "abcdefgh")).toBe(true);
        }
      } finally {
        vi.useRealTimers();
      }
    });
  });
});

// S33 A4 · The side panel lists the speakers and switches a role
//
// Story: The person opens the side panel of the interview. Under the filters it lists "Presentador · Host" and
// "Ana Ruiz · Invitada". A click on the role of the host turns it into Invitada, and the helper is told.
//
// Setup: a jsdom watch page with a player and a video, fake timers, the browser language set per case, and a stub
// `chrome` whose service worker answers with an analysed flag file: one flag, the voices "Presentador" (people: host)
// and "Ana Ruiz (invitada)" (people: guest, person "Ana Ruiz"); it records each message. The content script runs as on
// YouTube and the test opens the side panel. Then the real service worker gets a `role` message while a stub `fetch`
// records each request. What the helper does with it is checked in tests/helper/test_summary.py (S33 A3).
describe("S33 A4 · The side panel lists the speakers and switches a role", () => {
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
});

// The feed counts only what stands; the flags the judge dropped wait folded at its end.
describe("The feed counts only what stands; the flags the judge dropped wait folded at its end.", () => {
  const flag = (id: string, t: number, judge?: object) => ({ id, t, speaker: "s", quote: `frase ${t}`, type: "inaccuracy",
    label: "false", reason: "r", confidence: 0.9, on_player: true, related: null, sources: [], note: null, judge });

  it("counts leave out dropped flags, which sit folded after the rest", () => {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    const file = { video_id: "x", status: "done", flags: [flag("a", 10), flag("b", 20, { verdict: "drop", reason: "cierto" }),
      flag("c", 30), flag("d", 40, { verdict: "drop", reason: "cierto" })] } as any;
    const overlay = mountOverlay(player, video, () => file, () => {});
    mountPanel(overlay.layer, video, () => file, overlay.show);
    expect(player.querySelector(".fc-panel-tab")!.textContent).toContain("Avisos (2)");
    const falsos = [...player.querySelectorAll(".fc-flt button")].find((b) => b.textContent!.includes("Falsos"))!;
    expect(falsos.textContent).toContain("2");
    const folded = player.querySelector<HTMLDetailsElement>(".fc-dropped")!;
    expect(folded.open).toBe(false);
    expect(folded.querySelector("summary")!.textContent).toContain("Descartados por el juez (2)");
    expect([...folded.querySelectorAll(".fc-row")].map((r) => r.textContent!.includes("frase 20") || r.textContent!.includes("frase 40")))
      .toEqual([true, true]);
  });
});

// The feed lights the row at the playhead with its reason, follows the playhead, and offers "Ir al directo"
// once the person scrolls it.
describe("The feed lights the row at the playhead with its reason, follows the playhead, and offers \"Ir al directo\"", () => {
  const flag = (t: number) => ({
    id: `f-${t}`, t, speaker: "Invitado", quote: `frase ${t}`, type: "inaccuracy", label: "false",
    reason: `Motivo ${t}.`, confidence: 0.8, on_player: true, related: null, note: null,
    sources: [{ publisher: "INE", url: "https://ine.es/x", date: "2024" }],
  });

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    const file = { video_id: "abc", published_at: null, status: "done", stop_reason: null, flags: [flag(10), flag(50)] } as any;
    const overlay = mountOverlay(player, video, () => file, () => {});
    mountPanel(overlay.layer, video, () => file, overlay.show);
    const playTo = (t: number) => {
      Object.defineProperty(video, "currentTime", { value: t, writable: true, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));
    };
    const row = (t: number) => [...player.querySelectorAll<HTMLElement>(".fc-row")].find((r) => r.textContent!.includes(`frase ${t}`))!;
    const jump = player.querySelector<HTMLElement>(".fc-jump")!;
    return { player, playTo, row, jump };
  }

  it("only the row at the playhead shows its reason, its sources and its confidence", () => {
    const { playTo, row } = page();
    playTo(12);
    expect(row(10).textContent).toContain("Motivo 10.");
    expect(row(10).textContent).toContain("1 fuente");
    expect(row(10).textContent).toContain("80%");
    playTo(55);
    expect(row(10).textContent).not.toContain("Motivo 10.");
    expect(row(50).textContent).toContain("Motivo 50.");
  });

  it("a scroll by the person shows Ir al directo; a click on it hides it again", () => {
    const { player, jump } = page();
    expect(jump.hidden).toBe(true);
    player.querySelector(".fc-list")!.dispatchEvent(new Event("wheel"));
    expect(jump.hidden).toBe(false);
    expect(jump.textContent).toBe("Ir al directo");
    jump.click();
    expect(jump.hidden).toBe(true);
  });
});
