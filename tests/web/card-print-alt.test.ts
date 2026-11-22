// @vitest-environment jsdom
// S11 A2 · The reader prints the full sheet and copies the alt text
//
// Story: In the same sheet the reader picks "Para imprimir", then A4 or Letter. The preview shows the paper sheet: the
// wordmark, her name, six figures, who speaks when, the mix bar, every aviso with its reason (her two gravest marked
// "destacados"), a QR code to her profile and the disclosure line. "Imprimir o PDF" opens the browser's print dialog
// with only that sheet on the page. For each format, "Texto alternativo" shows a description of the card written from
// the same figures, under 1000 characters, with "Copiar". "Compartir…" opens the device's share menu with the image and
// the profile link where the device has one.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch. Its
// debate01 has the invented guests Ana and Luis and the host Marta; Ana (/es/v/debate01/ana) has 6 avisos, each with
// the reason "Invented reason.", her two gravest "false-1.0" (10:30, «cifra inventada 1») and "ad_hominem-11.0" (7:00),
// 2,1 avisos per 10 min of her speech, 6 of 10 checked claims correct and 3 of 10 false or misleading. The clock
// reads 19 Nov 2026. The browser's print dialog, clipboard and share menu are fakes that record their calls; a fake of
// the drawing library (modern-screenshot) returns a PNG blob, as the browser cannot draw a page element.
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

vi.mock("../../src/web/node_modules/modern-screenshot/dist/index.mjs", () => ({
  domToBlob: async () => new Blob(["png"], { type: "image/png" }),
}));

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const DISCLOSURE_ES = "Análisis automático con IA · 19 nov 2026 · Las marcas son señales, no veredictos.";
const PROFILE_URL = `${location.origin}/es/v/debate01/ana`;

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const sheet = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Descargar ficha"]');
const card = () => sheet()?.querySelector<HTMLElement>("[data-card]") ?? null;
const control = (name: string) =>
  [...(sheet() ?? document).querySelectorAll<HTMLElement>('button, [role="radio"], input')]
    .find((b) => text(b) === name || b.getAttribute("aria-label") === name);
const press = async (name: string) => {
  const b = control(name);
  if (!b) throw new Error(`no control "${name}"`);
  await act(async () => b.click());
};
const alt = () => sheet()!.querySelector<HTMLElement>('[aria-label="Texto alternativo"]');

async function openSheet() {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => get(String(url)));
  history.replaceState(null, "", "/es/v/debate01/ana");
  document.body.innerHTML = '<div id="app"></div>';
  await act(() => mount(document.getElementById("app")!, FakePlayer as any));
  await press("Descargar ficha");
}

describe("S11 A2 · The reader prints the full sheet and copies the alt text", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-19T12:00:00Z"));
    URL.createObjectURL = () => "blob:card";
    URL.revokeObjectURL = () => {};
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  // Case 1 · Para imprimir, A4 → the paper sheet with every part of the board
  it("Case 1 · Para imprimir · A4 → wordmark, name, six figures, who speaks when, mix bar, every aviso, QR, disclosure", async () => {
    await openSheet();
    await press("Para imprimir");
    await press("A4");
    const c = card()!;
    expect(c.dataset.card).toBe("print");
    expect(c.dataset.paper).toBe("a4");
    expect(c.querySelector('[aria-label="Calvet"], img[alt="Calvet"]')).not.toBeNull();
    expect(text(c)).toContain("Ana");
    expect(c.querySelectorAll('[data-part="figure"]')).toHaveLength(6);
    expect(text(c)).toContain("Graves cada 10 min que habla");
    const voices = c.querySelector('[data-part="voices"]')!;
    for (const who of ["Ana", "Luis", "Marta"]) expect(text(voices), who).toContain(who);
    expect(c.querySelector('[data-part="mix"]')).not.toBeNull();
    const avisos = [...c.querySelectorAll('[data-part="aviso"]')];
    expect(avisos).toHaveLength(6);
    for (const a of avisos) expect(text(a)).toContain("Invented reason.");
    expect(text(c)).toContain("1 y 2, destacados");
    expect(avisos.filter((a) => a.querySelector('[data-part="rank"]')).map((a) => text(a.querySelector('[data-part="rank"]'))))
      .toEqual(["2", "1"]);
    expect(c.querySelector(`[data-part="qr"][aria-label="${PROFILE_URL}"]`)).not.toBeNull();
    expect(text(c).endsWith(DISCLOSURE_ES)).toBe(true);
    // Case 2 · Carta → the same sheet on Letter paper
    await press("Carta");
    expect(card()!.dataset.paper).toBe("letter");
    expect(card()!.querySelectorAll('[data-part="aviso"]')).toHaveLength(6);
  });

  // Case 3 · "Imprimir o PDF" → the print dialog opens with only the paper sheet to print, at its paper size
  it("Case 3 · Imprimir o PDF → window.print with the A4 sheet as the only printed part", async () => {
    await openSheet();
    await press("Para imprimir");
    await press("A4");
    const printed: (string | undefined)[] = [];
    vi.stubGlobal("print", () => printed.push(document.documentElement.dataset.print));
    await press("Imprimir o PDF");
    expect(printed).toEqual(["a4"]);
    expect([...document.querySelectorAll("style")].some((s) => /@page\s*{[^}]*size:\s*A4/i.test(s.textContent ?? ""))).toBe(true);
    await act(async () => { dispatchEvent(new Event("afterprint")); });
    expect(document.documentElement.dataset.print).toBeUndefined();
  });

  // Case 4 · each format → an alt text from the same figures, under 1000 characters, that "Copiar" copies
  it("Case 4 · each format → Texto alternativo with her figures, < 1000 characters, copied by Copiar", async () => {
    await openSheet();
    const copied: string[] = [];
    vi.stubGlobal("navigator", { ...navigator, language: "es-ES", clipboard: { writeText: async (s: string) => { copied.push(s); } } });
    // Each format's own figures: the 4:5 InterviewCard counts false or misleading claims and names her featured avisos.
    const facts: Record<string, string[]> = {
      "Cuadrada 1:1": ["2,1", "6 de 10"],
      "Vertical 4:5": ["3 de 10", "2 falsos", "6 correctos", "Peso: 2 altos", "«cifra inventada 1»"],
      "Para imprimir": ["2,1", "6 de 10"],
    };
    for (const format of Object.keys(facts)) {
      await press(format);
      const said = text(alt());
      for (const fact of ["Ana", "Debate inventado", ...facts[format], DISCLOSURE_ES]) expect(said, `${format}: ${fact}`).toContain(fact);
      expect(said.length).toBeLessThan(1000);
      expect(text(sheet())).toContain(`${said.length}/1000`);
      await press("Copiar");
      expect(copied.at(-1)).toBe(said);
    }
  });

  // Case 5 · "Compartir…" where the device can share files → the share menu with the PNG and the profile link
  it("Case 5 · Compartir… → navigator.share with a PNG file and the profile link; no button without a share menu", async () => {
    const shared: ShareData[] = [];
    vi.stubGlobal("navigator", {
      ...navigator, language: "es-ES",
      canShare: () => true,
      share: async (data: ShareData) => { shared.push(data); },
    });
    await openSheet();
    await press("Vertical 4:5");
    await press("Compartir…");
    expect(shared).toHaveLength(1);
    expect(shared[0].url).toBe(PROFILE_URL);
    expect(shared[0].files).toHaveLength(1);
    expect(shared[0].files![0].type).toBe("image/png");
    expect(shared[0].files![0].name).toMatch(/^ana.*debate01.*\.png$/);
    // Case 6 · a device with no share menu → no "Compartir…" button
    vi.stubGlobal("navigator", { ...navigator, language: "es-ES", share: undefined, canShare: undefined });
    await openSheet();
    expect(control("Compartir…")).toBeUndefined();
  });
});
