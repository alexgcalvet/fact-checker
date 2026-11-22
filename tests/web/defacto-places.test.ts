// @vitest-environment jsdom
// The large DeFacto mark lives on «Cómo funciona» and on the error pages (design panel, 2026-11-22; logo-spec.md §3)
//
// Story: A reader opens «Cómo funciona»: the page name sits as a small kicker, then the large mark turns once with its
// beam and halo, then holds; under it, one line: «Para que los debates busquen la realidad, no la persuasión.», then the lede and the rest. A reader who asks for
// reduced motion sees the mark still, its window lit. A reader on a page that does not exist sees the large mark, «Esta
// página no existe.» and one link home; the mark turns on load and again under the mouse. A page whose data fails to
// load shows the same mark with its own line.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers the app's fetch, or fails
// with 500 for the error case; the web app is mounted through its `mount` export; matchMedia is stubbed per case.
// jsdom runs no CSS animation, so the test fires animationend on the arms itself.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const settle = () => new Promise((done) => setTimeout(done, 20));
const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

async function open(path: string, { reduce = false, broken = false } = {}) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL) => (broken ? Promise.resolve(new Response("", { status: 500 })) : get(String(url))));
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: (q.includes("reduce") && reduce) || q.includes("min-width"), media: q, addEventListener() {}, removeEventListener() {},
  }));
  sessionStorage.setItem("df-turned", "1"); // the header's mark has turned already: only the large one turns
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="root"></div>';
  const root = document.getElementById("root")!;
  await act(async () => { await mount(root, FakePlayer as any).catch(() => {}); });
  await act(settle);
  return root;
}
const big = (root: HTMLElement) => root.querySelector("main .df-big");
const layers = (root: HTMLElement) => big(root)?.querySelector(".df-layers") ?? null;
const end = async (root: HTMLElement) => {
  const arms = layers(root)!.querySelector(".df-arms")!;
  await act(() => { arms.dispatchEvent(new Event("animationend", { bubbles: true })); });
};

describe("The large DeFacto mark on «Cómo funciona» and the error pages", () => {
  afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

  it("Case 1 · «Cómo funciona» → the page name as a kicker, the large mark, its line, the lede; it turns once and holds", async () => {
    const root = await open("/es/como-funciona");
    const hero = root.querySelector("main.how")!.firstElementChild!;
    expect([...hero.children].map((el) => el.tagName.toLowerCase() + (el.className ? `.${String(el.className).split(" ")[0]}` : ""))).toEqual(
      ["h1", "div.df-big", "p.df-line", "p.how-lede", "a.how-to-form"]);
    expect(text(hero.querySelector("h1"))).toBe("Cómo funciona");
    expect(big(root)!.getAttribute("aria-label")).toBe("DeFacto");
    expect(text(hero.querySelector(".df-line"))).toBe("Para que los debates busquen la realidad, no la persuasión.");
    // A wrap may fall only after «realidad,»: each half keeps its words together.
    expect([...hero.querySelectorAll(".df-line > span")].map(text)).toEqual(["Para que los debates busquen la realidad,", "no la persuasión."]);
    expect(text(hero.querySelector(".how-lede"))).toBe("Mejoramos el método en público.");
    expect(layers(root)?.getAttribute("aria-hidden")).toBe("true");
    expect(layers(root)!.querySelector(".df-beam")).not.toBeNull();
    await end(root);
    expect(layers(root)).toBeNull();
    await act(() => { big(root)!.dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); });
    expect(layers(root)).toBeNull();
  });

  it("Case 2 · reduced motion → still, with the lit window and its halo; no layers", async () => {
    const root = await open("/es/como-funciona", { reduce: true });
    expect(layers(root)).toBeNull();
    expect(big(root)!.querySelector(".df-rest .df-pane")).not.toBeNull();
    expect(big(root)!.querySelector(".df-glow")).not.toBeNull();
  });

  it("Case 3 · a page that does not exist → the large mark, «Esta página no existe.», one link home; it turns again under the mouse", async () => {
    const root = await open("/es/nada-por-aqui");
    expect(big(root)).not.toBeNull();
    expect(text(root.querySelector("main p"))).toBe("Esta página no existe.");
    expect(text(root.querySelector("main a"))).toBe("Inicio");
    const links = [...root.querySelectorAll("main a")];
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/es/"]);
    expect(layers(root)).not.toBeNull();
    await end(root);
    expect(layers(root)).toBeNull();
    await act(() => { big(root)!.dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); });
    expect(layers(root)).not.toBeNull();
  });

  it("Case 4 · the video's data fails to load (500) → the large mark, its line, one link home", async () => {
    const root = await open("/es/v/debate01", { broken: true });
    expect(big(root)).not.toBeNull();
    expect(text(root.querySelector("main p"))).toBe("Algo ha fallado al cargar esta página.");
    expect(root.querySelector("main a")?.getAttribute("href")).toBe("/es/");
  });
});
