// An invented archive of 12 approved videos for the list's filters (S8), and the helpers that mount the list on it.
//
// | id  | channel    | guests                        | langs | falso | retorica | title                       |
// |-----|------------|-------------------------------|-------|-------|----------|-----------------------------|
// | v01 | Canal Norte | Ana Pérez (candidata)        | es en | 1     | 2        | Debate de la vivienda       |
// | v02 | Canal Norte | Ana Pérez (candidata), Luis Gómez | es en | 0 | 1        | El presupuesto, a debate    |
// | v03 | Canal Norte | Luis Gómez                   | es    | 2     | 1        | Entrevista sobre empleo     |
// | v04 | Canal Norte | Luis Gómez                   | es    | 1     | 3        | Debate de pensiones         |
// | v05 | Canal Norte | Marta Ruiz                   | es    | 0     | 1        | La educación pública        |
// | v06 | Canal Norte | Marta Ruiz                   | es    | 3     | 2        | Entrevista de la mañana     |
// | v07 | Canal Sur   | Marta Ruiz                   | es    | 1     | 1        | Debate del agua             |
// | v08 | Canal Sur   | Ana Pérez                    | es    | 2     | 0        | Presupuestos y sanidad      |
// | v09 | Canal Sur   | Luis Gómez                   | es en | 1     | 0        | Entrevista de la tarde      |
// | v10 | Canal Sur   | Luis Gómez                   | es    | 2     | 0        | Debate fiscal               |
// | v11 | Canal Sur   | Marta Ruiz                   | es    | 1     | 0        | Debate del campo            |
// | v12 | Canal Sur   | Marta Ruiz                   | es    | 0     | 0        | Entrevista final            |
//
// v12 has 2 Engañoso, v03 one Puntualización; no video has an Evasiva. So: Retórica 7, Falso 9, Engañoso 1,
// Puntualización 1, Evasiva 0; in English 3 (v01, v02, v09), of which 2 have Retórica.
import { act } from "react";
import { vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { FakePlayer } from "./youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const video = (n: number, channel: string, guests: string[], en: boolean, falso: number, retorica: number, title: string,
  extra: Partial<Record<"enganoso" | "puntualizacion", number>> = {}) => ({
  video_id: `v${String(n).padStart(2, "0")}`, title, channel, duration: 1800, published_at: `2026-10-${String(30 - n).padStart(2, "0")}`,
  type: n % 2 ? "debate" : "interview", guests, langs: en ? ["es", "en"] : ["es"],
  flags: falso + retorica + (extra.enganoso ?? 0) + (extra.puntualizacion ?? 0),
  counts: { falso, enganoso: 0, retorica, evasiva: 0, puntualizacion: 0, contexto: 0, ...extra },
});
const NORTE = "Canal Norte";
const SUR = "Canal Sur";
export const VIDEOS = [
  video(1, NORTE, ["Ana Pérez (candidata)"], true, 1, 2, "Debate de la vivienda"),
  video(2, NORTE, ["Ana Pérez (candidata)", "Luis Gómez"], true, 0, 1, "El presupuesto, a debate"),
  video(3, NORTE, ["Luis Gómez"], false, 2, 1, "Entrevista sobre empleo", { puntualizacion: 1 }),
  video(4, NORTE, ["Luis Gómez"], false, 1, 3, "Debate de pensiones"),
  video(5, NORTE, ["Marta Ruiz"], false, 0, 1, "La educación pública"),
  video(6, NORTE, ["Marta Ruiz"], false, 3, 2, "Entrevista de la mañana"),
  video(7, SUR, ["Marta Ruiz"], false, 1, 1, "Debate del agua"),
  video(8, SUR, ["Ana Pérez"], false, 2, 0, "Presupuestos y sanidad"),
  video(9, SUR, ["Luis Gómez"], true, 1, 0, "Entrevista de la tarde"),
  video(10, SUR, ["Luis Gómez"], false, 2, 0, "Debate fiscal"),
  video(11, SUR, ["Marta Ruiz"], false, 1, 0, "Debate del campo"),
  video(12, SUR, ["Marta Ruiz"], false, 0, 0, "Entrevista final", { enganoso: 2 }),
];

/** Mounts the web app at `path` over the invented archive, or `videos`; a reload is another open at the same address. */
export async function open(path: string, videos: unknown[] = VIDEOS) {
  vi.stubGlobal("fetch", async (url: string | URL) =>
    (String(url) === "/api/videos" ? Response.json({ videos }) : new Response("{}", { status: 404 })));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

/** A phone window: every max-width media query matches. */
export const asPhone = () =>
  vi.stubGlobal("matchMedia", (media: string) => ({ matches: media.includes("max-width"), media, addEventListener() {}, removeEventListener() {} }));

export const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
/** The text without any space: "Retórica 7" and "Retórica7" read the same. */
export const tight = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, "");
/** The ids of the videos the page links to, each once, in page order. */
export const shown = (root: HTMLElement) =>
  [...new Set([...root.querySelectorAll<HTMLAnchorElement>('a[href^="/es/v/"]')].map((a) => a.getAttribute("href")!.slice(6)))];
export const lead = (root: HTMLElement) => [...root.querySelectorAll("article")].find((a) => text(a).includes("Lo último"));
export const params = () => Object.fromEntries(new URLSearchParams(location.search));
export const buttons = (within: ParentNode) => [...within.querySelectorAll<HTMLButtonElement>("button")];
/** The button whose text, spaces removed, starts with `label`, spaces removed. */
export const button = (within: ParentNode, label: string) => buttons(within).find((b) => tight(b).startsWith(label.replace(/\s+/g, "")));
export const click = (el: Element) => act(async () => (el as HTMLElement).click());
export async function type(input: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
export const back = () => act(() => new Promise<void>((done) => {
  addEventListener("popstate", () => done(), { once: true });
  history.back();
}));
