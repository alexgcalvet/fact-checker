// @vitest-environment jsdom
// S8 A2 · Channel, guest and words narrow the list, with a way out when nothing matches
//
// Story: The reader opens the channel menu and picks one channel, then the guest menu, types "an" in its search field
// and picks "Ana Pérez"; each option shows how many videos it would leave with the other choices kept, and the address
// reads `?canal=…&invitado=ana-perez`. In the search pill they type "presupuesto" (or "PRESUPUESTO", or without
// accents), which matches titles, channels and guests' names, and the address gets `q=presupuesto`. When nothing
// matches, the page names what fails, offers "Quitar la búsqueda «presupuesto»" first, then one "Quitar «x» · N vídeos"
// button for each choice whose removal gives at least one video, then "Ver los 12 vídeos".
//
// Setup: the invented archive of tests/support/list_fakes.ts stands in for `GET /api/videos`: 12 videos, 6 on "Canal
// Norte" (v01–v06) and 6 on "Canal Sur" (v07–v12); Ana Pérez is in v01, v02 (as "Ana Pérez (candidata)") and v08;
// "presupuesto" is in the titles of v02 and v08 ("Presupuestos y sanidad"); "educación" in v05's; 3 videos also in
// English (v01, v02, v09); Marta Ruiz in v05, v06, v07, v11 and v12. The web app is
// mounted through its own `mount` export, in a laptop window. A menu is the button with a listbox popup whose text
// starts with "Canal" or "Invitado"; the search pill is the search box with the placeholder "Buscar título, canal o
// persona"; the guest menu's search field is the input next to its button.
import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { button, buttons, click, open, params, shown, text, tight, type } from "../support/list_fakes";

const menu = (root: HTMLElement, label: string) =>
  [...root.querySelectorAll<HTMLElement>('[aria-haspopup="listbox"]')].find((b) => text(b).startsWith(label))!;
const options = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>('[role="listbox"] [role="option"]')];
const option = (root: HTMLElement, label: string) => options(root).find((o) => tight(o).startsWith(label.replace(/\s+/g, "")))!;
function pill(root: HTMLElement) {
  const found = root.querySelector<HTMLInputElement>('input[placeholder="Buscar título, canal o persona"]');
  expect(found, "the search pill").not.toBeNull();
  return found!;
}

describe("S8 A2 · Channel, guest and words narrow the list, with a way out when nothing matches", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the channel menu → each channel with its count; a pick → ?canal=canal-sur, its 6 videos
  it("Case 1 · the channel menu → «Canal Norte 6», «Canal Sur 6»; pick Canal Sur → ?canal=canal-sur, v07–v12", async () => {
    const root = await open("/es/videos");
    await click(menu(root, "Canal"));
    expect(tight(option(root, "Canal Norte"))).toBe("CanalNorte6");
    expect(tight(option(root, "Canal Sur"))).toBe("CanalSur6");
    await click(option(root, "Canal Sur"));
    expect(params()).toEqual({ canal: "canal-sur" });
    expect(shown(root)).toEqual(["v07", "v08", "v09", "v10", "v11", "v12"]);
    const english = await open("/es/videos?idioma=en");
    await click(menu(english, "Canal"));
    expect(tight(option(english, "Canal Norte")), "counted with the language kept").toBe("CanalNorte2");
    expect(tight(option(english, "Canal Sur"))).toBe("CanalSur1");
  });

  // Case 2 · the guest menu with a channel on → counts with the channel kept; "an" finds Ana Pérez; a pick → both keys
  it("Case 2 · on ?canal=canal-sur the guest menu, «an» typed → only «Ana Pérez 1»; pick → &invitado=ana-perez, v08", async () => {
    const root = await open("/es/videos?canal=canal-sur");
    await click(menu(root, "Invitado"));
    expect(tight(option(root, "Marta Ruiz")), "Marta Ruiz on Canal Sur: v07, v11, v12").toBe("MartaRuiz3");
    const find = menu(root, "Invitado").parentElement!.querySelector<HTMLInputElement>("input")!;
    await type(find, "an");
    const names = options(root).map((o) => text(o)).filter((t) => !/^Tod/.test(t));
    expect(names).toHaveLength(1);
    expect(tight(option(root, "Ana Pérez")), "once, without the role; on Canal Sur only v08").toBe("AnaPérez1");
    await click(option(root, "Ana Pérez"));
    expect(params()).toEqual({ canal: "canal-sur", invitado: "ana-perez" });
    expect(location.search).toBe("?canal=canal-sur&invitado=ana-perez");
    expect(shown(root)).toEqual(["v08"]);
  });

  // Case 3 · the search pill → title words, any case, any accents; ?q=presupuesto
  it("Case 3 · «presupuesto», «PRESUPUESTO» → v02 and v08, ?q=presupuesto; «educacion» → v05", async () => {
    const root = await open("/es/videos");
    await type(pill(root), "presupuesto");
    expect(params()).toEqual({ q: "presupuesto" });
    expect(shown(root)).toEqual(["v02", "v08"]);
    await type(pill(root), "PRESUPUESTO");
    expect(shown(root)).toEqual(["v02", "v08"]);
    await type(pill(root), "educacion");
    expect(shown(root)).toEqual(["v05"]);
  });

  // Case 4 · the search matches channels and guests' names too; a reload of ?q= keeps it
  it("Case 4 · «canal sur» → its 6 videos; «perez» → Ana Pérez's 3; a reload of ?q=perez → the same 3 in the pill", async () => {
    let root = await open("/es/videos");
    await type(pill(root), "canal sur");
    expect(shown(root)).toEqual(["v07", "v08", "v09", "v10", "v11", "v12"]);
    await type(pill(root), "perez");
    expect(shown(root)).toEqual(["v01", "v02", "v08"]);
    root = await open("/es/videos?q=perez");
    expect(pill(root).value).toBe("perez");
    expect(shown(root)).toEqual(["v01", "v02", "v08"]);
  });

  // Case 5 · the "/" key → focuses the search pill
  it("Case 5 · the «/» key → the search pill takes the focus", async () => {
    const root = await open("/es/videos");
    await act(async () => { document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true, cancelable: true })); });
    expect(document.activeElement).toBe(pill(root));
  });

  // Case 6 · nothing matches with a search → the title names it; «Quitar la búsqueda» first, then the removals that help
  it("Case 6 · ?idioma=en&canal=canal-sur&q=presupuesto → no rows; «Quitar la búsqueda «presupuesto»» first, then «Quitar «x» · 1 vídeo» ×2, «Ver los 12 vídeos»", async () => {
    const root = await open("/es/videos?idioma=en&canal=canal-sur&q=presupuesto");
    expect(shown(root)).toEqual([]);
    const title = [...root.querySelectorAll("h2, h3")].find((h) => text(h).includes("presupuesto"));
    expect(title, "a title names what fails").toBeDefined();
    expect(title!.parentElement!.querySelector("p"), "no paragraph").toBeNull();
    const ways = buttons(root).map((b) => text(b)).filter((t) => t.startsWith("Quitar la") || t.startsWith("Quitar «") || t.startsWith("Ver los"));
    expect(ways[0]).toBe("Quitar la búsqueda «presupuesto»");
    expect(ways.at(-1)).toBe("Ver los 12 vídeos");
    expect(ways.slice(1, -1).sort()).toEqual(["Quitar «Canal Sur» · 1 vídeo", "Quitar «También en inglés» · 1 vídeo"]);
    await click(button(root, "Quitar «Canal Sur»")!);
    expect(params()).toEqual({ idioma: "en", q: "presupuesto" });
    expect(shown(root)).toEqual(["v02"]);
  });

  // Case 7 · nothing matches without a search → only the removals that give at least one video; «Ver los 12» shows all
  it("Case 7 · ?idioma=en&canal=canal-norte&invitado=marta-ruiz → «Quitar «También en inglés» · 2 vídeos», «Quitar «Marta Ruiz» · 2 vídeos», no Canal Norte, then «Ver los 12 vídeos»", async () => {
    const root = await open("/es/videos?idioma=en&canal=canal-norte&invitado=marta-ruiz");
    expect(shown(root)).toEqual([]);
    const ways = buttons(root).map((b) => text(b)).filter((t) => t.startsWith("Quitar «") || t.startsWith("Ver los"));
    expect(ways.at(-1)).toBe("Ver los 12 vídeos");
    expect(ways.slice(0, -1).sort(), "no «Canal Norte»: its removal leaves none").toEqual(["Quitar «Marta Ruiz» · 2 vídeos", "Quitar «También en inglés» · 2 vídeos"]);
    await click(button(root, "Ver los 12 vídeos")!);
    expect(location.search).toBe("");
    expect(shown(root)).toHaveLength(12);
  });
});
