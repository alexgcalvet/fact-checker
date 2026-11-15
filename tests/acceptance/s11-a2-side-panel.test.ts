// S11 A2 · The side panel lists every flag, under the bar too
//
// Story: On the same page, the person sees a closed "Avisos (3)" tab at the side of the player and opens it.
// The panel lists the three flags in time order, each with its minute, its name and its quote; the one under
// the bar is shown greyed.
//
// Setup: a jsdom page with a player element and a 100-second video; the overlay and the panel are mounted as
// the content script mounts them, with a fixed flag file of three flags out of time order: a contradiction at
// second 90, a fallacy at second 10 and an inaccuracy under the bar at second 50.
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
