// @vitest-environment jsdom
// S3 A3 · The full screen button turns the phone sideways
// Story: With the phone upright, the viewer taps the full screen button. The browser goes full screen and turns the
// video sideways, and the flag being said shows on its card, not in the strip. A tap on "Salir de pantalla completa"
// lets the phone turn back.
// Edge case: WHEN the browser refuses full screen or turning (an iPhone) THEN the page still fills the screen with the
// video, its bar and its card.
// Setup: the invented collector and the fake YouTube player; a stubbed matchMedia answers as a phone upright; the
// browser's full screen and screen orientation are spies. The video plays from second 1215.
import { act } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function upright(at: number) {
  vi.stubGlobal("matchMedia", (media: string) => ({ matches: media.includes("max-width"), media, addEventListener() {}, removeEventListener() {} }));
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
const strip = (root: HTMLElement) => root.querySelector<HTMLElement>('.now[aria-label="Aviso de ahora"]');
const click = (el: HTMLElement) => act(async () => el.click());
const orientation = (lock: () => Promise<void>) => {
  const o = { lock: vi.fn(lock), unlock: vi.fn() };
  Object.defineProperty(screen, "orientation", { value: o, configurable: true });
  return o;
};

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  delete (HTMLElement.prototype as any).requestFullscreen;
  delete (screen as any).orientation;
});

it("goes full screen and asks to turn sideways, shows the card, and lets go on exit", async () => {
  const request = vi.fn(() => Promise.resolve());
  (HTMLElement.prototype as any).requestFullscreen = request;
  const turn = orientation(() => Promise.resolve());
  const { root } = await upright(1215);

  // Case 1 · the full screen button → the browser's full screen, a lock to landscape, the card and no strip
  await click(button(root, "Pantalla completa"));
  expect(request).toHaveBeenCalledTimes(1);
  expect(turn.lock).toHaveBeenCalledWith("landscape");
  expect(card(root)!.textContent).toContain("cifra inventada 3");
  expect(strip(root)).toBeNull();

  // Case 2 · "Salir de pantalla completa" → the lock is let go
  await click(button(root, "Salir de pantalla completa"));
  expect(turn.unlock).toHaveBeenCalledTimes(1);
  expect(strip(root)!.textContent).toContain("20:10");
  console.log("PASS S3 A3 · The full screen button turns the phone sideways");
});

it("fills the page with the video, its bar and its card when the browser refuses (an iPhone)", async () => {
  orientation(() => Promise.reject(new Error("not supported")));
  const { root } = await upright(1215);

  // Case 3 · no full screen and a refused lock → the stage still fills the page, with the bar and the card
  await click(button(root, "Pantalla completa"));
  expect(root.querySelector(".stage")!.classList.contains("full")).toBe(true);
  expect(button(root, "Salir de pantalla completa")).not.toBeNull();
  expect(card(root)!.textContent).toContain("cifra inventada 3");
  expect(strip(root)).toBeNull();
  console.log("PASS S3 A3 · edge: the page fills when the browser refuses");
});

it("stays full with its card when the browser goes full screen but refuses to turn (an Android without a lock)", async () => {
  (HTMLElement.prototype as any).requestFullscreen = vi.fn(() => Promise.resolve());
  const turn = orientation(() => Promise.reject(new Error("not allowed")));
  const { root } = await upright(1215);

  // Case 4 · full screen granted, the lock refused → the stage stays full with its card
  await click(button(root, "Pantalla completa"));
  expect(turn.lock).toHaveBeenCalledWith("landscape");
  expect(root.querySelector(".stage")!.classList.contains("full")).toBe(true);
  expect(card(root)!.textContent).toContain("cifra inventada 3");
  console.log("PASS S3 A3 · edge: full screen stays when the turn is refused");
});
