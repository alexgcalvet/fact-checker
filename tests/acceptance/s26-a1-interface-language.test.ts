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
// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

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
