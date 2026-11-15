// S14 A3 · The person exports the summary from the side panel
//
// Story: On a page that mimics the YouTube player, the person opens the side panel and clicks "Exportar
// resumen". The extension asks the helper for the summary of that video and opens the PNG in a new tab, with
// the alt text ready to copy under it.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel are mounted as the
// content script mounts them, with a fixed flag file of one flag and an export callback that counts its calls.
// For the service worker, a stub `chrome` global records the message listener and each tab it opens. The page
// that the new tab shows (image and alt text) is checked in s14-a2-summary-png.sh, case 3.
// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

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
