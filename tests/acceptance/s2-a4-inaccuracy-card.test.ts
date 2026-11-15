// S2 A4 · An inaccuracy card shows the source and the date
//
// Story: On a page that mimics the YouTube player, with an inaccuracy flag at second 30 with confidence
// 0.9, rated "false", sourced to INE on 2025-10-28, the person plays to second 30 and sees a card with
// "Dato falso", the words, "INE · 2025-10-28" and "90%". When the flag has a note that the figure changed
// after the video was published, the card also shows "Dato actualizado:" with the note.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file; playback is moved by setting the video time and firing "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

function flagFile(note: string | null) {
  return {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{
      id: "false-30.0", t: 30, speaker: "guest", quote: "el paro bajó al ocho por ciento", type: "inaccuracy",
      label: "false", reason: "La EPA dio un 10,45 %.", confidence: 0.9, related: null,
      sources: [{ publisher: "INE", url: "https://www.ine.es/epa", date: "2025-10-28" }], note,
    }],
  } as any;
}

function page(note: string | null) {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  mountOverlay(player, video, () => flagFile(note));
  Object.defineProperty(video, "currentTime", { value: 30, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  return player;
}

describe("S2 A4 · An inaccuracy card shows the source and the date", () => {
  it("Case 1 · at second 30 → one card with Dato falso, the words, the source, the date and 90%", () => {
    const cards = page(null).querySelectorAll(".fc-card");
    expect(cards.length).toBe(1);
    const text = cards[0].textContent!;
    expect(text).toContain("Dato falso");
    expect(text).toContain("el paro bajó al ocho por ciento");
    expect(text).toContain("INE · 2025-10-28");
    expect(text).toContain("90%");
    expect(text).not.toContain("Dato actualizado");
  });

  it("Case 2 · the flag has a note → the card also shows Dato actualizado with the note", () => {
    const text = page("Hoy es del 10,1 %.").querySelector(".fc-card")!.textContent!;
    expect(text).toContain("Dato actualizado: Hoy es del 10,1 %.");
  });
});
