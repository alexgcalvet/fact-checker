// S4 A2 · A card under the mouse stays until the person is done
//
// Story: On the mimic player, a card shows at second 42. The person moves the mouse over it at second 49
// and starts typing a reason; at second 55 the card is still there. When the mouse leaves, the card goes.
//
// Setup: a jsdom page with a player and a video, the overlay mounted with one flag at second 42 and a mark
// callback; playback is moved by setting the video time and firing "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const flagFile = {
  video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
    label: "ad_hominem", reason: "Ataca.", confidence: 0.55, on_player: true, related: null, sources: [], note: null }],
} as any;

describe("S4 A2 · A card under the mouse stays until the person is done", () => {
  it("Case 1 · mouse over the card at 49 → still there at 55; mouse out → gone", () => {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile, () => {});
    const playTo = (t: number) => {
      Object.defineProperty(video, "currentTime", { value: t, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));
    };

    playTo(49);
    const card = player.querySelector(".fc-card")!;
    expect(card).not.toBeNull();
    card.dispatchEvent(new Event("pointerenter", { bubbles: true }));
    playTo(55);
    expect(player.querySelectorAll(".fc-card").length).toBe(1);

    card.dispatchEvent(new Event("pointerleave", { bubbles: true }));
    playTo(55.5);
    expect(player.querySelectorAll(".fc-card").length).toBe(0);
  });
});
