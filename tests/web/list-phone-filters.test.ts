// @vitest-environment jsdom
// S8 A3 · On a phone, a search field and the "Filtros" sheet
//
// Story: On a phone, the list shows the heading, a full-width search field that filters as the reader types, then one
// row with "Orden" on the left and "Filtros" on the right, with a count badge when two filters are on. "Filtros" opens a
// sheet with the channels, a guest search and the language; its bone button reads "Ver 5 vídeos" and its number changes
// with each pick before the reader closes it; "Restablecer" clears them.
//
// Setup: the invented archive of tests/support/list_fakes.ts stands in for `GET /api/videos`: 12 videos, 3 also in
// English (v01, v02, v09), 6 on "Canal Norte" (v01–v06), Marta Ruiz in v05, v06, v07, v11 and v12, Ana Pérez in v01,
// v02 and v08. The window is a phone: every max-width media query matches. The web app is mounted through its own
// `mount` export. The sheet is the dialog named "Filtros"; the guest search is its input "Buscar persona".
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { asPhone, button, click, open, params, shown, text, tight, type } from "../support/list_fakes";

const field = (root: HTMLElement) => root.querySelector<HTMLInputElement>('input[placeholder="Buscar título, canal o persona"]')!;
const sheet = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Filtros"]');
const filters = (root: HTMLElement) => button(root.querySelector('[role="search"]')!, "Filtros")!;
const see = () => button(sheet()!, "Ver")!;

describe("S8 A3 · On a phone, a search field and the «Filtros» sheet", () => {
  beforeEach(() => asPhone());
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the heading, then one search field that filters as the reader types; ?q=perez
  it("Case 1 · phone /es/videos → the heading «Vídeos 12», one search field; «perez» typed → v01, v02, v08 and ?q=perez", async () => {
    const root = await open("/es/videos");
    expect(tight(root.querySelector("h1"))).toBe("Vídeos12");
    expect(root.querySelectorAll('input[placeholder="Buscar título, canal o persona"]')).toHaveLength(1);
    await type(field(root), "perez");
    expect(shown(root)).toEqual(["v01", "v02", "v08"]);
    expect(params()).toEqual({ q: "perez" });
  });

  // Case 2 · one row: «Orden» on the left, «Filtros» with no number on the right; no menus, no kind chips, no toggle
  it("Case 2 · at rest → «Orden …» then «Filtros» with no number; no Canal or Invitado menu, no kind chip, no view toggle", async () => {
    const root = await open("/es/videos");
    const bar = root.querySelector<HTMLElement>('[role="search"]')!;
    const sort = [...bar.querySelectorAll<HTMLElement>('[aria-haspopup="listbox"]')].find((b) => text(b).startsWith("Orden"));
    expect(sort, "«Orden»").toBeDefined();
    expect(tight(filters(root))).toBe("Filtros");
    expect(sort!.compareDocumentPosition(filters(root)) & Node.DOCUMENT_POSITION_FOLLOWING, "«Orden» comes first").toBeTruthy();
    expect([...root.querySelectorAll('[aria-haspopup="listbox"]')].filter((b) => /^(Canal|Invitado)/.test(text(b)))).toHaveLength(0);
    expect(button(bar, "Retórica")).toBeUndefined();
    expect(root.querySelector('button[aria-label="Cuadrícula"]')).toBeNull();
  });

  // Case 3 · two filters on → «Filtros 2»
  it("Case 3 · ?idioma=en&canal=canal-norte → «Filtros 2», v01 and v02", async () => {
    const root = await open("/es/videos?idioma=en&canal=canal-norte");
    expect(tight(filters(root))).toBe("Filtros2");
    expect(shown(root)).toEqual(["v01", "v02"]);
  });

  // Case 4 · «Filtros» → the sheet with the channels, the guest search and the language; «Ver 12 vídeos»
  it("Case 4 · tap «Filtros» → the sheet «Filtros» with «Canal Norte 6», «Buscar persona», «Marta Ruiz 5», «También en inglés 3», «Ver 12 vídeos»; no kinds", async () => {
    const root = await open("/es/videos");
    expect(sheet()).toBeNull();
    await click(filters(root));
    const s = sheet()!;
    expect(s).not.toBeNull();
    expect(tight(button(s, "Canal Norte"))).toBe("CanalNorte6");
    expect(s.querySelector('input[placeholder="Buscar persona"]'), "the guest search").not.toBeNull();
    expect(tight(button(s, "Marta Ruiz"))).toBe("MartaRuiz5");
    expect(tight(button(s, "También en inglés"))).toBe("Tambiéneninglés3");
    expect(button(s, "Retórica"), "no kind of aviso").toBeUndefined();
    expect(tight(see())).toBe("Ver12vídeos");
  });

  // Case 5 · each pick → the bone button's number follows it; the guest search narrows the guests; the button closes
  it("Case 5 · Marta Ruiz → «Ver 5 vídeos», Canal Norte → «Ver 2 vídeos»; «an» in the guest search shows only Ana Pérez; «Ver 2 vídeos» closes on v05, v06", async () => {
    const root = await open("/es/videos");
    await click(filters(root));
    await click(button(sheet()!, "Marta Ruiz")!);
    expect(tight(see())).toBe("Ver5vídeos");
    await click(button(sheet()!, "Canal Norte")!);
    expect(tight(see())).toBe("Ver2vídeos");
    await type(sheet()!.querySelector<HTMLInputElement>('input[placeholder="Buscar persona"]')!, "an");
    expect(button(sheet()!, "Ana Pérez")).toBeDefined();
    expect(button(sheet()!, "Luis Gómez")).toBeUndefined();
    await click(see());
    expect(sheet()).toBeNull();
    expect(shown(root).sort()).toEqual(["v05", "v06"]);
    expect(tight(filters(root))).toBe("Filtros2");
    expect(params()).toEqual({ canal: "canal-norte", invitado: "marta-ruiz" });
  });

  // Case 6 · «Restablecer» → every filter cleared, «Ver 12 vídeos»; the search and the sort stay
  it("Case 6 · on ?q=e&idioma=en&canal=canal-norte&orden=densidad, «Restablecer» → ?q=e&orden=densidad, «Filtros» with no number", async () => {
    const root = await open("/es/videos?q=e&idioma=en&canal=canal-norte&orden=densidad");
    await click(filters(root));
    await click(button(sheet()!, "Restablecer")!);
    expect(tight(see()), "every title has an «e»").toBe("Ver12vídeos");
    expect(params()).toEqual({ q: "e", orden: "densidad" });
    expect(tight(filters(root))).toBe("Filtros");
  });
});
