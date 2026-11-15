// @vitest-environment jsdom
// Every source of a card is a link that opens in a new tab.
import { expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

it("each source is a link to its page", () => {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  const file = { video_id: "abc", published_at: null, status: "done", stop_reason: null, flags: [{
    id: "false-10.0", t: 10, speaker: "Invitado", quote: "el paro está en el 14 %", type: "inaccuracy", label: "false",
    reason: "Es el 10,45 %.", confidence: 0.9, related: null, note: null,
    sources: [{ publisher: "INE", url: "https://www.ine.es/epa", date: "2025-10-28" },
              { publisher: "Newtral", url: "https://www.newtral.es/paro", date: "2025-10-29" }],
  }] } as any;
  mountOverlay(player, video, () => file, () => {});
  Object.defineProperty(video, "currentTime", { value: 11, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  const links = [...player.querySelectorAll<HTMLAnchorElement>(".fc-card a")];
  expect(links.map((a) => [a.textContent, a.href, a.target])).toEqual([
    ["INE", "https://www.ine.es/epa", "_blank"],
    ["Newtral", "https://www.newtral.es/paro", "_blank"],
  ]);
});
