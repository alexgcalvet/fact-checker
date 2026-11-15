// S6 A2 · A disputed card shows each measure and the controversy
//
// Story: On a page that mimics the YouTube player, a disputed flag shows at its second. The card reads
// "Dato discutido", lists each measure as "name: value (source)", and shows the controversy line under them.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds one disputed flag at second 30 with the three unemployment measures of
// tests/golden/empleo.json and a controversy line; playback is moved by setting the video time and firing
// "timeupdate".
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const CONTROVERSY = "El paro registrado no cuenta a los fijos discontinuos inactivos, unos 0,9 millones (SEPE).";
const LINES = [
  "paro registrado (SEPE): 2.443.766 (SEPE, octubre 2025)",
  "paro registrado + demandantes con relación laboral: unos 3,3 millones (SEPE, octubre 2025)",
  "parados EPA: 2.613.200 (INE, EPA 3T 2025)",
];

const flagFile = {
  video_id: "abc", published_at: "2025-11-10", status: "done", stop_reason: null,
  flags: [{
    id: "disputed-30.0", t: 30, speaker: "guest", quote: "tenemos casi tres millones y medio de parados registrados",
    type: "inaccuracy", label: "disputed", reason: "Depende de la medida.", confidence: 0.9, related: null,
    sources: [{ publisher: "SEPE", url: "https://www.sepe.es/paro", date: "2025-11-04" }], note: null,
    measures: [
      { name: "paro registrado (SEPE)", value: "2.443.766", source: "SEPE, octubre 2025", tier: 2, supports: false },
      { name: "paro registrado + demandantes con relación laboral", value: "unos 3,3 millones",
        source: "SEPE, octubre 2025", tier: 2, supports: true },
      { name: "parados EPA", value: "2.613.200", source: "INE, EPA 3T 2025", tier: 1, supports: false },
    ],
    controversy: CONTROVERSY,
  }],
} as any;

describe("S6 A2 · A disputed card shows each measure and the controversy", () => {
  it("Case 1 · at second 30 → a Dato discutido card with each measure, then the controversy line", () => {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile);
    Object.defineProperty(video, "currentTime", { value: 30, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));

    const cards = player.querySelectorAll(".fc-card");
    expect(cards.length).toBe(1);
    const text = cards[0].textContent!;
    expect(text).toContain("Dato discutido");
    for (const line of LINES) expect(text).toContain(line);
    expect(text).toContain(CONTROVERSY);
    expect(text.indexOf(CONTROVERSY)).toBeGreaterThan(text.indexOf(LINES[2]));
  });
});
