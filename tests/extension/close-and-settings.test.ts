// @vitest-environment jsdom
// The ✕ closes a card under the mouse, the text size also sizes the feed, and the strip and the Avisos button
// hide with YouTube's controls.
import { expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

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
