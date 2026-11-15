// S10 A2 · A context card shows who or what was named
//
// Story: On a page that mimics the YouTube player, a context flag shows at its second. The card reads
// "Contexto", names "Marta Gil" and gives the sentence, with no buttons to mark it unfair as a claim.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a mark
// callback and a fixed flag file that holds one context flag at second 182 (label "person", the name as
// quote, the sentence as reason), marked for the player; playback is moved by setting the video time and
// firing "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const NAME = "Marta Gil";
const SENTENCE = "Ministro de Transportes del Gobierno de España desde noviembre de 2023.";

const flagFile = {
  video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{
    id: "person-182.0", t: 182, speaker: "Invitado", quote: NAME, type: "context", label: "person",
    reason: SENTENCE, confidence: 0.95, on_player: true, related: null, sources: [], note: null,
  }],
} as any;

function at(second: number) {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  mountOverlay(player, video, () => flagFile, () => {});
  Object.defineProperty(video, "currentTime", { value: second, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  return player.querySelectorAll(".fc-card");
}

describe("S10 A2 · A context card shows who or what was named", () => {
  it("Case 1 · at second 183 → a Contexto card with the name and the sentence", () => {
    const cards = at(183);
    expect(cards.length).toBe(1);
    const text = cards[0].textContent!;
    expect(text).toContain("Contexto");
    expect(text).toContain(NAME);
    expect(text).toContain(SENTENCE);
  });

  it("Case 2 · the person can mark cards → the context card has no mark buttons", () => {
    const cards = at(183);
    expect(cards[0].querySelectorAll("button").length).toBe(0);
  });

  it("Case 3 · at second 181, before the mention → no card", () => {
    expect(at(181).length).toBe(0);
  });
});
