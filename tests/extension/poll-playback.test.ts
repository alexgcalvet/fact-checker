// @vitest-environment jsdom
// The poll of the flag file tells the helper where the person is, so the analysis follows what they watch.
import { expect, it, vi } from "vitest";

it("the poll sends the playback second, and the service worker puts it on the request", async () => {
  history.pushState({}, "", "/watch?v=abc123");
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const video = document.querySelector("video")!;
  Object.defineProperty(video, "currentTime", { value: 754.6, writable: true });
  const sendMessage = vi.fn(async () => ({ ok: true, data: null }));
  let listener: any;
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  (globalThis as any).fetch = fetchMock;
  (globalThis as any).chrome = {
    runtime: { id: "x", sendMessage, onMessage: { addListener: (f: any) => { listener = f; } } },
    storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
  };
  await import("../../src/extension/src/content");
  await new Promise((r) => setTimeout(r, 0));
  expect(sendMessage).toHaveBeenCalledWith({ kind: "flags", videoId: "abc123", at: 754.6, lang: "es" });

  await import("../../src/extension/src/sw");
  await new Promise<void>((done) => listener({ kind: "flags", videoId: "abc123", at: 754.6 }, {}, () => done()));
  expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8765/videos/abc123?at=754");
});
