// S13 A4 · A card already marked shows the mark instead of the buttons
//
// Story: On the mimic player, a card marked "unfair" shows at its second. It reads "Marcaste: ✗ No" with a
// "cambiar" link instead of the two buttons; the link brings the buttons back.
//
// Setup: a jsdom page with a player and a video, the overlay mounted with one flag at second 42 that carries a
// past mark, and a mark callback that records what it gets; playback is moved to second 43.
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const flagFile = (mark: string) => ({
  video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
    label: "ad_hominem", reason: "Ataca.", confidence: 0.85, on_player: true, related: null, sources: [], note: null,
    mark }],
}) as any;

function page(mark: string) {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  const sent: string[] = [];
  const file = flagFile(mark);
  mountOverlay(player, video, () => file, (flag, verdict) => { sent.push(verdict); });
  Object.defineProperty(video, "currentTime", { value: 43, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  const card = () => player.querySelector<HTMLElement>(".fc-card")!;
  const buttons = () => [...card().querySelectorAll("button")].map((b) => b.textContent!);
  const change = () => [...card().querySelectorAll<HTMLElement>("a, button")].find((b) => b.textContent === "cambiar");
  return { card, buttons, change, sent };
}

describe("S13 A4 · A card already marked shows the mark instead of the buttons", () => {
  // Case 1 · a card marked unfair → "Marcaste: ✗ No" and a "cambiar" link, no mark buttons
  it("Case 1 · a card marked unfair → \"Marcaste: ✗ No\" and \"cambiar\", no mark buttons", () => {
    const { card, buttons, change } = page("unfair");
    expect(card().textContent).toContain("Marcaste: ✗ No");
    expect(change()).toBeDefined();
    expect(buttons()).not.toContain("✓ De acuerdo");
    expect(buttons()).not.toContain("✗ No");
  });

  // Case 2 · a click on "cambiar" → the two mark buttons come back, and nothing is sent yet
  it("Case 2 · a click on \"cambiar\" → the two mark buttons come back", () => {
    const { buttons, change, sent } = page("unfair");
    change()!.click();
    expect(buttons()).toContain("✓ De acuerdo");
    expect(buttons()).toContain("✗ No");
    expect(sent).toEqual([]);
  });

  // Case 3 · a card marked correct → "Marcaste: ✓ De acuerdo"
  it("Case 3 · a card marked correct → \"Marcaste: ✓ De acuerdo\"", () => {
    const { card } = page("correct");
    expect(card().textContent).toContain("Marcaste: ✓ De acuerdo");
  });
});
