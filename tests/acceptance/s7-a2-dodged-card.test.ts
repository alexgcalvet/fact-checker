// S7 A2 · A dodged-question card shows the question
//
// Story: On a page that mimics the YouTube player, a dodged-question flag shows at its second. The card
// reads "Pregunta esquivada", quotes the host's question, and gives the reason.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds one dodged-question flag at second 40 (the end of the answer), marked for the
// player, whose related utterance is the host's question at second 2; playback is moved by setting the
// video time and firing "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const QUESTION = "¿Cuántas viviendas se han entregado?";
const REASON = "Se preguntó por viviendas entregadas y la respuesta habla de la ley de vivienda.";

const flagFile = {
  video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{
    id: "dodged-40.0", t: 40, speaker: "Invitado", quote: "la primera ley de vivienda de la democracia",
    type: "question", label: "dodged", answer: "dodged", reason: REASON, confidence: 0.9, on_player: true,
    related: { t: 2, quote: QUESTION }, sources: [], note: null,
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

describe("S7 A2 · A dodged-question card shows the question", () => {
  it("Case 1 · at second 40 → a Pregunta esquivada card with the host's question and the reason", () => {
    const cards = at(40);
    expect(cards.length).toBe(1);
    const text = cards[0].textContent!;
    expect(text).toContain("Pregunta esquivada");
    expect(text).toContain(QUESTION);
    expect(text).toContain(REASON);
  });

  it("Case 2 · at second 39, before the answer ends → no card", () => {
    expect(at(39).length).toBe(0);
  });
});
