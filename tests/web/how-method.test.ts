// @vitest-environment jsdom
// S6 A1 · The page explains the method in diagrams, with details on demand
//
// Story: A reader opens `/es/como-funciona` from the header's "Cómo funciona", which is lit. They see the route of eight
// steps (Transcribir to Publicar), each with its model ("Haiku · barato", "Opus · caro", "Persona" on Aprobar, "Sin
// IA" on Publicar), the loop back with "Se mide" marked "Planeado", the tree from which each mark comes (Falso,
// Engañoso, Retórica, Evasiva, Puntualización, Contexto), the severity scale (leve up to 1,4×, moderada to 2×, grave
// over 2×) and the confidence and sources blocks. Hovering, tabbing or tapping a box opens its detail beside it, never
// over it: plain text with no heading, and no `</>` marker or details switch anywhere (owner, after review).
// `/en/how-it-works` shows the same in English.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch. Browser storage starts empty, and the window is a laptop (no phone media query matches). The web app is
// mounted at /es/como-funciona (or /en/how-it-works). The page is the element with class "how"; the route is its
// ".route" list, the loop its ".loop" list, the marks tree its ".tree", the severity scale its ".severity". A box
// with a detail is a ".box" and carries its detail in data-tip; the shared tooltip is the element with role "tooltip".
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const settle = () => new Promise((done) => setTimeout(done, 20));

const STEPS_ES: [string, string][] = [
  ["Transcribir", "Local · gratis"], ["Cribar", "Haiku · barato"], ["Leer", "Opus · caro"], ["Buscar", "Haiku · barato"],
  ["Veredicto", "Opus · caro"], ["Juzgar", "Opus · caro"], ["Aprobar", "Persona"], ["Publicar", "Sin IA"],
];
const STEPS_EN: [string, string][] = [
  ["Transcribe", "Local · free"], ["Screen", "Haiku · cheap"], ["Read", "Opus · expensive"], ["Search", "Haiku · cheap"],
  ["Verdict", "Opus · expensive"], ["Judge", "Opus · expensive"], ["Approve", "Person"], ["Publish", "No AI"],
];
const WORDS_ES = ["Falso", "Engañoso", "Retórica", "Evasiva", "Puntualización", "Contexto"];
const WORDS_EN = ["False", "Misleading", "Rhetoric", "Evasive", "Nitpick", "Context"];

async function open(path: string) {
  const { send } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) => send(String(url), init));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(async () => { await mount(root, FakePlayer as any); await settle(); });
  return root.querySelector<HTMLElement>(".how")!;
}

const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ");
const boxes = (how: HTMLElement) => [...how.querySelectorAll<HTMLElement>(".box[data-tip]")];
const tooltip = () => document.querySelector<HTMLElement>('[role="tooltip"]')!;
// A tap: a pointerdown that is not a mouse's; the tooltip shows on the next tick.
const tap = (el: HTMLElement) => act(async () => {
  el.dispatchEvent(Object.assign(new MouseEvent("pointerdown", { bubbles: true }), { pointerType: "touch" }));
  await settle();
});

describe("S6 A1 · The page explains the method in diagrams, with details on demand", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // Case 1 · /es/como-funciona → the page shows, and the header's "Cómo funciona" is the lit item
  it('Case 1 · /es/como-funciona → the page shows, and the header\'s "Cómo funciona" is the lit item', async () => {
    const how = await open("/es/como-funciona");
    expect(how).not.toBeNull();
    const lit = document.querySelector('.site-nav [aria-current="page"]');
    expect(text(lit).trim()).toBe("Cómo funciona");
  });

  // Case 2 · the route → eight steps in order, each with its model line
  it("Case 2 · the route → eight steps in order, each with its model line", async () => {
    const steps = [...(await open("/es/como-funciona")).querySelectorAll(".route > li")].map(text);
    expect(steps).toHaveLength(8);
    STEPS_ES.forEach(([name, model], i) => {
      expect(steps[i]).toContain(name);
      expect(steps[i]).toContain(model);
    });
  });

  // Case 3 · the loop → "Tú das feedback", "Se mide" marked "Planeado", "Nueva versión"
  it('Case 3 · the loop → "Tú das feedback", "Se mide" marked "Planeado", "Nueva versión"', async () => {
    const loop = [...(await open("/es/como-funciona")).querySelectorAll(".loop > li")].map(text);
    expect(loop.some((box) => box.includes("Tú das feedback"))).toBe(true);
    expect(loop.find((box) => box.includes("Se mide"))).toContain("Planeado");
    expect(loop.some((box) => box.includes("Nueva versión"))).toBe(true);
    expect(loop.filter((box) => box.includes("Planeado"))).toHaveLength(1);
  });

  // Case 4 · the marks tree, the severity scale, confidence and sources → each one shows
  it("Case 4 · the marks tree, the severity scale, confidence and sources → each one shows", async () => {
    const how = await open("/es/como-funciona");
    for (const word of WORDS_ES) expect(text(how.querySelector(".tree"))).toContain(word);
    const scale = text(how.querySelector(".severity"));
    for (const part of ["Leve", "1,4×", "Moderada", "2×", "Grave"]) expect(scale).toContain(part);
    const heads = [...how.querySelectorAll("h2")].map((h) => text(h));
    expect(heads.some((h) => h.includes("Confianza"))).toBe(true);
    expect(heads.some((h) => h.includes("Fuentes"))).toBe(true);
  });

  // Case 5 · tabbing to the "Leer" box → its detail opens beside it, never over it: its sentence, then its facts
  it('Case 5 · tabbing to the "Leer" box → its detail opens beside it, never over it: its sentence, then its facts', async () => {
    const how = await open("/es/como-funciona");
    const leer = boxes(how).find((el) => text(el).includes("Leer"))!;
    const [lead, facts] = leer.dataset.tip!.split("\n\n");
    expect(facts).toContain("parts");
    const box = { top: 300, bottom: 380, left: 100, right: 300, width: 200, height: 80, x: 100, y: 300 };
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const rect = this.getAttribute("role") === "tooltip" ? { ...box, width: 320, height: 120 } : box;
      return { ...rect, toJSON() {} } as DOMRect;
    });
    vi.useFakeTimers();
    await act(async () => { leer.focus(); vi.advanceTimersByTime(400); });
    const tip = tooltip();
    expect(tip.hidden).toBe(false);
    const blocks = [...tip.querySelectorAll("p")].map((p) => p.textContent);
    expect(blocks).toEqual([lead, facts]);
    expect(tip.querySelector("h1, h2, h3, h4, strong"), "no heading in the detail").toBeNull();
    const top = parseFloat(tip.style.top);
    expect(top >= box.bottom || top + 120 <= box.top).toBe(true);
  });

  // Case 6 · the whole page → no "</>" marker, no "DETALLE TÉCNICO" heading in any detail, and no details switch
  it('Case 6 · the whole page → no "</>" marker, no "DETALLE TÉCNICO" in any detail, and no details switch', async () => {
    const how = await open("/es/como-funciona");
    expect(boxes(how).length).toBeGreaterThanOrEqual(8 + 3 + 6);
    expect(text(how)).not.toContain("</>");
    expect(text(how)).not.toContain("Detalles técnicos");
    for (const el of how.querySelectorAll<HTMLElement>("[data-tip]")) expect(el.dataset.tip).not.toContain("DETALLE TÉCNICO");
    expect(how.querySelector('[role="switch"]')).toBeNull();
  });

  // Case 7 · a tap on the "Buscar" box → its detail opens at once; a second tap closes it
  it('Case 7 · a tap on the "Buscar" box → its detail opens at once; a second tap closes it', async () => {
    const how = await open("/es/como-funciona");
    const buscar = boxes(how).find((el) => text(el).includes("Buscar"))!;
    await tap(buscar);
    expect(tooltip().hidden).toBe(false);
    expect(tooltip().querySelector("p")!.textContent).toBe(buscar.dataset.tip!.split("\n\n")[0]);
    await tap(buscar);
    expect(tooltip().hidden).toBe(true);
  });

  // Case 8 · /en/how-it-works → "How it works" lit, the same steps, models, loop, marks and severity in English
  it('Case 8 · /en/how-it-works → "How it works" lit, the same steps, models, loop, marks and severity in English', async () => {
    const how = await open("/en/how-it-works");
    expect(text(document.querySelector('.site-nav [aria-current="page"]')).trim()).toBe("How it works");
    const steps = [...how.querySelectorAll(".route > li")].map(text);
    expect(steps).toHaveLength(8);
    STEPS_EN.forEach(([name, model], i) => {
      expect(steps[i]).toContain(name);
      expect(steps[i]).toContain(model);
    });
    expect(text(how.querySelector(".loop"))).toContain("Planned");
    for (const word of WORDS_EN) expect(text(how.querySelector(".tree"))).toContain(word);
    const scale = text(how.querySelector(".severity"));
    for (const part of ["Minor", "1.4×", "Moderate", "2×", "Serious"]) expect(scale).toContain(part);
    expect(boxes(how)[0].dataset.tip).toMatch(/^The text and who speaks\./);
    expect(text(how)).not.toContain("</>");
  });

  // Case 9 · a mouse over the "Juzgar" box → its detail opens after 300 ms, beside it, never over it
  it('Case 9 · a mouse over the "Juzgar" box → its detail opens after 300 ms, beside it, never over it', async () => {
    const how = await open("/es/como-funciona");
    const juzgar = boxes(how).find((el) => text(el).includes("Juzgar"))!;
    const box = { top: 300, bottom: 380, left: 100, right: 300, width: 200, height: 80, x: 100, y: 300 };
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const rect = this.getAttribute("role") === "tooltip" ? { ...box, width: 320, height: 120 } : box;
      return { ...rect, toJSON() {} } as DOMRect;
    });
    vi.useFakeTimers();
    await act(async () => {
      juzgar.dispatchEvent(Object.assign(new MouseEvent("pointerover", { bubbles: true }), { pointerType: "mouse" }));
      vi.advanceTimersByTime(299);
    });
    expect(tooltip().hidden, "not before 300 ms").toBe(true);
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(tooltip().hidden).toBe(false);
    expect(tooltip().querySelector("p")!.textContent).toBe(juzgar.dataset.tip!.split("\n\n")[0]);
    const top = parseFloat(tooltip().style.top);
    expect(top >= box.bottom || top + 120 <= box.top).toBe(true);
  });
});
