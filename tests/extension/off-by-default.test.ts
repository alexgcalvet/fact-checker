// @vitest-environment jsdom
// The extension spends nothing until the person turns it on for a video; a video already analysed shows at once.
import { beforeEach, expect, it, vi } from "vitest";

function page(known: object | null) {
  history.pushState({}, "", "/watch?v=abc123");
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const sent: any[] = [];
  (globalThis as any).chrome = {
    runtime: {
      id: "x",
      sendMessage: vi.fn(async (m: any) => {
        sent.push(m);
        return { ok: true, data: m.kind === "flags" ? known : null };
      }),
    },
    storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
  };
  return sent;
}

const start = () => document.querySelector<HTMLButtonElement>(".fc-start");
const flush = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => vi.resetModules());

it("a new video asks for nothing until the person clicks the start button", async () => {
  const sent = page(null);
  await import("../../src/extension/src/content");
  await flush();
  expect(sent.some((m) => m.kind === "analyze")).toBe(false);
  start()!.click();
  await flush();
  expect(sent.filter((m) => m.kind === "analyze")).toEqual([expect.objectContaining({ videoId: "abc123" })]);
  expect(start()).toBeNull();
});

it("a video already analysed shows its flags with no start button", async () => {
  const sent = page({ video_id: "abc123", status: "done", flags: [] });
  await import("../../src/extension/src/content");
  await flush();
  expect(sent.some((m) => m.kind === "analyze")).toBe(false);
  expect(start()).toBeNull();
});
