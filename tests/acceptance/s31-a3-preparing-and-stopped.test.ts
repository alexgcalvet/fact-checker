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
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

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
