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
// The content script runs as on YouTube. What the helper shares is checked in test_s30_a2_consent_first.py.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

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
