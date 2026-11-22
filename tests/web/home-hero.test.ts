// @vitest-environment jsdom
// S12 A1 · The home page shows what this is and the newest analysis (board A7, owner 2026-11-22)
//
// Story: A reader opens `/es/`. They see "Los debates, frente a la realidad." and the line "Contrastamos cada frase con
// un método público. Ayúdanos a mejorarlo.", where «método público» leads to «Cómo funciona». Under them, the newest
// video (debate01) as one card: its title, "canal · fecha", the stat "22 frases revisadas · 12 con aviso" (12 marks,
// and 10 checked lines with no mark), a strip of 22 ticks with 12 amber, and "Ver con avisos"; the whole card leads to
// `/es/v/debate01`. No figures line and no «Lo último» label. Then the plain line, with no V. No item of the header's
// pill bar but «Inicio» is lit, and the page never names a severity or ranks anyone.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch: debate01 (newest, 60 min, Ana and Luis; 3 Falso, 3 Engañoso, 4 Retórica, 2 Puntualización) and
// intervw1 (30 min, Pablo). The window is a laptop. The web app is mounted at /es/ through its own `mount` export. The
// home page is the element with class "home"; its newest analysis is the element with class "home-lead"; the section
// line is the ".keel" element.
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

describe("S12 A1 · The home page shows what this is and the newest analysis", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · /es/ → the title, the lede with its link to «Cómo funciona», and no figures line
  it("Case 1 · /es/ → the title, the lede, «método público» → /es/como-funciona; no figures line", async () => {
    const root = await open("/es/");
    const home = root.querySelector("main.home");
    expect(home).not.toBeNull();
    expect(text(home!.querySelector("h1"))).toBe("Los debates, frente a la realidad.");
    const lede = home!.querySelector(".home-lede")!;
    expect(text(lede)).toBe("Contrastamos cada frase con un método público. Ayúdanos a mejorarlo.");
    const link = lede.querySelector("a")!;
    expect(text(link)).toBe("método público");
    expect(link.getAttribute("href")).toBe("/es/como-funciona");
    expect(home!.querySelector(".home-figures")).toBeNull();
  });

  // Case 2 · /es/ → debate01 as one card: title, source · date, the stat, a strip that matches it, the button; then the
  // plain line
  it("Case 2 · /es/ → debate01: title, «canal · fecha», «22 frases revisadas · 12 con aviso», 22 ticks with 12 amber, «Ver con avisos»; one link", async () => {
    const root = await open("/es/");
    const { videos } = await (await (await apiCollector()).get("/api/videos")).json() as { videos: { video_id: string; title: string }[] };
    const lead = root.querySelector(".home-lead")!;
    expect(text(lead)).not.toContain("Lo último");
    expect(text(lead.querySelector("h2"))).toBe(videos.find((v) => v.video_id === "debate01")!.title);
    expect(text(lead)).toContain("Invented Channel · 10 nov 2026");
    expect(text(lead.querySelector(".lead-stat"))).toBe("22 frases revisadas · 12 con aviso");
    const ticks = [...lead.querySelectorAll(".lead-strip > span")];
    expect(ticks).toHaveLength(22);
    expect(ticks.filter((t) => t.classList.contains("on"))).toHaveLength(12);
    expect(lead.querySelector(".verdicts")).toBeNull();
    const targets = new Set([...lead.querySelectorAll("a")].map((a) => a.getAttribute("href")));
    expect([...targets]).toEqual(["/es/v/debate01"]);
    expect([...lead.querySelectorAll("a")].some((a) => text(a) === "Ver con avisos")).toBe(true);
    const keel = root.querySelector("main.home .keel");
    expect(keel).not.toBeNull();
    expect(root.querySelector(".keel-v")).toBeNull();
    expect(lead.compareDocumentPosition(keel!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  // Case 3 · /es/ → only «Inicio» is lit in the header (owner change 2026-11-22), and no severity or ranking word anywhere
  it("Case 3 · /es/ → only «Inicio» lit in the pill bar; no severity or ranking word («grave», «leve», «peor», «mentira»…) on the page", async () => {
    const root = await open("/es/");
    expect([...root.querySelectorAll('.site-nav [aria-current="page"]')].map(text)).toEqual(["Inicio"]);
    const page = text(root).toLowerCase();
    for (const word of ["grave", "graves", "gravedad", "leve", "moderada", "peor", "peores", "mentira", "mentiras", "ranking"]) {
      expect(page).not.toMatch(new RegExp(`(^|[^\\p{L}])${word}([^\\p{L}]|$)`, "u"));
    }
    console.log("PASS S12 A1 · The home page shows what this is and the newest analysis");
  });
});
