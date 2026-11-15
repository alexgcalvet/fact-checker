// S3 A4 (extension part) · Only flags above their type's bar reach the player
//
// Story: On the mimic player page, a 0.55 fallacy that the helper marked for the player shows its card,
// and a 0.85 inaccuracy that it did not mark shows none. The helper part is test_s3_a4_on_player.py;
// s3-a4-bar-per-type.sh runs both.
//
// Setup: a jsdom page with a player and a video, the overlay mounted with a fixed flag file whose two
// flags start at second 20; playback is moved to second 21.
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const flagFile = {
  video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [
    { id: "a", t: 20, speaker: "guest", quote: "eso es lo que dicen los datos", type: "fallacy", label: "vague_authority",
      reason: "Vago.", confidence: 0.55, on_player: true, related: null, sources: [], note: null },
    { id: "b", t: 20, speaker: "guest", quote: "el paro juvenil se duplicó", type: "inaccuracy", label: "false",
      reason: "No.", confidence: 0.85, on_player: false, related: null,
      sources: [{ publisher: "INE", url: "https://www.ine.es/x", date: "2025-10-28" }], note: null },
  ],
} as any;

describe("S3 A4 · Only flags above their type's bar reach the player", () => {
  it("Case 1 · marked 0.55 fallacy → its card shows; unmarked 0.85 inaccuracy → no card", () => {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile);
    Object.defineProperty(video, "currentTime", { value: 21, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    const cards = player.querySelectorAll(".fc-card");
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("eso es lo que dicen los datos");
    expect(player.textContent).not.toContain("el paro juvenil se duplicó");
  });
});
