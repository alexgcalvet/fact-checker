// @vitest-environment jsdom
// S9 A1 · The list switches to a grid and keeps the choice
//
// Story: A reader on `/es/videos` presses the grid button ("Cuadrícula") at the right of the toolbar. The videos show as
// cards of one height: thumbnail, a title of at most two lines in a block of fixed height (the full title on hover), one
// line "canal · fecha", and one line with the mix bar and the avisos per 10 minutes, also for a video with no avisos;
// every card in a row lines up. Filters and sort stay; the address gets `vista=cuadricula`. A reload keeps the grid,
// Back returns to the list, and "Lista" brings back the rows. Opening `/es/videos` with no `vista` on the same device
// later shows the view they last chose.
//
// Setup: the invented archive of tests/support/list_fakes.ts stands in for `GET /api/videos`: 12 videos, v01 the
// newest (29 Oct 2026, 30 minutes, 3 avisos, also in English), 6 on "Canal Norte" (v01–v06), 3 also in English (v01,
// v02, v09). One case serves a copy of v12 with no avisos. The web app is mounted through its own `mount` export, in a
// laptop window unless a case stubs a phone; a reload mounts it again at the same address. Each case starts with an
// empty browser storage. The toolbar is the element with role "search"; the view buttons are icon buttons named "Lista"
// and "Cuadrícula". A card's slots are its title block, its "canal · fecha" line and its foot line.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { asPhone, back, button, click, lead, open, params, shown, text, VIDEOS } from "../support/list_fakes";

const ALL = ["v01", "v02", "v03", "v04", "v05", "v06", "v07", "v08", "v09", "v10", "v11", "v12"];
const NORTE = ["v01", "v02", "v03", "v04", "v05", "v06"];
const cards = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>(".cards > li")];
const rows = (root: HTMLElement) => root.querySelectorAll(".row-laptop, .row-phone").length;
const toggle = (root: HTMLElement, label: "Lista" | "Cuadrícula") => root.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
const slots = (card: Element) => ({
  title: card.querySelector(".card-title"), meta: card.querySelector(".card-meta"), foot: card.querySelector(".card-foot"),
});

describe("S9 A1 · The list switches to a grid and keeps the choice", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · at rest → the rows; the toggle at the right of the toolbar, «Lista» pressed, «Cuadrícula» not
  it("Case 1 · /es/videos with no stored view → the rows; in the toolbar «Lista» pressed, «Cuadrícula» not", async () => {
    const root = await open("/es/videos");
    const bar = root.querySelector('[role="search"]')!;
    expect(bar.contains(toggle(root, "Cuadrícula")), "the toggle sits in the toolbar").toBe(true);
    expect(toggle(root, "Lista")!.getAttribute("aria-pressed")).toBe("true");
    expect(toggle(root, "Cuadrícula")!.getAttribute("aria-pressed")).toBe("false");
    expect(rows(root)).toBeGreaterThan(0);
    expect(cards(root)).toHaveLength(0);
  });

  // Case 2 · «Cuadrícula» → 12 cards, no lead, ?vista=cuadricula; a card: thumbnail, title with its full text on hover,
  // «Canal Norte · 29 oct · EN», the mix bar and «1,0/10′»
  it("Case 2 · press «Cuadrícula» → 12 cards, no lead, ?vista=cuadricula; v01's card: thumbnail, title, «Canal Norte · 29 oct · EN», mix bar, «1,0/10′»", async () => {
    const root = await open("/es/videos");
    await click(toggle(root, "Cuadrícula")!);
    expect(params()).toEqual({ vista: "cuadricula" });
    expect(toggle(root, "Cuadrícula")!.getAttribute("aria-pressed")).toBe("true");
    expect(rows(root)).toBe(0);
    expect(lead(root)).toBeUndefined();
    expect(cards(root)).toHaveLength(12);
    expect(shown(root)).toEqual(ALL);
    const first = cards(root)[0];
    const { title, meta, foot } = slots(first);
    expect(first.querySelector("img")!.getAttribute("src")).toContain("/v01/");
    expect(text(title)).toBe("Debate de la vivienda");
    expect(title!.getAttribute("title"), "the full title on hover").toBe("Debate de la vivienda");
    expect(text(meta)).toBe("Canal Norte · 29 oct · EN");
    expect(foot!.querySelector(".mix"), "the mix bar").not.toBeNull();
    expect(text(foot)).toContain("1,0/10′");
    expect(text(slots(cards(root)[2]).meta), "no EN without English").toBe("Canal Norte · 27 oct");
  });

  // Case 3 · every card has every slot, a video with no avisos too: an empty bar and «0,0/10′»; the slots have fixed heights
  it("Case 3 · every card has its title block, its «canal · fecha» line and its foot line; with 0 avisos, an empty bar and «0,0/10′»", async () => {
    const zero = { ...VIDEOS[11], flags: 0, counts: { falso: 0, enganoso: 0, retorica: 0, evasiva: 0, puntualizacion: 0, contexto: 0 } };
    const root = await open("/es/videos?vista=cuadricula", [...VIDEOS.slice(0, 11), zero]);
    for (const card of cards(root)) {
      const { title, meta, foot } = slots(card);
      expect(title && meta && foot, text(card)).toBeTruthy();
      expect(foot!.querySelector(".mix"), text(card)).not.toBeNull();
    }
    const empty = slots(cards(root).at(-1)!).foot!;
    expect(empty.querySelector(".mix .seg"), "an empty bar").toBeNull();
    expect(text(empty)).toContain("0,0/10′");
    const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../../src/web/src/style.css"), "utf8");
    const block = css.match(/\.card-title\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(block, "the title block is always 44 px tall").toMatch(/(?<![-\w])height:\s*44px/);
    expect(block, "the title is clamped to two lines").toMatch(/-webkit-line-clamp:\s*2/);
  });

  // Case 4 · the grid keeps the filters and the sort: ?canal=canal-norte&orden=antiguos → the 6, oldest first
  it("Case 4 · press «Cuadrícula» on ?canal=canal-norte&orden=antiguos → 6 cards oldest first; the address keeps both", async () => {
    const root = await open("/es/videos?canal=canal-norte&orden=antiguos");
    await click(toggle(root, "Cuadrícula")!);
    expect(params()).toEqual({ canal: "canal-norte", orden: "antiguos", vista: "cuadricula" });
    expect(shown(root)).toEqual([...NORTE].reverse());
    await click(button(root.querySelector('[role="search"]')!, "También en inglés")!);
    expect(params()).toEqual({ canal: "canal-norte", idioma: "en", orden: "antiguos", vista: "cuadricula" });
    expect(cards(root)).toHaveLength(2);
  });

  // Case 5 · a reload of ?vista=cuadricula → the grid; Back after the press → the rows; «Lista» → the rows, no vista
  it("Case 5 · a reload keeps the grid; Back after the press returns to the rows; «Lista» brings the rows back", async () => {
    let root = await open("/es/videos");
    await click(toggle(root, "Cuadrícula")!);
    await back();
    expect(location.search).toBe("");
    expect(cards(root)).toHaveLength(0);
    expect(rows(root)).toBeGreaterThan(0);
    root = await open("/es/videos?vista=cuadricula");
    expect(cards(root)).toHaveLength(12);
    await click(toggle(root, "Lista")!);
    expect(location.search).toBe("");
    expect(cards(root)).toHaveLength(0);
    expect(rows(root)).toBeGreaterThan(0);
  });

  // Case 6 · the last choice is remembered: /es/videos with no vista → the grid; after «Lista», the rows
  it("Case 6 · after picking the grid, /es/videos with no vista opens the grid; after «Lista», the rows", async () => {
    let root = await open("/es/videos");
    await click(toggle(root, "Cuadrícula")!);
    root = await open("/es/videos");
    expect(cards(root)).toHaveLength(12);
    expect(toggle(root, "Cuadrícula")!.getAttribute("aria-pressed")).toBe("true");
    await click(toggle(root, "Lista")!);
    root = await open("/es/videos");
    expect(cards(root)).toHaveLength(0);
    expect(rows(root)).toBeGreaterThan(0);
  });

  // Case 7 · the address wins over the remembered view: grid remembered, ?vista=lista → the rows
  it("Case 7 · the grid remembered, /es/videos?vista=lista → the rows", async () => {
    let root = await open("/es/videos");
    await click(toggle(root, "Cuadrícula")!);
    root = await open("/es/videos?vista=lista");
    expect(cards(root)).toHaveLength(0);
    expect(rows(root)).toBeGreaterThan(0);
  });

  // Case 8 · storage blocked → the toggle still works for the page
  it("Case 8 · storage blocked → /es/videos shows the rows and «Cuadrícula» still shows the grid", async () => {
    vi.stubGlobal("localStorage", { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } });
    const root = await open("/es/videos");
    expect(rows(root)).toBeGreaterThan(0);
    await click(toggle(root, "Cuadrícula")!);
    expect(cards(root)).toHaveLength(12);
  });

  // Case 9 · a phone (board ListPhone has no toggle) → no toggle, and ?vista=cuadricula keeps the rows
  it("Case 9 · on a phone → no «Cuadrícula» toggle; /es/videos?vista=cuadricula shows the rows", async () => {
    asPhone();
    const root = await open("/es/videos?vista=cuadricula");
    expect(toggle(root, "Cuadrícula")).toBeNull();
    expect(cards(root)).toHaveLength(0);
    expect(rows(root)).toBeGreaterThan(0);
  });
});
