// S13 A2 · The strip shows the analysed part
//
// Story: On a page that mimics the YouTube player, a 100-second video has a flag file analysed until second 40
// and still running. The strip under the video shows the first 40 % as analysed and the rest as pending; when
// the file says done, the whole strip is analysed.
//
// Setup: a jsdom page with a player element and a video element whose duration is 100 seconds; the overlay and
// the panel are mounted as the content script mounts them, with a flag file of one flag at second 10 that the
// test changes between the cases, as the poll of the content script does.
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const running = () => ({
  video_id: "abc", published_at: "2026-11-10", status: "running", stop_reason: null, analysed_until: 40,
  flags: [{ id: "fallacy-10.0", t: 10, speaker: "Invitado", quote: "frase 10", type: "fallacy", label: "ad_hominem",
    reason: "Motivo.", confidence: 0.85, on_player: true, related: null, sources: [], note: null }],
}) as any;

function page() {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
  let flagFile = running();
  const overlay = mountOverlay(player, video, () => flagFile, () => {});
  mountPanel(overlay.layer, video, () => flagFile, overlay.show);
  const strip = (cls: string) => player.querySelector<HTMLElement>(`.fc-strip .${cls}`);
  const poll = (change: object) => {
    flagFile = { ...flagFile, ...change };
    video.dispatchEvent(new Event("timeupdate"));
  };
  return { strip, poll };
}

describe("S13 A2 · The strip shows the analysed part", () => {
  // Case 1 · running, analysed until second 40 of 100 → the first 40 % analysed, the other 60 % pending
  it("Case 1 · running, analysed until second 40 of 100 → 40 % analysed, 60 % pending", () => {
    const { strip } = page();
    expect(parseFloat(strip("fc-analysed")!.style.width)).toBe(40);
    expect(parseFloat(strip("fc-pending")!.style.left)).toBe(40);
    expect(parseFloat(strip("fc-pending")!.style.width)).toBe(60);
  });

  // Case 2 · the next poll says analysed until second 70 → the analysed part grows to 70 %
  it("Case 2 · the next poll says analysed until second 70 → 70 % analysed", () => {
    const { strip, poll } = page();
    poll({ analysed_until: 70 });
    expect(parseFloat(strip("fc-analysed")!.style.width)).toBe(70);
  });

  // Case 3 · the file says done → the whole strip analysed, nothing pending
  it("Case 3 · the file says done → the whole strip analysed", () => {
    const { strip, poll } = page();
    poll({ status: "done" });
    expect(parseFloat(strip("fc-analysed")!.style.width)).toBe(100);
    expect(parseFloat(strip("fc-pending")?.style.width ?? "0")).toBe(0);
  });

  // Case 4 · the flag mark still sits on the strip, over the analysed part → one mark at 10 %
  it("Case 4 · the flag mark still sits on the strip → one mark at 10 %", () => {
    const { strip } = page();
    expect(parseFloat(strip("fc-mark")!.style.left)).toBe(10);
  });
});
