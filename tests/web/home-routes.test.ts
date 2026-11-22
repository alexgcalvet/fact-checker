// @vitest-environment jsdom
// S12 A3 · The list moves to its own address and the wordmark leads home
//
// Story: The list now opens at `/es/videos` (and `/en/videos`), with "Vídeos" lit in the pill bar; an old link
// `/es/?orden=densidad` lands on `/es/videos?orden=densidad`. On every page, the viewer included, the DeFacto wordmark
// links to `/es/` (or `/en/`); on the home page it is marked as the current page.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch: debate01 (newest) and intervw1. The window is a laptop. The web app is mounted through its own `mount`
// export at the path of each case. The header is the `header` element; the wordmark's link is its first `a`.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const settle = () => new Promise((done) => setTimeout(done, 20));
const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

async function open(path: string) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL) => get(String(url)));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  await act(settle);
  return root;
}
const wordmark = (root: HTMLElement) => root.querySelector("header")!.querySelector("a")!;

describe("S12 A3 · The list moves to its own address and the wordmark leads home", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · /es/videos → the list, «Vídeos» lit and linking to /es/videos
  it("Case 1 · /es/videos → the list «Vídeos 2», the pill «Vídeos» lit, its link /es/videos", async () => {
    const root = await open("/es/videos");
    expect(root.querySelector("main.list")).not.toBeNull();
    expect(text(root.querySelector("main.list h1"))).toBe("Vídeos 2");
    const lit = root.querySelector('.site-nav [aria-current="page"]')!;
    expect(text(lit)).toBe("Vídeos");
    expect(lit.getAttribute("href")).toBe("/es/videos");
  });

  // Case 2 · /en/videos → the English list
  it("Case 2 · /en/videos → the list in English, «Videos» lit", async () => {
    const root = await open("/en/videos");
    expect(text(root.querySelector("main.list h1"))).toBe("Videos 2");
    expect(text(root.querySelector('.site-nav [aria-current="page"]'))).toBe("Videos");
  });

  // Case 3 · an old /es/?orden=densidad link → /es/videos?orden=densidad, the list in that order, no new history entry
  it("Case 3 · /es/?orden=densidad → address /es/videos?orden=densidad, the sorted list, no new history entry", async () => {
    history.replaceState(null, "", "/es/");
    const entries = history.length;
    const root = await open("/es/?orden=densidad");
    expect(location.pathname + location.search).toBe("/es/videos?orden=densidad");
    expect(history.length).toBe(entries);
    const sort = [...root.querySelectorAll('main.list [role="search"] [aria-haspopup="listbox"]')].find((b) => text(b).startsWith("Orden"));
    expect(text(sort)).toContain("Más discutidos primero");
  });

  // Case 4 · an old /es/?orden=graves link → /es/videos?orden=falso-enganoso
  it("Case 4 · /es/?orden=graves → address /es/videos?orden=falso-enganoso", async () => {
    await open("/es/?orden=graves");
    expect(location.pathname + location.search).toBe("/es/videos?orden=falso-enganoso");
  });

  // Case 5 · owner change 2026-11-22 (second): the DeFacto wordmark leads home on every page, lit on the home page; the
  // footer holds CALVET and the X logo as one link to CALVET on X, in a new tab, never a bare letter "X"
  it("Case 5 · the DeFacto wordmark leads home on every page; the footer's CALVET + X logo link goes to X", async () => {
    for (const path of ["/es/videos", "/es/v/debate01", "/es/como-funciona", "/es/"]) {
      const link = wordmark(await open(path));
      expect(link.getAttribute("href")).toBe("/es/");
      expect(link.getAttribute("aria-label")).toBe("DeFacto, inicio");
      expect(link.getAttribute("target")).toBeNull();
      expect(link.getAttribute("aria-current")).toBe(path === "/es/" ? "page" : null);
    }
    expect(wordmark(await open("/en/v/debate01")).getAttribute("aria-label")).toBe("DeFacto, home");
    const home = await open("/es/");
    const lit = home.querySelector('.site-nav [aria-current="page"]')!;
    expect(text(lit)).toBe("Inicio");
    expect(lit.getAttribute("href")).toBe("/es/");
    const x = [...home.querySelectorAll("footer a")].filter((a) => /^https:\/\/x\.com\//.test(a.getAttribute("href") ?? ""));
    expect(x).toHaveLength(1);
    expect(x[0].getAttribute("target")).toBe("_blank");
    expect(x[0].getAttribute("rel")).toContain("noopener");
    expect(x[0].getAttribute("aria-label")).toBe("CALVET en X (se abre en otra pestaña)");
    expect(x[0].getAttribute("title")).toBe("CALVET en X");
    expect(x[0].querySelectorAll(".footer-calvet, .footer-x")).toHaveLength(2);
    expect(text(x[0])).toBe("");
    // The owner, 2026-11-22: CALVET on X opens the footer, at its far left.
    expect(home.querySelector("footer")!.firstElementChild).toBe(x[0]);
  });

  // Case 6 · every internal link to the list → /es/videos: the pill bar, the footer
  it("Case 6 · on the home page, the pill «Vídeos» and the footer «Vídeos» lead to /es/videos; nothing links to /es/?orden", async () => {
    const root = await open("/es/");
    expect([...root.querySelectorAll(".site-nav a")].find((a) => text(a) === "Vídeos")!.getAttribute("href")).toBe("/es/videos");
    const footer = [...root.querySelectorAll("footer a")].find((a) => text(a) === "Vídeos");
    expect(footer?.getAttribute("href")).toBe("/es/videos");
    expect(root.querySelectorAll('a[href^="/es/?"]').length).toBe(0);
    console.log("PASS S12 A3 · The list moves to its own address and the wordmark leads home");
  });
});
