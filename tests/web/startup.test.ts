// @vitest-environment jsdom
// Inline 2026-11-22 · A page shows without waiting for YouTube, and the viewer asks for its data at once
//
// Story: A reader opens the home page while YouTube's player script is still loading: the home page shows anyway. A reader opens a video: the web app asks for the video and its flags together, not one after the other, and
// the viewer starts once the player script is ready.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch, which records when each request starts and ends. For the home page, the page's own script runs on a
// page with #app, and YouTube's script never loads (jsdom loads no external script). For the viewer, the web app is
// mounted through its `mount` export with a player that is still loading (a promise the test releases).
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const settle = () => new Promise((done) => setTimeout(done, 20));

async function open(path: string, player?: Promise<unknown>) {
  const { get } = await apiCollector();
  const log: string[] = [];
  vi.stubGlobal("fetch", async (url: string | URL) => {
    const name = new URL(String(url), "https://web.example").pathname;
    log.push(`start ${name}`);
    const res = await get(String(url));
    log.push(`end ${name}`);
    return res;
  });
  history.replaceState(null, "", path);
  // With #app the page's own script mounts the app; a test that mounts it itself uses another element.
  document.body.innerHTML = player ? '<div id="root"></div>' : '<div id="app"></div>';
  const root = document.body.firstElementChild as HTMLElement;
  vi.resetModules();
  await act(async () => {
    const { mount } = await import("../../src/web/src/main");
    if (player) void mount(root, player as any);
    await settle();
  });
  return { root, log };
}

describe("A page shows without waiting for YouTube", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("Case 1 · the home page with the player script still loading → it shows", async () => {
    const { root } = await open("/es/");
    expect(root.querySelector("main")).not.toBeNull();
  });

  it("Case 2 · a video → the video and its flags are asked together; the viewer starts once the player is ready", async () => {
    let ready: (p: unknown) => void = () => {};
    const { root, log } = await open("/es/v/debate01", new Promise((done) => { ready = done; }));
    const firstEnd = log.findIndex((line) => line.startsWith("end"));
    expect(log.slice(0, firstEnd)).toEqual(
      expect.arrayContaining(["start /api/videos/debate01", "start /api/videos/debate01/flags"]));
    ready(FakePlayer);
    await act(settle);
    expect(root.querySelector("main")).not.toBeNull();
    expect(root.textContent).toContain("cifra inventada");
  });
});
