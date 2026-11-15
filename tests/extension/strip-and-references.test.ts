// @vitest-environment jsdom
// The strip under the video holds only the marks, with a tip of minute and kind over a mark.
// A card's details pair each source link with the figures it backs.
import { expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

function page(flags: object[]) {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  const file = { video_id: "abc", status: "done", flags } as any;
  const overlay = mountOverlay(player, video, () => file, () => {});
  mountPanel(overlay.layer, video, () => file, overlay.show);
  const playTo = (t: number) => {
    Object.defineProperty(video, "currentTime", { value: t, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
  };
  return { player, playTo };
}

const fallacy = { id: "ad_hominem-30.0", t: 30, speaker: "Invitado", quote: "q", type: "fallacy", label: "ad_hominem",
  reason: "r", confidence: 0.9, on_player: true, related: null, sources: [], note: null };

it("the strip draws no playback of its own: YouTube's red bar shows it", () => {
  const { player, playTo } = page([fallacy]);
  playTo(25);
  expect(player.querySelector(".fc-strip .fc-played, .fc-strip .fc-sun")).toBeNull();
  expect(player.querySelector(".fc-strip")!.classList.contains("fc-done")).toBe(true);
});

it("a mark under the mouse shows a tip with its minute and kind", () => {
  const { player } = page([fallacy]);
  player.querySelector(".fc-mark")!.dispatchEvent(new Event("pointerenter"));
  const tip = player.querySelector<HTMLElement>(".fc-tip")!;
  expect(tip.hidden).toBe(false);
  expect(tip.textContent).toContain("0:30");
  expect(tip.textContent).toContain("Ad hominem");
});

it("each figure carries the link of the outlet it names", () => {
  const { player, playTo } = page([{
    id: "misleading-10.0", t: 10, speaker: "Invitado", quote: "q", type: "inaccuracy", label: "misleading",
    reason: "r", confidence: 0.9, on_player: true, related: null, note: null,
    measures: [
      { name: "Titulares extranjeros", value: "16 %", source: "Seguridad Social vía Maldita.es, 2026", tier: 1, supports: false },
      { name: "Perceptores", value: "150.000", source: "Ministerio de Inclusión, junio 2026", tier: 1, supports: false },
    ],
    sources: [
      { publisher: "Maldita.es", url: "https://maldita.es/a", date: "2026-01-01" },
      { publisher: "Ministerio de Inclusión", url: "https://inclusion.gob.es/b", date: "2026-06-01" },
    ],
  }]);
  playTo(11);
  const refs = [...player.querySelectorAll(".fc-card .fc-ref")];
  expect(refs.length).toBe(2);
  expect(refs[0].querySelector("a")!.href).toBe("https://maldita.es/a");
  expect(refs[0].textContent).toContain("16 %");
  expect(refs[1].querySelector("a")!.href).toBe("https://inclusion.gob.es/b");
  expect(refs[1].textContent).toContain("150.000");
});

it("the strip lies exactly over YouTube's progress bar", () => {
  const { player, playTo } = page([fallacy]);
  const bar = document.createElement("div");
  bar.className = "ytp-progress-bar";
  player.append(bar);
  const rect = (left: number, top: number, width: number, height: number) =>
    ({ left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({}) }) as DOMRect;
  bar.getBoundingClientRect = () => rect(112, 640, 1056, 3);
  player.querySelector<HTMLElement>(".fc-layer")!.getBoundingClientRect = () => rect(100, 0, 1280, 720);
  playTo(10);
  const strip = player.querySelector<HTMLElement>(".fc-strip")!;
  expect(strip.style.left).toBe("12px");
  expect(strip.style.width).toBe("1056px");
  expect(strip.style.top).toBe(`${640 + 1.5 - 9}px`);
});
