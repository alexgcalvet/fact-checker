// S1 A4 · A card shows on the player at the flag's second
//
// Story: On a page that mimics the YouTube player, with a flag file that holds one flag at second 42
// with confidence 0.9 and one at second 50 with confidence 0.6, the person plays to second 42 and sees
// one card with the name, the words and "90%"; no card appears for the 0.6 flag.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file; playback is moved by setting the video time and firing "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const flagFile = {
  video_id: "abc",
  published_at: "2026-11-10",
  status: "done",
  stop_reason: null,
  flags: [
    { id: "f1", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad para hablar", type: "fallacy",
      label: "ad_hominem", reason: "Attacks the critic.", confidence: 0.9, related: null, sources: [], note: null },
    { id: "f2", t: 50, speaker: "guest", quote: "o esto o el caos", type: "fallacy",
      label: "false_dilemma", reason: "Two options only.", confidence: 0.6, related: null, sources: [], note: null },
  ],
};

function page() {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  mountOverlay(player, video, () => flagFile);
  const playTo = (t: number) => {
    Object.defineProperty(video, "currentTime", { value: t, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
  };
  return { player, playTo };
}

describe("S1 A4 · A card shows on the player at the flag's second", () => {
  it("Case 1 · before second 42 → no card", () => {
    const { player, playTo } = page();
    playTo(41);
    expect(player.querySelectorAll(".fc-card").length).toBe(0);
  });

  it("Case 2 · at second 42 → one card with the name, the words and 90%", () => {
    const { player, playTo } = page();
    playTo(42);
    const cards = player.querySelectorAll(".fc-card");
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Ad hominem");
    expect(cards[0].textContent).toContain("la oposición no tiene autoridad para hablar");
    expect(cards[0].textContent).toContain("90%");
  });

  it("Case 3 · at second 50, the 0.6 flag → no card for it", () => {
    const { player, playTo } = page();
    playTo(50);
    expect(player.textContent).not.toContain("o esto o el caos");
  });
});
