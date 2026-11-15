// S8 A2 · A contradiction card shows both statements
//
// Story: On a page that mimics the YouTube player, a contradiction flag shows at its second. The card
// reads "Contradicción", quotes the earlier statement with its minute, then the new one, and gives the
// reason.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds one contradiction flag at second 252.5 (the second statement), marked for the
// player, whose related utterance is the first statement at second 9; playback is moved by setting the
// video time and firing "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const EARLIER = "no vamos a subir el IVA";
const NOW = "subiremos el IVA de la luz el año que viene";
const REASON = "Antes dijo que no subiría el IVA y ahora anuncia una subida del IVA de la luz.";

const flagFile = {
  video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{
    id: "self-252.5", t: 252.5, speaker: "Invitado", quote: NOW, type: "contradiction", label: "self",
    reason: REASON, confidence: 0.9, on_player: true, related: { t: 9, quote: EARLIER }, sources: [], note: null,
  }],
} as any;

function at(second: number) {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  mountOverlay(player, video, () => flagFile);
  Object.defineProperty(video, "currentTime", { value: second, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  return player.querySelectorAll(".fc-card");
}

describe("S8 A2 · A contradiction card shows both statements", () => {
  it("Case 1 · at second 253 → a Contradicción card with the earlier statement and its minute, then the new one, and the reason", () => {
    const cards = at(253);
    expect(cards.length).toBe(1);
    const text = cards[0].textContent!;
    expect(text).toContain("Contradicción");
    expect(text).toContain("0:09");
    expect(text).toContain(EARLIER);
    expect(text).toContain(NOW);
    expect(text.indexOf(EARLIER)).toBeLessThan(text.indexOf(NOW));
    expect(text).toContain(REASON);
  });

  it("Case 2 · at second 252, before the second statement → no card", () => {
    expect(at(252).length).toBe(0);
  });
});
