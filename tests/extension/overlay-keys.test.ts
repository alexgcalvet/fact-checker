// @vitest-environment jsdom
// Typing a reason must not reach YouTube's keyboard shortcuts (k pauses, f goes full screen, digits seek).
import { expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

it("keys typed in the reason field do not reach the player", () => {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  const reached: string[] = [];
  for (const type of ["keydown", "keypress", "keyup"]) player.addEventListener(type, (e) => reached.push(e.type));
  const flags = { flags: [{ id: "a", t: 1, type: "fallacy", label: "ad_hominem", quote: "q", reason: "r",
    confidence: 0.9, on_player: true, sources: [], note: null }] } as any;
  mountOverlay(player, video, () => flags, () => {});
  Object.defineProperty(video, "currentTime", { value: 2, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  [...player.querySelectorAll("button")].find((b) => b.textContent!.includes("✗ No"))!.click();
  const input = player.querySelector(".fc-card input")!;
  for (const type of ["keydown", "keypress", "keyup"]) input.dispatchEvent(new KeyboardEvent(type, { key: "k", bubbles: true }));
  expect(reached).toEqual([]);
});
