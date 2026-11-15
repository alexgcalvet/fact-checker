// @vitest-environment jsdom
// After the extension is reloaded, the old copy of the content script in an open tab fails quietly: no unhandled
// error, its layer goes, and it no longer reacts to the next video. Vitest fails a test on an unhandled rejection.
import { expect, it, vi } from "vitest";

it("an invalidated extension context leaves no unhandled error and stops the old script", async () => {
  history.pushState({}, "", "/watch?v=abc123");
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const sendMessage = vi.fn(async () => { throw new Error("Extension context invalidated."); });
  // Chrome may keep the id on an orphaned script, so the error itself has to tell.
  (globalThis as any).chrome = {
    runtime: { id: "x", sendMessage },
    storage: { local: { get: vi.fn(async () => { throw new Error("Extension context invalidated."); }),
                        set: vi.fn(async () => { throw new Error("Extension context invalidated."); }) } },
  };
  await import("../../src/extension/src/content");
  await new Promise((r) => setTimeout(r, 0));
  expect(document.querySelector(".fc-layer")).toBeNull();

  const { setSettings } = await import("../../src/extension/src/overlay");
  setSettings({ quiet: true }, document.createElement("div"));

  const calls = sendMessage.mock.calls.length;
  document.dispatchEvent(new Event("yt-navigate-finish"));
  await new Promise((r) => setTimeout(r, 0));
  expect(sendMessage.mock.calls.length).toBe(calls);
  expect(document.querySelector(".fc-layer")).toBeNull();
});
