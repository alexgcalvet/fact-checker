// @vitest-environment jsdom
// S3 A1 · Turning a phone sideways fills the screen with the video
// Story: A viewer watches /es/v/debate01 on a phone held upright and turns it sideways. The video fills the screen with
// the bar over it; the header, the title and the panel are gone. At second 1215 the card of the flag said at 20:10 shows
// top right over the video. They turn the phone upright again: the page shows the video, the "Ahora" strip and the
// panel, and the video keeps playing from the same second.
// Setup: the invented collector (tests/support/api_fakes.ts) and the fake YouTube player; a stubbed matchMedia answers
// as a phone upright (max-width 760px) or sideways (coarse pointer, landscape, at most 500px high) and fires its change
// events on a turn. The video plays from second 1215.
import { act } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let sideways = false;
const listeners = new Set<() => void>();
const answers = (media: string) => (media.includes("landscape") ? sideways : media.includes("max-width") ? !sideways : false);
function turn(to: boolean) {
  sideways = to;
  return act(async () => listeners.forEach((l) => l()));
}

async function onPhone(at: number) {
  sideways = false;
  vi.stubGlobal("matchMedia", (media: string) => ({
    get matches() { return answers(media); }, media,
    addEventListener: (_: string, l: () => void) => listeners.add(l), removeEventListener: (_: string, l: () => void) => listeners.delete(l),
  }));
  vi.stubGlobal("scrollTo", vi.fn());
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL) => get(String(url)));
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  history.replaceState(null, "", "/es/v/debate01");
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  const player = FakePlayer.last!;
  await act(async () => {
    player.ready();
    player.play(at);
    vi.advanceTimersByTime(250);
  });
  return { root, player };
}

const card = (root: HTMLElement) => root.querySelector<HTMLElement>('.stage article[aria-label="Aviso de ahora"]');
const strip = (root: HTMLElement) => root.querySelector<HTMLElement>('.now[aria-label="Aviso de ahora"]');
const panel = (root: HTMLElement) => root.querySelector<HTMLElement>("aside.panel:not(.side-sheet)");

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  listeners.clear();
});

it("fills the screen with the video and its card when the phone turns sideways, and comes back upright", async () => {
  const { root, player } = await onPhone(1215);
  // Case 1 · upright → the strip and the panel, no card
  expect(strip(root)!.textContent).toContain("20:10");
  expect(card(root)).toBeNull();
  expect(panel(root)).not.toBeNull();

  // Case 2 · sideways → the stage fills the screen, the card of 20:10 over it, no strip and no panel
  await turn(true);
  expect(root.querySelector(".stage")!.classList.contains("full")).toBe(true);
  expect(card(root)!.textContent).toContain("Engañoso");
  expect(card(root)!.textContent).toContain("cifra inventada 3");
  expect(strip(root)).toBeNull();
  expect(panel(root)).toBeNull();
  expect(root.querySelector('.stage .bar button[aria-label="Pantalla completa"]')).not.toBeNull();

  // Case 3 · upright again → the strip and the panel, the same player at the same second
  await turn(false);
  expect(root.querySelector(".stage")!.classList.contains("full")).toBe(false);
  expect(strip(root)!.textContent).toContain("20:10");
  expect(panel(root)).not.toBeNull();
  expect(FakePlayer.last).toBe(player);
  expect(player.destroyed).toBe(false);
  expect(player.seeks).toEqual([]);
  console.log(`PASS S3 A1 · Turning a phone sideways fills the screen with the video`);
});
