// @vitest-environment jsdom
// A context chip stays long enough to read it and waits for the mouse; a card's sources come first in its details.
import { expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";

const context = (reason: string) => ({
  id: "person-100.0", t: 100, speaker: "Invitado", quote: "Ana Pérez", type: "context", label: "person",
  reason, confidence: 0.95, on_player: true, related: null, sources: [], note: null,
});

function page(flags: object[]) {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  mountOverlay(player, video, () => ({ video_id: "abc", status: "done", flags }) as any, () => {});
  const playTo = (t: number) => {
    Object.defineProperty(video, "currentTime", { value: t, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
  };
  return { player, playTo, chips: () => player.querySelectorAll(".fc-chip") };
}

it("a long context chip stays past 8 seconds; a short one leaves at 8", () => {
  const long = page([context("x".repeat(240))]);
  long.playTo(112);
  expect(long.chips().length).toBe(1);
  const short = page([context("Economista.")]);
  short.playTo(109);
  expect(short.chips().length).toBe(0);
});

it("a chip under the mouse stays, and 3 seconds more after the mouse leaves", () => {
  const { playTo, chips } = page([context("Economista.")]);
  playTo(101);
  chips()[0].dispatchEvent(new Event("pointerenter", { bubbles: true }));
  playTo(120);
  expect(chips().length).toBe(1);
  chips()[0].dispatchEvent(new Event("pointerleave", { bubbles: true }));
  playTo(122);
  expect(chips().length).toBe(1);
  playTo(124);
  expect(chips().length).toBe(0);
});

it("a source that no line names gets a line of its own, after the figures", () => {
  const { player, playTo } = page([{
    id: "false-10.0", t: 10, speaker: "Invitado", quote: "medio millón", type: "inaccuracy", label: "misleading",
    reason: "No.", confidence: 0.9, on_player: true, related: null, note: null,
    measures: [{ name: "Titulares", value: "16 %", source: "SS", tier: 1, supports: false }],
    sources: [{ publisher: "Maldita", url: "https://maldita.es/x", date: "2026-01-01" }],
  }]);
  playTo(11);
  const lines = [...player.querySelectorAll(".fc-card details > div")];
  expect(lines[0].querySelector("a")).toBeNull();
  expect(lines.at(-1)!.querySelector("a")?.href).toBe("https://maldita.es/x");
});
