// @vitest-environment jsdom
// The DeFacto wordmark turns once per session (owner, 2026-11-22; sketches/defacto/logo-spec.md §2)
//
// Story: A reader on a laptop opens their first page: the header's wordmark gets its turning layers, hidden from
// screen readers, while the link keeps the name. When the arms start turning, the session remembers it; when they
// end, the layers go and one still drawing stays. The next page does not turn. A reader who asks for reduced motion,
// or reads on a phone, never sees the layers. If no animation event comes, the layers still go after 4.1 s. The mouse
// over the wordmark, or the keyboard's focus on it, turns it again, at once, on every page (owner, 2026-11-22).
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers the app's fetch; the web
// app is mounted through its `mount` export at /es/videos; matchMedia is stubbed per case; sessionStorage starts empty.
// jsdom runs no CSS animation, so the test fires animationstart and animationend on the arms itself.
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const settle = () => new Promise((done) => setTimeout(done, 20));

async function open(media: { reduce?: boolean; phone?: boolean } = {}) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL) => get(String(url)));
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: (q.includes("reduce") && !!media.reduce) || (q.includes("max-width") && !!media.phone) ||
      (q.includes("min-width") && !media.phone),
    media: q, addEventListener() {}, removeEventListener() {},
  }));
  history.replaceState(null, "", "/es/videos");
  document.body.innerHTML = '<div id="root"></div>';
  const root = document.getElementById("root")!;
  await act(() => mount(root, FakePlayer as any));
  await act(settle);
  return root;
}
const mark = (root: HTMLElement) => root.querySelector("header a.df-mark")!;
const layers = (root: HTMLElement) => mark(root).querySelector(".df-layers");

describe("The DeFacto wordmark turns once per session", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  it("Case 1 · first page → layers, hidden from screen readers; start → remembered; end → layers gone", async () => {
    const root = await open();
    expect(mark(root).getAttribute("aria-label")).toBe("DeFacto, inicio");
    expect(layers(root)?.getAttribute("aria-hidden")).toBe("true");
    expect(mark(root).classList.contains("df-once")).toBe(true);
    const arms = layers(root)!.querySelector(".df-arms")!;
    await act(() => { arms.dispatchEvent(new Event("animationstart", { bubbles: true })); });
    expect(sessionStorage.getItem("df-turned")).toBe("1");
    await act(() => { arms.dispatchEvent(new Event("animationend", { bubbles: true })); });
    expect(layers(root)).toBeNull();
    expect(mark(root).classList.contains("df-once")).toBe(false);
    expect(mark(root).querySelector(".df-rest")).not.toBeNull();
  });

  it("Case 2 · the session already turned → no layers", async () => {
    sessionStorage.setItem("df-turned", "1");
    expect(layers(await open())).toBeNull();
  });

  it("Case 3 · reduced motion, or a phone → no layers", async () => {
    expect(layers(await open({ reduce: true }))).toBeNull();
    expect(layers(await open({ phone: true }))).toBeNull();
  });

  it("Case 4 · no animation event comes → the layers go after 4.1 s (delay, turn, half a second)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const root = await open();
    expect(layers(root)).not.toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(3900));
    expect(layers(root)).not.toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(300));
    expect(layers(root)).toBeNull();
  });

  it("Case 5 · the session already turned; the mouse over the wordmark → it turns at once; the end → still again", async () => {
    sessionStorage.setItem("df-turned", "1");
    const root = await open();
    expect(layers(root)).toBeNull();
    await act(() => { mark(root).dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); });
    expect(layers(root)).not.toBeNull();
    expect(mark(root).classList.contains("df-now")).toBe(true);
    const arms = layers(root)!.querySelector(".df-arms")!;
    await act(() => { arms.dispatchEvent(new Event("animationend", { bubbles: true })); });
    expect(layers(root)).toBeNull();
    await act(() => { mark(root).dispatchEvent(new FocusEvent("focusin", { bubbles: true })); });
    expect(layers(root)).not.toBeNull();
  });

  it("Case 6 · reduced motion → the mouse over the wordmark turns nothing", async () => {
    const root = await open({ reduce: true });
    await act(() => { mark(root).dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); });
    expect(layers(root)).toBeNull();
  });
});
