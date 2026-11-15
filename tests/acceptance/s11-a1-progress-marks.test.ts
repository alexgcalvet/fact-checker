// S11 A1 · Every flag has a mark at its second on a strip under the video
//
// Story: On a page that mimics the YouTube player, a 100-second video has three flags at seconds 10, 50 and 90,
// one of them under the bar. The strip under the video shows three marks, at 10 %, 50 % and 90 % of its width,
// each with the color of its type.
//
// Setup: a jsdom page with a player element and a video element whose duration is 100 seconds; the overlay
// and the panel are mounted as the content script mounts them, with a fixed flag file of three flags: a fallacy
// at second 10, an inaccuracy under the bar at second 50 and a contradiction at second 90.
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel, TYPE_COLOR } from "../../src/extension/src/panel";

const flag = (id: string, t: number, type: string, label: string, onPlayer: boolean) => ({
  id, t, speaker: "Invitado", quote: `frase ${t}`, type, label, reason: "Motivo.", confidence: 0.85,
  on_player: onPlayer, related: null, sources: [], note: null,
});
const flagFile = {
  video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [
    flag("fallacy-10.0", 10, "fallacy", "ad_hominem", true),
    flag("inaccuracy-50.0", 50, "inaccuracy", "false", false),
    flag("contradiction-90.0", 90, "contradiction", "self", true),
  ],
} as any;

function marks() {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
  const overlay = mountOverlay(player, video, () => flagFile, () => {});
  mountPanel(overlay.layer, video, () => flagFile, overlay.show);
  return [...player.querySelectorAll<HTMLElement>(".fc-strip .fc-mark")];
}

/** The color as the browser reports it, so "#f5a623" and "rgb(245, 166, 35)" compare equal. */
function computed(color: string) {
  const probe = document.createElement("div");
  probe.style.backgroundColor = color;
  return probe.style.backgroundColor;
}

describe("S11 A1 · Every flag has a mark at its second on a strip under the video", () => {
  // Case 1 · three flags on a 100-second video → three marks at 10 %, 50 % and 90 % of the strip
  it("Case 1 · three flags on a 100-second video → three marks at 10 %, 50 % and 90 %", () => {
    const found = marks();
    expect(found.length).toBe(3);
    expect(found.map((m) => parseFloat(m.style.left)).sort((a, b) => a - b)).toEqual([10, 50, 90]);
  });

  // Case 2 · each mark → the color of its flag's type
  it("Case 2 · each mark → the color of its flag's type", () => {
    const byLeft = Object.fromEntries(marks().map((m) => [parseFloat(m.style.left), m.style.backgroundColor]));
    expect(new Set([byLeft[10], byLeft[50], byLeft[90]]).size).toBe(3);
    expect(byLeft[10]).not.toBe("");
    expect(byLeft[10]).toBe(computed(TYPE_COLOR.fallacy));
    expect(byLeft[50]).toBe(computed(TYPE_COLOR.inaccuracy));
    expect(byLeft[90]).toBe(computed(TYPE_COLOR.contradiction));
  });

  // Case 3 · the flag under the bar → a thinner mark than the shown flags
  it("Case 3 · the flag under the bar → a thinner mark than the shown flags", () => {
    const width = Object.fromEntries(marks().map((m) => [parseFloat(m.style.left), parseFloat(m.style.width)]));
    expect(width[50]).toBeLessThan(width[10]);
    expect(width[50]).toBeLessThan(width[90]);
  });
});
