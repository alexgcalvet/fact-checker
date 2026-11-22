// @vitest-environment jsdom
// S11 A1 · The reader downloads a square or vertical card as an image
//
// Story: On Ana Pérez's profile, a reader presses "Descargar ficha". A sheet opens (from the right on a laptop, from the
// bottom on a phone) with the formats "Cuadrada 1:1", "Vertical 4:5" and "Para imprimir", and ES · EN. They pick 4:5
// and see the owner's InterviewCard: the video's thumbnail on the plate, cut by the Fault, with the CALVET wordmark (in
// a debate, her half of the thumbnail, the first guest's half mirrored); "DEBATE · 10 NOV 2026"; her name; «the title»
// · how long she spoke of the video; the big "3 de 10" with "datos, falsos o engañosos"; the verdict bar with "2 falsos
// · 1 engañoso · 1 puntualiz. · 6 correctos"; "Peso: 2 altos · 1 medio · 2 bajos"; "Retórica y falacias" with each
// device ×n; "Esquivó 0 de 4 preguntas"; and under "Destacados" her two gravest avisos, each with its quote, minute, a
// verdict such as "Falso, peso alto.", its reason and, for a figure, its source. If the thumbnail cannot load, the
// plate is the night band. "Descargar PNG" saves a 1080 × 1350 image named after her and the video. Picking 1:1 gives a
// 1080 × 1080 image with no quote. Picking EN gives the same card in English. Every card ends with "Análisis automático
// con IA · 19 nov 2026 · Las marcas son señales, no veredictos." and no control removes it.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch. Its
// debate01 («Debate inventado», published 10 Nov 2026, 1 h long) has the invented guests Ana and Luis, in that order;
// Ana's profile is /es/v/debate01/ana. She speaks 1720 s (29 min); her summary: 10 checked claims, 2 false, 1
// misleading, 1 nitpick, 6 correct; weight 2 serious, 1 moderate, 2 minor; ad hominem ("Ataque personal") ×2; 0 of 4
// questions dodged. Her two gravest avisos: "false-1.0", a Falso rated serious at 10:30, quote «cifra inventada 1»,
// reason "Invented reason.", source "Invented Office"; then "ad_hominem-11.0", serious, at 7:00, «cifra inventada 11».
// The clock reads 19 Nov 2026. The browser cannot draw a page element into a PNG, so a fake of the drawing library
// (modern-screenshot) records the element and the size it is asked for, and the download link's click is recorded
// instead of saving a file. jsdom loads no image: the test fires the thumbnail's error event itself.
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

const drawn: { node: HTMLElement; options: { width?: number; height?: number } }[] = [];
vi.mock("../../src/web/node_modules/modern-screenshot/dist/index.mjs", () => ({
  domToBlob: async (node: HTMLElement, options: { width?: number; height?: number } = {}) => {
    drawn.push({ node, options });
    return new Blob(["png"], { type: "image/png" });
  },
}));

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const DISCLOSURE_ES = "Análisis automático con IA · 19 nov 2026 · Las marcas son señales, no veredictos.";
const DISCLOSURE_EN = "Automatic analysis with AI · 19 Nov 2026 · Marks are signals, not verdicts.";

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const sheet = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Descargar ficha"]');
const card = () => sheet()?.querySelector<HTMLElement>("[data-card]") ?? null;
const control = (name: string) =>
  [...(sheet() ?? document).querySelectorAll<HTMLElement>('button, [role="radio"], input')]
    .find((b) => text(b) === name || b.getAttribute("aria-label") === name || text(b.closest("label")) === name);
const press = async (name: string) => {
  const b = control(name);
  if (!b) throw new Error(`no control "${name}"`);
  await act(async () => b.click());
};
const saved: string[] = [];

async function profile() {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => get(String(url)));
  history.replaceState(null, "", "/es/v/debate01/ana");
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

describe("S11 A1 · The reader downloads a square or vertical card as an image", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-19T12:00:00Z"));
    drawn.length = 0;
    saved.length = 0;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      if (this.download) saved.push(this.download);
    });
    URL.createObjectURL = () => "blob:card";
    URL.revokeObjectURL = () => {};
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  // Case 1 · "Descargar ficha" on her profile → a sheet with the three formats and ES · EN
  it("Case 1 · Descargar ficha → a sheet with Cuadrada 1:1, Vertical 4:5, Para imprimir and ES · EN", async () => {
    await profile();
    expect(sheet()).toBeNull();
    await press("Descargar ficha");
    expect(sheet()).not.toBeNull();
    for (const name of ["Cuadrada 1:1", "Vertical 4:5", "Para imprimir", "ES", "EN"]) expect(control(name), name).toBeTruthy();
  });

  // Case 2 · 4:5 → the InterviewCard with every block, in Spanish
  it("Case 2 · Vertical 4:5 → the InterviewCard: kicker, name, title and time, hook, bar, Peso, devices, dodged, Destacados", async () => {
    await profile();
    await press("Descargar ficha");
    await press("Vertical 4:5");
    const c = card()!;
    expect(c.dataset.card).toBe("45");
    const said = text(c);
    for (const part of [
      "Debate · 10 nov 2026", "Ana", "«Debate inventado» · 29 min hablando de 1 h 00 min",
      "3 de 10", "datos, falsos o engañosos", "2 falsos", "1 engañoso", "1 puntualiz.", "6 correctos",
      "Peso: 2 altos · 1 medio · 2 bajos", "Retórica y falacias", "Esquivó 0 de 4 preguntas", "Destacados",
      "«cifra inventada 1»", "10:30", "Falso, peso alto.", "Invented reason.", "Invented Office",
      "«cifra inventada 11»", "7:00", "Ataque personal, peso alto.",
    ]) expect(said, part).toContain(part);
    expect(said).toMatch(/Ataque personal\s*×2/);
    expect(said.indexOf("«cifra inventada 1»")).toBeLessThan(said.indexOf("«cifra inventada 11»"));
    for (const third of ["«cifra inventada 5»", "«cifra inventada 3»"]) expect(said, "only two featured").not.toContain(third);
    expect(c.querySelector('[data-part="bar"]')).not.toBeNull();
    expect(c.querySelector('[aria-label="Calvet"], img[alt="Calvet"]')).not.toBeNull();
    for (const gone of ["Lo más grave", "Gravedad", "grave.", "no revisado"]) expect(said, gone).not.toContain(gone);
    // Case 3 · the 4:5 card has no "Frase destacada" toggle: it always shows the featured avisos
    expect(control("Frase destacada")).toBeUndefined();
    expect(sheet()!.querySelector('input[type="checkbox"]')).toBeNull();
  });

  // Case 4 · a debate → the plate shows the YouTube thumbnail, loaded for the PNG, Ana's (first guest's) left half
  it("Case 4 · debate → the plate is the video's i.ytimg.com thumbnail with crossOrigin, the left half for Ana", async () => {
    await profile();
    await press("Descargar ficha");
    await press("Vertical 4:5");
    const images = [...card()!.querySelectorAll<HTMLImageElement>('[data-part="plate"] img')];
    expect(images.length).toBeGreaterThan(0);
    for (const img of images) {
      expect(img.src).toMatch(/^https:\/\/i\.ytimg\.com\/vi\/debate01\//);
      expect(img.getAttribute("crossorigin")).toBe("anonymous");
      expect(img.dataset.half).toBe("left");
    }
    // Case 5 · the thumbnail cannot load → the plate is the night band, with no image, and the card keeps every block
    for (let i = 0; i < 3 && card()!.querySelector('[data-part="plate"] img'); i++) {
      await act(async () => card()!.querySelector('[data-part="plate"] img')!.dispatchEvent(new Event("error")));
    }
    expect(card()!.querySelector('[data-part="plate"]')).not.toBeNull();
    expect(card()!.querySelector('[data-part="plate"] img')).toBeNull();
    expect(text(card())).toContain("Destacados");
    expect(text(card()).endsWith(DISCLOSURE_ES)).toBe(true);
  });

  // Case 6 · "Descargar PNG" on 4:5 → a 1080 × 1350 image of the card, named after her and the video
  it("Case 6 · Descargar PNG on 4:5 → 1080 × 1350 PNG of the card, named ana…debate01….png", async () => {
    await profile();
    await press("Descargar ficha");
    await press("Vertical 4:5");
    await press("Descargar PNG");
    expect(drawn).toHaveLength(1);
    expect(drawn[0].node.dataset.card).toBe("45");
    expect([drawn[0].options.width, drawn[0].options.height]).toEqual([1080, 1350]);
    expect(saved).toHaveLength(1);
    expect(saved[0]).toMatch(/^ana.*debate01.*\.png$/);
  });

  // Case 7 · 1:1 → a 1080 × 1080 image with no quote
  it("Case 7 · Cuadrada 1:1 → 1080 × 1080 PNG with no quote", async () => {
    await profile();
    await press("Descargar ficha");
    await press("Cuadrada 1:1");
    const c = card()!;
    expect(c.dataset.card).toBe("11");
    expect(text(c)).toContain("Ana");
    expect(text(c)).not.toContain("cifra inventada");
    await press("Descargar PNG");
    expect(drawn.at(-1)!.node.dataset.card).toBe("11");
    expect([drawn.at(-1)!.options.width, drawn.at(-1)!.options.height]).toEqual([1080, 1080]);
    expect(saved.at(-1)).toMatch(/^ana.*debate01.*\.png$/);
  });

  // Case 8 · EN → the same card in English, with the English disclosure
  it("Case 8 · EN → the 4:5 InterviewCard in English", async () => {
    await profile();
    await press("Descargar ficha");
    await press("Vertical 4:5");
    await press("EN");
    const c = card()!;
    expect(c.dataset.card).toBe("45");
    expect(c.getAttribute("lang")).toBe("en");
    const said = text(c);
    for (const part of [
      "Debate · 10 Nov 2026", "Ana", "29 min speaking of 1 h 00 min", "3 of 10", "claims, false or misleading",
      "2 false", "6 correct", "Weight: 2 high · 1 medium · 2 low", "Rhetoric and fallacies", "Dodged 0 of 4 questions",
      "Featured", "«cifra inventada 1»", "False, high weight.",
    ]) expect(said, part).toContain(part);
    for (const gone of ["Peso", "Destacados", "Esquivó", "datos, falsos"]) expect(said, gone).not.toContain(gone);
    expect(said.endsWith(DISCLOSURE_EN)).toBe(true);
  });

  // Case 9 · every format, paper and language → the card ends with the disclosure; no control can remove it
  it("Case 9 · every format, paper and language → the card ends with the locked disclosure", async () => {
    await profile();
    await press("Descargar ficha");
    for (const [lang, disclosure] of [["ES", DISCLOSURE_ES], ["EN", DISCLOSURE_EN]]) {
      await press(lang);
      for (const format of ["Cuadrada 1:1", "Vertical 4:5", "Para imprimir"]) {
        await press(format);
        expect(text(card()).endsWith(disclosure), `${lang} ${format}`).toBe(true);
      }
      for (const paper of ["Carta", "A4"]) {
        await press(paper);
        expect(text(card()).endsWith(disclosure), `${lang} ${paper}`).toBe(true);
      }
    }
    expect(sheet()!.querySelector('input[type="checkbox"]')).toBeNull();
  });
});
