// @vitest-environment jsdom
// S1 A1 · The viewer follows the player
//
// Story: A viewer opens /es/v/debate01 (the invented debate) and plays it. At second 80 the panel lights the flag
// said at second 75 and no later one; the viewer taps the time 20:10 of a flag and the video jumps to 1210 and keeps
// playing; tapping the flag's text does the same and also opens its reason.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch,
// and a fake YouTube player (tests/support/youtube_fake.ts) for the embed. Fake timers drive the app's 250 ms poll of
// the player's time; React's act lets each render finish. The web app is mounted through its own `mount` export at
// /es/v/debate01 in a Spanish browser, and the video plays from second 50.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function playing() {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL) => get(String(url)));
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  history.replaceState(null, "", "/es/v/debate01");
  document.body.innerHTML = '<div id="app"></div>';
  FakePlayer.last = undefined;
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  const player = FakePlayer.last!;
  await act(async () => {
    player.ready();
    player.play(50);
    vi.advanceTimersByTime(250);
  });
  return { root, player };
}

const panel = (root: HTMLElement) => root.querySelector<HTMLElement>('aside[aria-label="Avisos"]')!;
const rows = (root: HTMLElement) => [...panel(root).querySelectorAll<HTMLElement>("li > article")];
const lit = (root: HTMLElement) => rows(root).filter((r) => r.getAttribute("aria-current") === "time");
const row = (root: HTMLElement, time: string) => rows(root).find((r) => r.querySelector(`button[aria-label="Ir a ${time}"]`))!;

describe("S1 A1 · The viewer follows the player", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Case 1 · the video of debate01 plays on to second 80 → the flag at 1:15 is the only lit row
  it("Case 1 · the video of debate01 plays on to second 80 → the flag at 1:15 is the only lit row", async () => {
    const { root, player } = await playing();
    expect(player.options.videoId).toBe("debate01");
    expect(root.contains(player.iframe)).toBe(true);
    expect(rows(root).length).toBe(12);
    await act(async () => {
      player.reach(80);
      vi.advanceTimersByTime(250);
    });
    expect(lit(root).length).toBe(1);
    expect(lit(root)[0]).toBe(row(root, "1:15"));
    expect(lit(root)[0].textContent).toContain("cifra inventada 2");
  });

  // Case 2 · the viewer taps the time 20:10 → the player seeks to 1210 once, is not paused, and the row lights
  it("Case 2 · the viewer taps the time 20:10 → the player seeks to 1210 once, is not paused, and the row lights", async () => {
    const { root, player } = await playing();
    await act(async () => row(root, "20:10").querySelector<HTMLElement>('button[aria-label="Ir a 20:10"]')!.click());
    expect(player.seeks).toEqual([[1210, true]]);
    expect(player.pauses).toBe(0);
    expect(player.state).toBe(1);
    await act(async () => {
      player.reach(1211);
      vi.advanceTimersByTime(250);
    });
    expect(lit(root)).toEqual([row(root, "20:10")]);
  });

  // Case 3 · the viewer taps the text of the flag at 20:10 → the video goes to 1210 and keeps playing, and its reason opens
  it("Case 3 · the viewer taps the text of the flag at 20:10 → the video goes to 1210 and keeps playing, and its reason opens", async () => {
    const { root, player } = await playing();
    const text = row(root, "20:10").querySelector<HTMLElement>("button[aria-expanded]")!;
    expect(text.getAttribute("aria-expanded")).toBe("false");
    expect(row(root, "20:10").textContent).not.toContain("Invented reason.");
    await act(async () => text.click());
    expect(player.seeks).toEqual([[1210, true]]);
    expect(player.pauses).toBe(0);
    expect(player.state).toBe(1);
    expect(text.getAttribute("aria-expanded")).toBe("true");
    expect(row(root, "20:10").textContent).toContain("Invented reason.");
  });
});
