// @vitest-environment jsdom
// The viewer controls on the mimic player: pin, pause while the person writes a reason, and quiet mode.
import { describe, expect, it, vi } from "vitest";
import "../../src/extension/src/guard";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const flag = (id: string, t: number, confidence: number) => ({
  id, t, speaker: "Invitado", quote: `frase ${t}`, type: "fallacy", label: "ad_hominem", reason: "Ataca.",
  confidence, related: null, sources: [], note: null,
});

function page(flags: object[], paused = true) {
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  Object.defineProperty(video, "paused", { value: paused, configurable: true });
  video.pause = vi.fn();
  video.play = vi.fn();
  const file = { video_id: "abc", published_at: null, status: "done", stop_reason: null, flags } as any;
  const overlay = mountOverlay(player, video, () => file, () => {});
  mountPanel(overlay.layer, video, () => file, overlay.show);
  const playTo = (t: number) => {
    Object.defineProperty(video, "currentTime", { value: t, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
  };
  const cards = () => [...player.querySelectorAll<HTMLElement>(".fc-card")];
  const button = (text: string) => [...player.querySelectorAll("button")].find((b) => b.textContent!.includes(text))!;
  return { player, video, playTo, cards, button };
}

describe("pin", () => {
  it("a pinned card stays past its seconds; its ✕ closes it", () => {
    const { playTo, cards } = page([flag("a", 10, 0.9)]);
    playTo(11);
    cards()[0].querySelector<HTMLElement>(".fc-pin")!.click();
    playTo(60);
    expect(cards().length).toBe(1);
    cards()[0].querySelector<HTMLElement>(".fc-pin")!.click();
    expect(cards().length).toBe(0);
  });

  it("P pins the newest card and never reaches YouTube", () => {
    const { playTo, cards } = page([flag("a", 10, 0.9), flag("b", 12, 0.9)]);
    const reached = vi.fn();
    window.addEventListener("keydown", reached, true);
    playTo(13);
    document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "p", bubbles: true }));
    expect(reached).not.toHaveBeenCalled();
    playTo(60);
    expect(cards().map((c) => c.textContent)).toEqual([expect.stringContaining("frase 12")]);
  });
});

describe("pause on ✗", () => {
  it("a playing video pauses for the reason and plays on after Guardar", () => {
    const { video, playTo, button } = page([flag("a", 10, 0.9)], false);
    playTo(11);
    button("✗ No").click();
    expect(video.pause).toHaveBeenCalledOnce();
    button("Guardar").click();
    expect(video.play).toHaveBeenCalledOnce();
  });

  it("a paused video stays paused after Cancelar", () => {
    const { video, playTo, button } = page([flag("a", 10, 0.9)], true);
    playTo(11);
    button("✗ No").click();
    button("Cancelar").click();
    expect(video.play).not.toHaveBeenCalled();
    expect(button("✗ No")).toBeDefined();
  });
});

it("quiet mode hides a 0.85 card on the player and keeps it in the panel", () => {
  const { player, playTo, cards, button } = page([flag("a", 10, 0.85)]);
  button("⚙").click();
  const quiet = player.querySelector<HTMLInputElement>(".fc-settings input[type=checkbox]")!;
  quiet.checked = true;
  quiet.dispatchEvent(new Event("change"));
  playTo(11);
  expect(cards().length).toBe(0);
  expect(player.querySelectorAll(".fc-row").length).toBe(1);
});
