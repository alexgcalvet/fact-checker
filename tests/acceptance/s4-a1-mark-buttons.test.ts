// S4 A1 (extension part) · Marking a card keeps the mark on the laptop
//
// Story: On the mimic player, the person clicks "✗ No" on an ad hominem card, types "es una pregunta,
// no un ataque" and saves; the mark goes out with the flag, "unfair" and the reason. "✓ De acuerdo" sends
// "correct" at once. The helper part is test_s4_a1_mark_stored.py; s4-a1-mark-a-card.sh runs both.
//
// Setup: a jsdom page with a player and a video, the overlay mounted with one flag at second 42 and a
// mark callback that records what it gets; playback is moved to second 43.
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const flagFile = {
  video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
    label: "ad_hominem", reason: "Ataca.", confidence: 0.55, on_player: true, related: null, sources: [], note: null }],
} as any;

function page() {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  const sent: [string, string, string][] = [];
  mountOverlay(player, video, () => flagFile, (flag, verdict, reason) => { sent.push([flag.id, verdict, reason]); });
  Object.defineProperty(video, "currentTime", { value: 43, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  const button = (text: string) =>
    [...player.querySelectorAll("button")].find((b) => b.textContent!.includes(text)) as HTMLButtonElement;
  return { player, sent, button };
}

describe("S4 A1 · Marking a card keeps the mark on the laptop", () => {
  it("Case 1 · ✗ No, a reason, Guardar → the mark goes out as unfair with the reason", () => {
    const { player, sent, button } = page();
    button("✗ No").click();
    const input = player.querySelector(".fc-card input") as HTMLInputElement;
    expect(input).not.toBeNull();
    input.value = "es una pregunta, no un ataque";
    button("Guardar").click();
    expect(sent).toEqual([["ad_hominem-42.0", "unfair", "es una pregunta, no un ataque"]]);
  });

  it("Case 2 · ✓ De acuerdo → the mark goes out at once as correct, with no reason", () => {
    const { sent, button } = page();
    button("De acuerdo").click();
    expect(sent).toEqual([["ad_hominem-42.0", "correct", ""]]);
  });
});
