// S9 A3 · The card shows the earlier statement or the promise
//
// Story: On a page that mimics the YouTube player, a record flag shows the earlier statement with its date
// and its source as a link; a promise flag shows "Prometido en abril de 2023: 184.000 viviendas para 2026 ·
// Estado: no cumplida".
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds two contradiction flags marked for the player: a "record" flag at second 10 whose
// related utterance is an earlier public statement (no second, a date and a source), and a "promise" flag at
// second 40 with its promise; playback is moved by setting the video time and firing "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const NOW = "yo nunca dije que no pactaría con ese partido";
const EARLIER = "no pactaré con ese partido";
const URL = "https://example.org/el-diario/entrevista-2023-07-02";
const HOMES = "hemos cumplido lo que prometimos en vivienda";

const flagFile = {
  video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [
    {
      id: "record-10.0", t: 10, speaker: "Invitado", quote: NOW, type: "contradiction", label: "record",
      reason: "En julio de 2023 dijo que no pactaría con ese partido.", confidence: 0.9, on_player: true,
      related: { t: null, quote: EARLIER, date: "2023-07-02", source: { publisher: "El Diario", url: URL } },
      sources: [{ publisher: "El Diario", url: URL, date: "2023-07-02" }], note: null,
    },
    {
      id: "promise-40.0", t: 40, speaker: "Invitado", quote: HOMES, type: "contradiction", label: "promise",
      reason: "Se entregaron muchas menos viviendas de las prometidas.", confidence: 0.9, on_player: true,
      related: null, note: null,
      promise: { made: "2023-04", figure: "184.000 viviendas", deadline: "2026", status: "not met" },
      sources: [{ publisher: "El País", url: "https://example.org/el-pais/viviendas-2025", date: "2025-09-15" }],
    },
  ],
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

describe("S9 A3 · The card shows the earlier statement or the promise", () => {
  it("Case 1 · at second 11, a record flag → the earlier statement with its date, its source as a link, then the new words", () => {
    const cards = at(11);
    expect(cards.length).toBe(1);
    const text = cards[0].textContent!;
    expect(text).toContain(NOW);
    expect(text.indexOf(EARLIER)).toBeLessThan(text.indexOf(NOW));
    const earlier = [...cards[0].children].find((el) => el.textContent!.includes(EARLIER))!;
    expect(earlier).toBeDefined();
    expect(earlier.textContent).toContain("2023-07-02");
    const link = earlier.querySelector(`a[href="${URL}"]`);
    expect(link).not.toBeNull();
    expect(link!.textContent).toContain("El Diario");
  });

  it("Case 2 · at second 41, a promise flag → the date, figure, deadline and status of the promise", () => {
    const cards = at(41);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Prometido en abril de 2023: 184.000 viviendas para 2026 · Estado: no cumplida");
  });
});
