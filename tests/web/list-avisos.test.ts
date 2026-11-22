// @vitest-environment jsdom
// S4 A1 · The list shows every approved video with its avisos and how disputed it is
//
// Story: The owner opens `/es/videos`. The newest video, debate01, leads at the top with "Lo último"; under it every approved
// video is a row, newest first, each linking to `/es/v/<id>`. A row shows its title, channel, type, date, duration,
// languages ("ES · EN" or "ES"), its avisos with their count per verdict, the avisos per 10 minutes such as "4,9/10′"
// with its level ("muy discutido" from 6,0, "discutido" from 4,0, else "poco discutido"; the owner raised them from 4,0 and 2,5 after real data), and a mix bar. A video's
// avisos count every flag but context notes and hidden flags, puntualizaciones included.
// Edge case: WHEN no video is approved THEN the page reads "Todavía no hay vídeos analizados" with a link to "Cómo
// funciona", and no sort.
// Copy pass 2026-11-21 (owner): the lead drops its languages, and its totals "N avisos y M notas de contexto" move to the verdict row's tooltip.
// S12 route move 2026-11-21
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch.
// Its debate01 (es + en, newest, 60 min) has 3 false, 3 misleading, 4 ad hominem flags and 2 nitpicks; its intervw1
// (es, 30 min) has 3 false, 1 misleading and 1 ad hominem flag. For the levels, a fake answer of `GET /api/videos`
// lists three invented videos of known counts and lengths. The web app is mounted through its own `mount` export.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const counts = (falso: number, enganoso: number, retorica: number, evasiva: number, puntualizacion: number, contexto: number) =>
  ({ falso, enganoso, retorica, evasiva, puntualizacion, contexto });
const invented = (video_id: string, published_at: string, duration: number, c: ReturnType<typeof counts>) => ({
  video_id, title: `Vídeo ${video_id}`, channel: "Canal inventado", duration, published_at, type: "interview", guests: ["Pablo"],
  flags: Object.values(c).reduce((a, b) => a + b, 0), langs: ["es"], counts: c,
});
// At the edges of the levels: 18 avisos in 30 min → 6,0 (muy discutido); 59 in 100 min → 5,9 and 20 in 50 min → 4,0
// (discutido); 39 in 100 min → 3,9 (poco discutido). The first video has 7 context notes that never count as avisos.
const LEVELS = [
  invented("hot00001", "2026-11-20", 1800, counts(3, 4, 6, 2, 3, 7)),
  invented("warm0001", "2026-11-19", 6000, counts(59, 0, 0, 0, 0, 0)),
  invented("warm0002", "2026-11-18", 3000, counts(0, 10, 0, 10, 0, 0)),
  invented("cold0001", "2026-11-17", 6000, counts(39, 0, 0, 0, 0, 0)),
];

async function open(path: string, videos?: object[]) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) =>
    (videos && String(url) === "/api/videos" ? Response.json({ videos }) : get(String(url))));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ");
// The ids of the videos the page links to, in page order, each once.
const linked = (root: HTMLElement) =>
  [...new Set([...root.querySelectorAll<HTMLAnchorElement>('a[href^="/es/v/"]')].map((a) => a.getAttribute("href")))];
const row = (root: HTMLElement, id: string) => root.querySelector(`ol a[href="/es/v/${id}"]`)!.closest("li")!;
const cell = (el: Element, kind: string) => text(el.querySelector(`[data-kind="${kind}"]`));

describe("S4 A1 · The list shows every approved video with its avisos and how disputed it is", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the collector's list → each video's counts by verdict kind, without the hidden flags
  it("Case 1 · GET /api/videos → counts per verdict kind; a hidden flag leaves them", async () => {
    const { get, send } = await apiCollector();
    const before = ((await (await get("/api/videos")).json()) as any).videos;
    expect(before.find((v: any) => v.video_id === "debate01").counts).toEqual(counts(3, 3, 4, 0, 2, 0));
    expect(before.find((v: any) => v.video_id === "intervw1").counts).toEqual(counts(3, 1, 1, 0, 0, 0));
    const hid = await send("/analyses/debate01/flags/false-1.0/hide?lang=en", { method: "POST", headers: { Authorization: "Bearer admin-secret" } });
    expect(hid.status).toBe(200);
    const after = ((await (await get("/api/videos")).json()) as any).videos;
    expect(after.find((v: any) => v.video_id === "debate01").counts).toEqual(counts(2, 3, 4, 0, 2, 0));
  });

  // Case 2 · /es/ → debate01 leads with "Lo último", then every approved video, newest first, each linked
  it("Case 2 · /es/ → the newest video leads with «Lo último», every approved video follows newest first", async () => {
    const root = await open("/es/videos");
    const lead = [...root.querySelectorAll("article")].find((a) => text(a).includes("Lo último"));
    expect(lead, "the lead").toBeDefined();
    expect(lead!.querySelector('a[href="/es/v/debate01"]'), "the lead links to debate01").not.toBeNull();
    expect(linked(root)).toEqual(["/es/v/debate01", "/es/v/intervw1"]);
    expect(text(root)).not.toContain("pending1");
  });

  // Case 3 · a row → its title, channel, type, date, duration, languages, avisos per verdict, density and mix bar
  it("Case 3 · the interview's row → its fields, its avisos per verdict, «1,7/10′ poco discutido» and its mix bar", async () => {
    const root = await open("/es/videos");
    const r = row(root, "intervw1");
    for (const shown of ["Entrevista inventada", "Invented Channel", "Entrevista", "5 nov 2026", "30:00", "ES"]) {
      expect(text(r), shown).toContain(shown);
    }
    expect(text(r)).not.toContain("ES · EN");
    expect(cell(r, "avisos")).toContain("5");
    expect([cell(r, "falso"), cell(r, "enganoso"), cell(r, "retorica"), cell(r, "evasiva"), cell(r, "puntualizacion")])
      .toEqual(["3", "1", "1", "–", "–"]);
    expect(text(r)).toContain("1,7/10′");
    expect(text(r)).toContain("poco discutido");
    const bar = r.querySelector('[role="img"]');
    expect(bar?.getAttribute("aria-label")).toBe("3 Falso, 1 Engañoso, 1 Retórica");
  });

  // Case 4 · the lead → the debate's languages "ES · EN", its 12 avisos with 2 puntualizaciones, and 2,0 per 10 min
  it("Case 4 · the lead → ES · EN, 12 avisos with its 2 puntualizaciones, «2,0» per 10 min", async () => {
    const root = await open("/es/videos");
    const lead = [...root.querySelectorAll("article")].find((a) => text(a).includes("Lo último"))!;
    expect(lead.querySelector('[data-tip="12 avisos"]'), "the totals in the verdict row's tooltip").not.toBeNull();
    expect(text(lead)).toContain("2,0");
    expect(lead.querySelector('[role="img"]')?.getAttribute("aria-label")).toBe("3 Falso, 3 Engañoso, 4 Retórica, 2 Puntualización");
  });

  // Case 5 · avisos per 10 min at the edges → 6,0 muy discutido, 5,9 and 4,0 discutido, 3,9 poco discutido; notes apart
  it("Case 5 · 6,0, 5,9, 4,0 and 3,9 avisos per 10 min → «muy discutido», «discutido», «discutido», «poco discutido»", async () => {
    const root = await open("/es/videos", LEVELS);
    const lead = [...root.querySelectorAll("article")].find((a) => text(a).includes("Lo último"))!;
    expect(lead.querySelector('[data-tip="18 avisos y 7 notas de contexto"]'), "the totals in the verdict row's tooltip").not.toBeNull();
    expect(text(lead)).toContain("6,0");
    expect(text(lead)).toContain("muy discutido");
    for (const [id, density] of [["warm0001", "5,9/10′"], ["warm0002", "4,0/10′"]]) {
      const r = row(root, id);
      expect(text(r), id).toContain(density);
      expect(text(r), id).toContain("discutido");
      expect(text(r), id).not.toContain("muy discutido");
      expect(text(r), id).not.toContain("poco discutido");
    }
    const cold = row(root, "cold0001");
    expect(text(cold)).toContain("3,9/10′");
    expect(text(cold)).toContain("poco discutido");
    expect(text(cold), "the type").toContain("Entrevista");
    expect(cell(cold, "avisos")).toContain("39");
  });

  // Case 6 · no approved video → "Todavía no hay vídeos analizados", a link to "Cómo funciona", no sort
  it("Case 6 · no approved video → «Todavía no hay vídeos analizados», «Cómo funciona», and no sort", async () => {
    const root = await open("/es/videos", []);
    expect(text(root)).toContain("Todavía no hay vídeos analizados");
    const how = [...root.querySelectorAll("a")].find((a) => a.textContent === "Cómo funciona");
    expect(how?.getAttribute("href")).toBe("/es/como-funciona");
    expect(root.querySelector('[aria-haspopup="listbox"]')).toBeNull();
    expect(text(root)).not.toContain("primero");
  });
});
