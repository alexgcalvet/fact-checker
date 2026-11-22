// @vitest-environment jsdom
// S8 A1 · One toolbar narrows the list, counted and kept in the address
//
// Story: A reader opens `/es/videos` with 12 approved videos. Under the heading "Vídeos 12" one toolbar holds the search
// field, the buttons "Canal", "Invitado" and "También en inglés", then "Orden" and the view toggle; there is no chip per
// kind of aviso, and an old link with `?tipo=retorica` shows all 12. They press "También en inglés": the list shows the
// 3 that exist in English, the lead goes, the button shows it is set with a × to clear it, "3 de 12 vídeos · Quitar
// filtros" appears under the toolbar, and the address becomes `/es/videos?idioma=en`. Reloading shows the same list;
// Back returns to all 12; "Quitar filtros" brings back every video and keeps the sort.
//
// Setup: the invented archive of tests/support/list_fakes.ts stands in for `GET /api/videos`: 12 videos, Retórica in
// 7 (v01–v07), 3 also in English (v01, v02, v09). The web app is mounted through its own `mount` export, in a laptop
// window; a reload mounts it again at the same address. The toolbar is the element with role "search"; the × of a set
// filter is the button named "Quitar <filter>".
import { afterEach, describe, expect, it, vi } from "vitest";
import { back, button, click, lead, open, params, shown, text, tight } from "../support/list_fakes";

const ALL = ["v01", "v02", "v03", "v04", "v05", "v06", "v07", "v08", "v09", "v10", "v11", "v12"];
const ENGLISH = ["v01", "v02", "v09"];
const toolbar = (root: HTMLElement) => root.querySelector<HTMLElement>('[role="search"]')!;
const english = (root: HTMLElement) => button(toolbar(root), "También en inglés")!;
const clear = (root: HTMLElement, name: string) => root.querySelector<HTMLButtonElement>(`button[aria-label="Quitar ${name}"]`);
const sortMenu = (root: HTMLElement) =>
  [...toolbar(root).querySelectorAll<HTMLElement>('[aria-haspopup="listbox"]')].find((b) => text(b).startsWith("Orden"))!;

describe("S8 A1 · One toolbar narrows the list, counted and kept in the address", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · at rest → «Vídeos 12», one toolbar with the search, Canal, Invitado, También en inglés, Orden and the toggle
  it("Case 1 · /es/videos → heading «Vídeos 12»; one toolbar with search, Canal, Invitado, También en inglés, Orden, Lista, Cuadrícula", async () => {
    const root = await open("/es/videos");
    expect(tight(root.querySelector("h1"))).toBe("Vídeos12");
    expect(root.querySelectorAll('[role="search"]')).toHaveLength(1);
    const bar = toolbar(root);
    expect(bar.querySelector('input[placeholder="Buscar título, canal o persona"]'), "the search field").not.toBeNull();
    for (const label of ["Canal", "Invitado", "También en inglés"]) expect(button(bar, label), label).toBeDefined();
    expect(sortMenu(root), "Orden").toBeDefined();
    expect(bar.querySelector('button[aria-label="Lista"]'), "Lista").not.toBeNull();
    expect(bar.querySelector('button[aria-label="Cuadrícula"]'), "Cuadrícula").not.toBeNull();
    expect(english(root).getAttribute("aria-pressed")).toBe("false");
    expect(shown(root)).toEqual(ALL);
    expect(lead(root)).toBeDefined();
    expect(text(root)).not.toContain("de 12 vídeos");
  });

  // Case 2 · no chip per kind of aviso; an old ?tipo=retorica link → all 12, no filtered status
  it("Case 2 · no kind chips; /es/videos?tipo=retorica → all 12, the lead, no «de 12 vídeos»", async () => {
    const root = await open("/es/videos?tipo=retorica");
    for (const kind of ["Falso", "Engañoso", "Retórica", "Evasiva", "Puntualización"]) {
      expect(button(toolbar(root), kind), `no «${kind}» chip`).toBeUndefined();
    }
    expect(shown(root)).toEqual(ALL);
    expect(lead(root)).toBeDefined();
    expect(text(root)).not.toContain("de 12 vídeos");
  });

  // Case 3 · «También en inglés» → its 3 videos, no lead, set with a ×, «3 de 12 vídeos · Quitar filtros», ?idioma=en
  it("Case 3 · press «También en inglés» → 3 videos, no lead, the button set with a ×, «3 de 12 vídeos · Quitar filtros», /es/videos?idioma=en", async () => {
    const root = await open("/es/videos?tipo=retorica");
    await click(english(root));
    expect(shown(root)).toEqual(ENGLISH);
    expect(lead(root)).toBeUndefined();
    expect(english(root).getAttribute("aria-pressed")).toBe("true");
    expect(clear(root, "También en inglés"), "the × of the set filter").not.toBeNull();
    expect(text(root)).toContain("3 de 12 vídeos");
    expect(button(root, "Quitar filtros")).toBeDefined();
    expect(location.pathname + location.search).toBe("/es/videos?idioma=en");
  });

  // Case 4 · the × of the set filter → all 12 again, the address empty
  it("Case 4 · the × of «También en inglés» → all 12, no filter in the address", async () => {
    const root = await open("/es/videos?idioma=en");
    await click(clear(root, "También en inglés")!);
    expect(params()).toEqual({});
    expect(shown(root)).toEqual(ALL);
    expect(english(root).getAttribute("aria-pressed")).toBe("false");
  });

  // Case 5 · a reload of ?idioma=en → the same 3; Back after the press → all 12 again
  it("Case 5 · a reload of /es/videos?idioma=en → the same 3; Back after the press → all 12 and the lead", async () => {
    let root = await open("/es/videos?idioma=en");
    expect(shown(root)).toEqual(ENGLISH);
    expect(text(root)).toContain("3 de 12 vídeos");
    root = await open("/es/videos");
    await click(english(root));
    expect(shown(root)).toEqual(ENGLISH);
    await back();
    expect(location.search).toBe("");
    expect(shown(root)).toEqual(ALL);
    expect(lead(root)).toBeDefined();
  });

  // Case 6 · «Quitar filtros» → every video, and the sort stays: ?orden=densidad
  it("Case 6 · «Quitar filtros» on ?idioma=en&canal=canal-norte&orden=densidad → all 12, the address keeps ?orden=densidad", async () => {
    const root = await open("/es/videos?idioma=en&canal=canal-norte&orden=densidad");
    expect(text(root)).toContain("2 de 12 vídeos");
    await click(button(root, "Quitar filtros")!);
    expect(params()).toEqual({ orden: "densidad" });
    expect(shown(root)).toHaveLength(12);
    expect(text(root)).not.toContain("de 12 vídeos");
  });

  // Case 7 · a new sort on a filtered list → the filters stay in the address
  it("Case 7 · «Orden» → «Más discutidos primero» on ?idioma=en → ?idioma=en&orden=densidad, still the 3", async () => {
    const root = await open("/es/videos?idioma=en");
    await click(sortMenu(root));
    await click([...root.querySelectorAll('[role="option"]')].find((o) => text(o).includes("Más discutidos primero"))!);
    expect(params()).toEqual({ idioma: "en", orden: "densidad" });
    expect(shown(root).sort()).toEqual(ENGLISH);
    expect(text(sortMenu(root))).toContain("Más discutidos");
  });
});
