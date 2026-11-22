// @vitest-environment jsdom
// S3 A2 · The flags open as a side sheet over the video
// Story: With the phone sideways, the viewer taps "Avisos" on the bar. A sheet slides over the right of the video with
// every flag, the one at 20:10 marked as now; the card over the video hides while the sheet is open. A tap on a flag's
// time jumps the video there; "Cerrar" closes the sheet and the card comes back.
// Setup: the invented collector and the fake YouTube player; a stubbed matchMedia answers as a phone held sideways
// (coarse pointer, landscape, at most 500px high). The video plays from second 1215.
import { act } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function sideways(at: number) {
  vi.stubGlobal("matchMedia", (media: string) => ({ matches: media.includes("landscape"), media, addEventListener() {}, removeEventListener() {} }));
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

const button = (root: HTMLElement, label: string) => root.querySelector<HTMLElement>(`button[aria-label="${label}"]`)!;
const card = (root: HTMLElement) => root.querySelector<HTMLElement>('.stage article[aria-label="Aviso de ahora"]');
const sheet = (root: HTMLElement) => root.querySelector<HTMLElement>('.stage aside.side-sheet[aria-label="Avisos"]');
const click = (el: HTMLElement) => act(async () => el.click());

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("opens every flag in a side sheet over the video, hides the card meanwhile, seeks on a time and closes", async () => {
  const { root, player } = await sideways(1215);
  expect(card(root)!.textContent).toContain("cifra inventada 3");

  // Case 1 · "Avisos" on the bar → the side sheet with every flag, 20:10 marked as now, no card
  await click(button(root, "Abrir el panel de avisos"));
  const open = sheet(root)!;
  expect(open.querySelectorAll("article.row").length).toBe(12);
  expect(open.querySelector('[aria-current="time"]')!.textContent).toContain("20:10");
  expect(card(root)).toBeNull();

  // Case 2 · a tap on a flag's time → the video jumps there
  await click(button(open, "Ir a 10:30"));
  expect(player.seeks).toEqual([[630, true]]);

  // Case 3 · "Cerrar" → the sheet goes and the card comes back
  await act(async () => {
    player.reach(1215);
    vi.advanceTimersByTime(250);
  });
  await click(button(sheet(root)!, "Cerrar"));
  expect(sheet(root)).toBeNull();
  expect(card(root)!.textContent).toContain("cifra inventada 3");
  console.log("PASS S3 A2 · The flags open as a side sheet over the video");
});
