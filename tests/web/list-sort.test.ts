// @vitest-environment jsdom
// S4 A2 · The reader sorts the list and the link keeps it
//
// Story: On `/es/videos` the owner opens the toolbar's "Orden Más recientes primero" under the heading "Vídeos 3" and picks
// "Más discutidos primero": the rows reorder by avisos per 10 minutes, each with its rank, the lead goes, and the address
// becomes `/es/videos?orden=densidad`. A reload keeps that order; a click on the column head "Duración" sorts the longest
// first and "Orden" reads "Más largos primero"; the browser's back button returns to the previous order.
// Copy pass 2026-11-21: ranks removed (owner); the sort «graves» is now «falso-enganoso».
// S12 route move 2026-11-21
// S8 v2 top area 2026-11-22: the sentence gives way to the heading and the toolbar's "Orden <value>".
//
// Setup: a fake answer of `GET /api/videos` stands in for the app's fetch, with three invented videos whose orders
// differ: by date new0001 (20 nov), mid00001 (15 nov), old00001 (1 nov); by avisos per 10 minutes mid00001 (6,0),
// old00001 (3,0), new0001 (1,0); by length old00001 (80 min), new0001 (60 min), mid00001 (20 min). The web app is
// mounted through its own `mount` export; a reload mounts it again at the same address.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const video = (video_id: string, published_at: string, duration: number, falso: number, retorica: number) => ({
  video_id, title: `Vídeo ${video_id}`, channel: "Canal inventado", duration, published_at, type: "debate", guests: ["Ana", "Luis"],
  flags: falso + retorica, langs: ["es"], counts: { falso, enganoso: 0, retorica, evasiva: 0, puntualizacion: 0, contexto: 0 },
});
const VIDEOS = [
  video("new0001", "2026-11-20", 3600, 2, 4), // 6 avisos in 60 min: 1,0
  video("mid00001", "2026-11-15", 1200, 6, 6), // 12 avisos in 20 min: 6,0
  video("old00001", "2026-11-01", 4800, 20, 4), // 24 avisos in 80 min: 3,0
];

async function open(path: string) {
  vi.stubGlobal("fetch", async (url: string | URL) =>
    (String(url) === "/api/videos" ? Response.json({ videos: VIDEOS }) : new Response("{}", { status: 404 })));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ");
const order = (root: HTMLElement) =>
  [...new Set([...root.querySelectorAll<HTMLAnchorElement>('a[href^="/es/v/"]')].map((a) => a.getAttribute("href")!.slice(6)))];
const sortButton = (root: HTMLElement) =>
  [...root.querySelectorAll('[role="search"] [aria-haspopup="listbox"]')].find((b) => text(b).trim().startsWith("Orden"))!;
const sentence = (root: HTMLElement) => text(sortButton(root));
const lead = (root: HTMLElement) => [...root.querySelectorAll("article")].find((a) => text(a).includes("Lo último"));
const click = (el: Element) => act(async () => (el as HTMLElement).click());

describe("S4 A2 · The reader sorts the list and the link keeps it", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · at rest → "3 vídeos · los más recientes primero", newest first with its lead
  it("Case 1 · /es/ → «Vídeos 3», «Orden Más recientes primero», newest first, with the lead", async () => {
    const root = await open("/es/videos");
    expect(text(root.querySelector("h1")).replace(/ /g, "")).toBe("Vídeos3");
    expect(sentence(root)).toContain("Más recientes primero");
    expect(order(root)).toEqual(["new0001", "mid00001", "old00001"]);
    expect(lead(root)).toBeDefined();
  });

  // Case 2 · the sort word → "Más discutidos primero" → by density, ranked, no lead, ?orden=densidad
  it("Case 2 · pick «Más discutidos primero» → by avisos per 10 min, ranked, no lead, /es/videos?orden=densidad", async () => {
    const root = await open("/es/videos");
    const word = sortButton(root);
    await click(word);
    expect(word.getAttribute("aria-expanded")).toBe("true");
    const option = [...root.querySelectorAll('[role="listbox"] [role="option"]')].find((o) => text(o).includes("Más discutidos primero"))!;
    await click(option);
    expect(order(root)).toEqual(["mid00001", "old00001", "new0001"]);
    expect(root.querySelectorAll(".rank")).toHaveLength(0);
    expect(lead(root)).toBeUndefined();
    expect(location.pathname + location.search).toBe("/es/videos?orden=densidad");
    expect(sentence(root)).toContain("Más discutidos primero");
  });

  // Case 3 · a reload of /es/videos?orden=densidad → the same order
  it("Case 3 · a reload of /es/videos?orden=densidad → still by avisos per 10 min", async () => {
    const root = await open("/es/videos?orden=densidad");
    expect(order(root)).toEqual(["mid00001", "old00001", "new0001"]);
    expect(sentence(root)).toContain("Más discutidos primero");
  });

  // Case 4 · the column head "Duración" → longest first, "Más largos primero", ?orden=largos
  it("Case 4 · a click on «Duración» → longest first, «Orden Más largos primero», /es/videos?orden=largos", async () => {
    const root = await open("/es/videos?orden=densidad");
    const head = [...root.querySelectorAll("button")].find((b) => b.textContent?.startsWith("Duración"))!;
    await click(head);
    expect(order(root)).toEqual(["old00001", "new0001", "mid00001"]);
    expect(sentence(root)).toContain("Más largos primero");
    expect(location.search).toBe("?orden=largos");
    expect(head.textContent, "the head shows the order").toContain("↓");
  });

  // Case 5 · the browser's back button → the previous order again
  it("Case 5 · back after «Duración» → by avisos per 10 min again", async () => {
    const root = await open("/es/videos?orden=densidad");
    await click([...root.querySelectorAll("button")].find((b) => b.textContent?.startsWith("Duración"))!);
    expect(order(root)).toEqual(["old00001", "new0001", "mid00001"]);
    await act(() => new Promise<void>((done) => {
      addEventListener("popstate", () => done(), { once: true });
      history.back();
    }));
    expect(location.search).toBe("?orden=densidad");
    expect(order(root)).toEqual(["mid00001", "old00001", "new0001"]);
    expect(sentence(root)).toContain("Más discutidos primero");
  });
});
