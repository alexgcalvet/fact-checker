// S21 A4 · The extension says when the helper is down
//
// Story: A tester opens a YouTube video with the helper stopped. Instead of the "Analizar este vídeo" button, the
// player shows "El ayudante de fact-checker no responde", how to install it and to run `fact-checker doctor`. When the
// helper comes back, the message goes and the button shows. If the helper stops during an analysis, the message shows
// again.
//
// Setup: a jsdom watch page with a player and a video, and fake timers. The content script talks to a fake service
// worker whose answer the test sets: "down" (what the service worker answers when it cannot reach the helper), "no
// file yet" or "running". Then the real service worker gets a request while the helper's address refuses the
// connection (fetch rejects with a TypeError, as Chrome does).
// @vitest-environment jsdom
import { afterAll, describe, expect, it, vi } from "vitest";

const DOWN = { ok: false, down: true };
const RUNNING = { video_id: "abc123", status: "running", stop_reason: null, analysed_until: 0, flags: [] };

describe("S21 A4 · The extension says when the helper is down", () => {
  let answer: object = DOWN;
  let listener: any;
  const sendMessage = vi.fn(async (_req: any) => answer);
  const message = () => document.querySelector<HTMLElement>(".fc-down");
  const startButton = () => [...document.querySelectorAll("button")].find((b) => b.textContent === "Analizar este vídeo");
  vi.useFakeTimers();
  afterAll(() => { vi.useRealTimers(); });

  // Case 1 · the helper is down when the video opens → the message with install and doctor hints, no button
  it("Case 1 · helper down on open → the message, with install and doctor hints, and no button", async () => {
    history.pushState({}, "", "/watch?v=abc123");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    (globalThis as any).chrome = {
      runtime: { id: "x", sendMessage, onMessage: { addListener: (f: any) => { listener = f; } } },
      storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
    };
    await import("../../src/extension/src/content");
    await vi.advanceTimersByTimeAsync(0);
    expect(message()?.textContent).toContain("El ayudante de fact-checker no responde");
    expect(message()?.textContent).toContain("instal");
    expect(message()?.textContent).toContain("fact-checker doctor");
    expect(startButton()).toBeUndefined();
  });

  // Case 2 · the helper comes back → the message goes and the button shows
  it("Case 2 · the helper comes back → no message, the button shows", async () => {
    expect(message()).not.toBeNull();
    answer = { ok: true, data: null };
    await vi.advanceTimersByTimeAsync(3000);
    expect(message()).toBeNull();
    expect(startButton()).toBeDefined();
  });

  // Case 3 · the helper stops during an analysis → the message shows again
  it("Case 3 · the helper stops during an analysis → the message shows again", async () => {
    expect(startButton()).toBeDefined();
    answer = { ok: true, data: RUNNING };
    startButton()!.click();
    await vi.advanceTimersByTimeAsync(3000);
    expect(message()).toBeNull();
    answer = DOWN;
    await vi.advanceTimersByTimeAsync(3000);
    expect(message()?.textContent).toContain("El ayudante de fact-checker no responde");
  });

  // Case 4 · the service worker cannot reach the helper → it answers "down"
  it("Case 4 · the connection to the helper is refused → the service worker answers down", async () => {
    (globalThis as any).fetch = vi.fn(async () => { throw new TypeError("Failed to fetch"); });
    await import("../../src/extension/src/sw");
    const reply = await new Promise<any>((done) => listener({ kind: "flags", videoId: "abc123", at: 3 }, {}, done));
    expect(reply).toEqual(DOWN);
  });
});
