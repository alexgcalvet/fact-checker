// @vitest-environment jsdom
// The feed counts only what stands; the flags the judge dropped wait folded at its end.
import { expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const flag = (id: string, t: number, judge?: object) => ({ id, t, speaker: "s", quote: `frase ${t}`, type: "inaccuracy",
  label: "false", reason: "r", confidence: 0.9, on_player: true, related: null, sources: [], note: null, judge });

it("counts leave out dropped flags, which sit folded after the rest", () => {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  const file = { video_id: "x", status: "done", flags: [flag("a", 10), flag("b", 20, { verdict: "drop", reason: "cierto" }),
    flag("c", 30), flag("d", 40, { verdict: "drop", reason: "cierto" })] } as any;
  const overlay = mountOverlay(player, video, () => file, () => {});
  mountPanel(overlay.layer, video, () => file, overlay.show);
  expect(player.querySelector(".fc-panel-tab")!.textContent).toContain("Avisos (2)");
  const falsos = [...player.querySelectorAll(".fc-flt button")].find((b) => b.textContent!.includes("Falsos"))!;
  expect(falsos.textContent).toContain("2");
  const folded = player.querySelector<HTMLDetailsElement>(".fc-dropped")!;
  expect(folded.open).toBe(false);
  expect(folded.querySelector("summary")!.textContent).toContain("Descartados por el juez (2)");
  expect([...folded.querySelectorAll(".fc-row")].map((r) => r.textContent!.includes("frase 20") || r.textContent!.includes("frase 40")))
    .toEqual([true, true]);
});
