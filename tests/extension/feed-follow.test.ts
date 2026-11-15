// @vitest-environment jsdom
// The feed lights the row at the playhead with its reason, follows the playhead, and offers "Ir al directo"
// once the person scrolls it.
import { expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const flag = (t: number) => ({
  id: `f-${t}`, t, speaker: "Invitado", quote: `frase ${t}`, type: "inaccuracy", label: "false",
  reason: `Motivo ${t}.`, confidence: 0.8, on_player: true, related: null, note: null,
  sources: [{ publisher: "INE", url: "https://ine.es/x", date: "2024" }],
});

function page() {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  const file = { video_id: "abc", published_at: null, status: "done", stop_reason: null, flags: [flag(10), flag(50)] } as any;
  const overlay = mountOverlay(player, video, () => file, () => {});
  mountPanel(overlay.layer, video, () => file, overlay.show);
  const playTo = (t: number) => {
    Object.defineProperty(video, "currentTime", { value: t, writable: true, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
  };
  const row = (t: number) => [...player.querySelectorAll<HTMLElement>(".fc-row")].find((r) => r.textContent!.includes(`frase ${t}`))!;
  const jump = player.querySelector<HTMLElement>(".fc-jump")!;
  return { player, playTo, row, jump };
}

it("only the row at the playhead shows its reason, its sources and its confidence", () => {
  const { playTo, row } = page();
  playTo(12);
  expect(row(10).textContent).toContain("Motivo 10.");
  expect(row(10).textContent).toContain("1 fuente");
  expect(row(10).textContent).toContain("80%");
  playTo(55);
  expect(row(10).textContent).not.toContain("Motivo 10.");
  expect(row(50).textContent).toContain("Motivo 50.");
});

it("a scroll by the person shows Ir al directo; a click on it hides it again", () => {
  const { player, jump } = page();
  expect(jump.hidden).toBe(true);
  player.querySelector(".fc-list")!.dispatchEvent(new Event("wheel"));
  expect(jump.hidden).toBe(false);
  expect(jump.textContent).toBe("Ir al directo");
  jump.click();
  expect(jump.hidden).toBe(true);
});
