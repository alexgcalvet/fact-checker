// @vitest-environment jsdom
// S12 A2 · Checked claims, the most disputed videos and the method
//
// Story: Under the line, "Datos revisados" shows at most 3 cards of Falso or Engañoso claims of 60 % confidence or
// more, from the 5 newest videos, highest confidence first, one per speaker; each card shows its mark, the quote, the
// speaker and the time, and opens the viewer at that second. "Los más discutidos" shows up to 4 videos by avisos per
// 10 minutes, each linking to its viewer, with "Ver los 2 vídeos" to the list. "Cómo se hace" shows the route of the
// page "Cómo funciona" without Aprobar: seven numbered boxes with their model and cost line, then the open loop "Tú das
// feedback" → "Se mide" (Planeado) → "Nueva versión"; hovering, focusing or tapping a box opens its detail, as on that
// page (owner review 2026-11-22). A section with no data is not shown.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers the app's fetch:
// debate01 (60 min, 12 avisos, Ana and Luis) and intervw1 (30 min, 5 avisos, Pablo), every flag at confidence 0.8.
// Some cases replace `GET /api/videos` and the flags answers with invented ones of known confidence, kind and judge
// verdict. The web app is mounted at /es/. A section is a `section` whose `h2` names it; a card of "Datos revisados"
// is an `a` of class "fact"; a step of "Cómo se hace" is a `.route > li`, a loop box a `.loop > li`, and a box with a
// detail a ".box" with data-tip; the shared tooltip has role "tooltip". The window is a laptop unless a case stubs
// matchMedia as a phone.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const settle = () => new Promise((done) => setTimeout(done, 20));
const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

const listed = (video_id: string, published_at: string, duration: number, avisos: number) => ({
  video_id, title: `Vídeo ${video_id}`, channel: "Canal inventado", duration, published_at, type: "debate", guests: ["Ana", "Luis"],
  flags: avisos, langs: ["es"], counts: { falso: avisos, enganoso: 0, retorica: 0, evasiva: 0, puntualizacion: 0, contexto: 0 },
});
const flag = (id: string, speaker: string, t: number, type: string, label: string, confidence: number, verdict = "keep") => ({
  id, t, speaker, quote: `frase inventada ${id}`, type, label, reason: "Invented reason.", confidence,
  sources: [{ publisher: "Invented Office", url: "https://example.org/data", date: "2026-10-01" }], judge: { verdict, reason: "Invented." },
});

/** Mounts /es/ with the collector, or with an invented list and invented flags per video id. */
async function open(videos?: object[], flags?: Record<string, object[]>) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => {
    const path = String(url);
    if (videos && path === "/api/videos") return Response.json({ videos });
    const id = path.match(/^\/api\/videos\/([^/?]+)\/flags/)?.[1];
    if (flags && id) return Response.json({ flags: flags[id] ?? [] });
    return get(path);
  });
  history.replaceState(null, "", "/es/");
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  await act(settle);
  return root;
}
const find = (root: HTMLElement, title: string) =>
  [...root.querySelectorAll("main.home section")].find((s) => text(s.querySelector("h2")) === title);
/** The section of that title; the case fails here, by name, if the page has none. */
function section(root: HTMLElement, title: string) {
  const found = find(root, title);
  expect(found, `section «${title}»`).toBeDefined();
  return found;
}

describe("S12 A2 · Checked claims, the most disputed videos and the method", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the collector's two videos → 3 cards, one per speaker, each Falso or Engañoso, opening the viewer at its second
  it("Case 1 · /es/ → «Datos revisados»: 3 cards, Ana, Luis and Pablo once each, Falso or Engañoso, href /es/v/<id>?t=<s>", async () => {
    const root = await open();
    const facts = [...section(root, "Datos revisados")!.querySelectorAll<HTMLAnchorElement>("a.fact")];
    expect(facts).toHaveLength(3);
    expect(facts.map((a) => text(a.querySelector(".fact-who"))).sort()).toEqual(["Ana", "Luis", "Pablo"]);
    for (const a of facts) {
      expect(["Falso", "Engañoso"]).toContain(text(a.querySelector(".fact-kind")));
      expect(text(a.querySelector("blockquote"))).toMatch(/^«.+»$/);
      expect(a.getAttribute("href")).toMatch(/^\/es\/v\/(debate01|intervw1)\?t=\d+$/);
      expect(text(a.querySelector(".fact-time"))).toMatch(/^\d+:\d\d$/);
    }
  });

  // Case 2 · invented flags → only Falso and Engañoso of 0.6 or more, not dropped, by confidence, one per speaker
  it("Case 2 · invented flags → Bea 0.95, Dani 0.7, Fran 0.65 in that order; Retórica, 0.5, a dropped flag and Bea's second flag left out", async () => {
    const root = await open([listed("vid00001", "2026-11-20", 3600, 6)], {
      vid00001: [
        flag("a", "Bea", 100, "inaccuracy", "false", 0.95), flag("b", "Bea", 200, "inaccuracy", "misleading", 0.9),
        flag("c", "Carlos", 300, "fallacy", "ad_hominem", 0.99), flag("d", "Dani", 400, "inaccuracy", "misleading", 0.7),
        flag("e", "Eva", 500, "inaccuracy", "false", 0.5), flag("f", "Fran", 600, "inaccuracy", "false", 0.65),
        flag("g", "Gema", 700, "inaccuracy", "false", 0.99, "drop"), flag("h", "Hugo", 800, "inaccuracy", "false", 0.98, "nitpick"),
      ],
    });
    const facts = [...section(root, "Datos revisados")!.querySelectorAll<HTMLAnchorElement>("a.fact")];
    expect(facts.map((a) => text(a.querySelector(".fact-who")))).toEqual(["Bea", "Dani", "Fran"]);
    expect(facts.map((a) => a.getAttribute("href"))).toEqual(["/es/v/vid00001?t=100", "/es/v/vid00001?t=400", "/es/v/vid00001?t=600"]);
    expect(facts.map((a) => text(a.querySelector(".fact-kind")))).toEqual(["Falso", "Engañoso", "Falso"]);
  });

  // Case 3 · the collector → «Los más discutidos»: debate01 (2,0/10′) then intervw1 (1,7/10′), and «Ver los 2 vídeos» to the list
  it("Case 3 · /es/ → «Los más discutidos» lists debate01 then intervw1, each to its viewer; «Ver los 2 vídeos» → /es/videos", async () => {
    const root = await open();
    const hot = section(root, "Los más discutidos")!;
    expect([...hot.querySelectorAll("li a")].map((a) => a.getAttribute("href"))).toEqual(["/es/v/debate01", "/es/v/intervw1"]);
    const all = [...hot.querySelectorAll("a")].find((a) => text(a).startsWith("Ver los 2 vídeos"));
    expect(all?.getAttribute("href")).toBe("/es/videos");
  });

  // Case 4 · six invented videos → the 4 of most avisos per 10 minutes, in that order
  it("Case 4 · six videos → the 4 most disputed per 10 minutes, most first", async () => {
    const videos = [
      listed("one00001", "2026-11-20", 3600, 6), listed("two00001", "2026-11-19", 600, 5), listed("thr00001", "2026-11-18", 1800, 2),
      listed("fou00001", "2026-11-17", 1800, 12), listed("fiv00001", "2026-11-16", 3000, 30), listed("six00001", "2026-11-15", 600, 0),
    ];
    const root = await open(videos, {});
    const hot = section(root, "Los más discutidos")!;
    expect([...hot.querySelectorAll("li a")].map((a) => a.getAttribute("href")!.slice(6)))
      .toEqual(["fiv00001", "two00001", "fou00001", "one00001"]);
  });

  // Case 5 · no Falso or Engañoso of enough confidence → no «Datos revisados» section
  it("Case 5 · only Retórica and low-confidence flags → «Datos revisados» is not shown", async () => {
    const root = await open([listed("vid00001", "2026-11-20", 3600, 2)], {
      vid00001: [flag("c", "Carlos", 300, "fallacy", "ad_hominem", 0.99), flag("e", "Eva", 500, "inaccuracy", "false", 0.5)],
    });
    expect(find(root, "Datos revisados")).toBeUndefined();
    expect(section(root, "Los más discutidos")).toBeDefined();
  });

  // Case 6 · laptop → the route without Aprobar, its model lines, the loop, a detail on every box, and the two links
  it("Case 6 · laptop → Transcribir … Publicar without Aprobar, each with its model; the loop; links to /es/como-funciona", async () => {
    const root = await open();
    const how = section(root, "Cómo se hace")!;
    const steps = [...how.querySelectorAll(".route > li")].map(text);
    const expected: [string, string][] = [["Transcribir", "Local · gratis"], ["Cribar", "Haiku · barato"], ["Leer", "Opus · caro"],
      ["Buscar", "Haiku · barato"], ["Veredicto", "Opus · caro"], ["Juzgar", "Opus · caro"], ["Publicar", "Sin IA"]];
    expect(steps).toHaveLength(7);
    expected.forEach(([name, model], i) => {
      expect(steps[i]).toContain(String(i + 1).padStart(2, "0"));
      expect(steps[i]).toContain(name);
      expect(steps[i]).toContain(model);
    });
    expect(text(how)).not.toContain("Aprobar");
    const loop = [...how.querySelectorAll(".loop > li")].map(text);
    expect(loop.map((box) => box.replace("Planeado", "").trim())).toEqual(["Tú das feedback", "Se mide", "Nueva versión"]);
    expect(loop[1]).toContain("Planeado");
    const boxes = [...how.querySelectorAll<HTMLElement>(".box")];
    expect(boxes).toHaveLength(10);
    for (const b of boxes) {
      expect(b.dataset.tip?.length).toBeGreaterThan(10);
      expect(b.tabIndex).toBe(0);
    }
    expect([...how.querySelectorAll("a")].map((a) => a.getAttribute("href")).sort()).toEqual(["/es/como-funciona", "/es/como-funciona#feedback"]);
  });

  // Case 7 · phone → the same route; a tap on «Buscar» opens its detail at once; another tap closes it
  it("Case 7 · phone → a tap on «Buscar» opens its detail; a second tap closes it", async () => {
    vi.stubGlobal("matchMedia", (media: string) => ({ matches: media.includes("max-width"), media, addEventListener() {}, removeEventListener() {} }));
    const root = await open();
    const how = section(root, "Cómo se hace")!;
    expect(how.querySelectorAll(".route > li")).toHaveLength(7);
    const buscar = [...how.querySelectorAll<HTMLElement>(".box[data-tip]")].find((b) => text(b).includes("Buscar"))!;
    const tooltip = () => document.querySelector<HTMLElement>('[role="tooltip"]')!;
    const tap = () => act(async () => {
      buscar.dispatchEvent(Object.assign(new MouseEvent("pointerdown", { bubbles: true }), { pointerType: "touch" }));
      await settle();
    });
    await tap();
    expect(tooltip().hidden).toBe(false);
    expect(tooltip().querySelector("p")!.textContent).toBe(buscar.dataset.tip!.split("\n\n")[0]);
    await tap();
    expect(tooltip().hidden).toBe(true);
    // Phone section links read «Todos».
    expect(text([...section(root, "Datos revisados")!.querySelectorAll("a")].find((a) => a.getAttribute("href") === "/es/videos"))).toMatch(/^Todos/);
    console.log("PASS S12 A2 · Checked claims, the most disputed videos and the method");
  });
});
