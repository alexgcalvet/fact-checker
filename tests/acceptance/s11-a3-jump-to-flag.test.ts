// S11 A3 · A click on a mark or a row jumps to the flag
//
// Story: On the same page, the person clicks the mark at 50 %. The video jumps to second 50 and the card of
// that flag shows, also if the flag is under the bar. A click on the row of the flag at second 90 jumps there
// the same way.
//
// Setup: a jsdom page with a player element and a 100-second video at second 0; the overlay and the panel are
// mounted as the content script mounts them, with a fixed flag file of three flags: a fallacy at second 10, an
// inaccuracy under the bar at second 50 and a contradiction at second 90.
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const flag = (id: string, t: number, type: string, label: string, onPlayer: boolean) => ({
  id, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type, label, reason: "Motivo.", confidence: 0.85,
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

function page() {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
  const overlay = mountOverlay(player, video, () => flagFile, () => {});
  mountPanel(overlay.layer, video, () => flagFile, overlay.show);
  const cards = () => [...player.querySelectorAll<HTMLElement>(".fc-card")].map((c) => c.textContent!);
  return { player, video, cards };
}

describe("S11 A3 · A click on a mark or a row jumps to the flag", () => {
  // Case 1 · click on the mark at 50 % → the video is at second 50 and the card of the flag under the bar shows
  it("Case 1 · click on the mark at 50 % → second 50 and the card of the flag under the bar", () => {
    const { player, video, cards } = page();
    const mark = [...player.querySelectorAll<HTMLElement>(".fc-mark")].find((m) => parseFloat(m.style.left) === 50)!;
    mark.click();
    expect(video.currentTime).toBe(50);
    video.dispatchEvent(new Event("seeked"));
    video.dispatchEvent(new Event("timeupdate"));
    expect(cards().length).toBe(1);
    expect(cards()[0]).toContain("frase del segundo 50");
  });

  // Case 2 · click on the row of the flag at second 90 → the video is at second 90 and its card shows
  it("Case 2 · click on the row at second 90 → second 90 and its card", () => {
    const { player, video, cards } = page();
    player.querySelector<HTMLElement>(".fc-panel-tab")!.click();
    const row = [...player.querySelectorAll<HTMLElement>(".fc-row")].find((r) => r.textContent!.includes("1:30"))!;
    row.click();
    expect(video.currentTime).toBe(90);
    video.dispatchEvent(new Event("seeked"));
    video.dispatchEvent(new Event("timeupdate"));
    expect(cards().length).toBe(1);
    expect(cards()[0]).toContain("frase del segundo 90");
  });

  // Case 3 · normal playback reaches second 52 with no click → no card for the flag under the bar
  // (a regression guard: the bar rule of normal playback must survive the jump)
  it("Case 3 · playback reaches second 52 with no click → no card for the flag under the bar", () => {
    const { video, cards } = page();
    video.currentTime = 52;
    video.dispatchEvent(new Event("timeupdate"));
    expect(cards().length).toBe(0);
  });
});
