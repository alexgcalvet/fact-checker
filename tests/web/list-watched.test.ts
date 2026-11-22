// @vitest-environment jsdom
// S9 A2 · Each video says if it is new, started or watched
//
// Story: A reader watches 4 minutes of a 40-minute video in the viewer and comes back to the list. That video reads
// "Empezado" with a bar under its thumbnail filled to a tenth, in the list and in the grid. A video they watched to the
// end reads "Visto" with a full bar. A video published 3 days ago that they never opened reads "Nuevo"; one published
// 10 days ago reads nothing. Ten seconds of a video leave it unmarked. Thumbnails sit dimmed at rest and light up under
// the pointer or focus; the duration and the bar stay undimmed. In another browser, nothing is marked.
//
// Setup: the list is the invented archive of tests/support/list_fakes.ts, dated from today: v12 published yesterday
// (the lead), v01 3 days ago, v02 10 days ago, the rest older. Two invented videos of tests/support/api_fakes.ts join it: debate01 (40 minutes,
// 20 days old) and intervw1 (30 minutes, 3 days old); their viewers are served by the invented collector, and a fake
// YouTube player (tests/support/youtube_fake.ts) plays them under fake timers. The web app is mounted through its own
// `mount` export; coming back to the list mounts it again. Each case starts with an empty browser storage.
import { act } from "react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { asPhone, text, VIDEOS } from "../support/list_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const ago = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
const LISTED = [
  ...VIDEOS.map((v, i) => ({ ...v, published_at: i === 0 ? ago(3) : i === 1 ? ago(10) : i === 11 ? ago(1) : ago(30 + i) })),
  { ...VIDEOS[3], video_id: "debate01", title: "Debate inventado", duration: 2400, published_at: ago(20) },
  { ...VIDEOS[4], video_id: "intervw1", title: "Entrevista inventada", duration: 1800, published_at: ago(3) },
];

let requests: [string, RequestInit | undefined][] = [];
async function at(path: string) {
  const { get } = await apiCollector();
  requests = [];
  vi.stubGlobal("fetch", async (url: string | URL, init?: RequestInit) => {
    requests.push([String(url), init]);
    return String(url) === "/api/videos" ? Response.json({ videos: LISTED }) : get(String(url));
  });
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  FakePlayer.last = undefined;
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

/** Opens the viewer of `id`, plays it from `from` to `to` seconds of `duration`, and fires the end if `ended`. */
async function watch(id: string, from: number, to: number, duration: number, ended = false) {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  await at(`/es/v/${id}`);
  const player = FakePlayer.last!;
  await act(async () => {
    player.ready();
    player.play(from, duration);
    vi.advanceTimersByTime(250);
  });
  await act(async () => {
    player.reach(to);
    vi.advanceTimersByTime(1000);
  });
  if (ended) await act(async () => player.options.events.onStateChange({ target: player, data: 0 }));
  vi.useRealTimers();
}

/** The row or the card of a video in the list. */
const item = (root: HTMLElement, id: string) => root.querySelector(`a[href="/es/v/${id}"]`)!.closest("li")!;
const bar = (root: HTMLElement, id: string) => item(root, id).querySelector<HTMLElement>(".watched > span");
const words = (el: Element) => ["Nuevo", "Empezado", "Visto"].filter((w) => new RegExp(`(^|\\W)${w}(\\W|$)`).test(text(el)));

describe("S9 A2 · Each video says if it is new, started or watched", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Case 1 · 4 minutes of a 40-minute video → «Empezado» and a bar at a tenth, in the rows and in the grid
  it("Case 1 · 4 of 40 minutes of debate01 → «Empezado», bar 10 %, in the rows and in the grid", async () => {
    await watch("debate01", 0, 240, 2400);
    let root = await at("/es/videos");
    expect(words(item(root, "debate01"))).toEqual(["Empezado"]);
    expect(bar(root, "debate01")!.style.width).toBe("10%");
    root = await at("/es/videos?vista=cuadricula");
    expect(words(item(root, "debate01"))).toEqual(["Empezado"]);
    expect(bar(root, "debate01")!.style.width).toBe("10%");
  });

  // Case 2 · a video watched to the end → «Visto» and a full bar; from 90 % it already reads «Visto»
  it("Case 2 · intervw1 played to its end → «Visto», full bar; debate01 at 91 % → «Visto»", async () => {
    await watch("intervw1", 1700, 1790, 1800, true);
    await watch("debate01", 2000, 2184, 2400);
    const root = await at("/es/videos");
    expect(words(item(root, "intervw1"))).toEqual(["Visto"]);
    expect(bar(root, "intervw1")!.style.width).toBe("100%");
    expect(words(item(root, "debate01"))).toEqual(["Visto"]);
  });

  // Case 3 · never opened: 3 days old → «Nuevo», no bar; 10 days old → nothing
  it("Case 3 · never opened → v01 (3 days old) reads «Nuevo» with no bar; v02 (10 days old) reads nothing", async () => {
    const root = await at("/es/videos");
    expect(words(item(root, "v01"))).toEqual(["Nuevo"]);
    expect(bar(root, "v01")).toBeNull();
    expect(words(item(root, "v02"))).toEqual([]);
    expect(bar(root, "v02")).toBeNull();
  });

  // Case 4 · 10 seconds of a new video → unmarked: no «Nuevo», no «Empezado», no bar
  it("Case 4 · 10 seconds of intervw1 (3 days old) → no state word and no bar", async () => {
    await watch("intervw1", 0, 10, 1800);
    const root = await at("/es/videos");
    expect(words(item(root, "intervw1"))).toEqual([]);
    expect(bar(root, "intervw1")).toBeNull();
  });

  // Case 5 · on a phone → the row says «Empezado» and carries the bar
  it("Case 5 · on a phone, 4 of 40 minutes of debate01 → its row reads «Empezado», bar 10 %", async () => {
    await watch("debate01", 0, 240, 2400);
    asPhone();
    const root = await at("/es/videos");
    expect(words(item(root, "debate01"))).toEqual(["Empezado"]);
    expect(bar(root, "debate01")!.style.width).toBe("10%");
  });

  // Case 6 · another browser (empty storage) → nothing is marked but the new videos
  it("Case 6 · another browser → debate01 unmarked, intervw1 and v01 read «Nuevo»", async () => {
    await watch("debate01", 0, 240, 2400);
    localStorage.clear();
    const root = await at("/es/videos");
    expect(words(item(root, "debate01"))).toEqual([]);
    expect(bar(root, "debate01")).toBeNull();
    expect(words(item(root, "intervw1"))).toEqual(["Nuevo"]);
  });

  // Case 7 · the progress stays in the browser: no request carries it, and blocked storage leaves the page working
  it("Case 7 · no request of the list or the viewer carries the progress; blocked storage → the list still shows", async () => {
    const carry = () => {
      expect(requests.every(([, init]) => !init?.body && (init?.method ?? "GET") === "GET")).toBe(true);
      expect(requests.some(([url]) => /240|progress|watched|visto/i.test(url))).toBe(false);
    };
    await watch("debate01", 0, 240, 2400);
    carry();
    await at("/es/videos?vista=cuadricula");
    carry();
    vi.stubGlobal("localStorage", { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } });
    await watch("debate01", 0, 240, 2400);
    const root = await at("/es/videos");
    expect(item(root, "debate01")).toBeTruthy();
    expect(words(item(root, "v01"))).toEqual(["Nuevo"]);
  });

  // Case 8 · the rest grade: the picture sits in the graded layer; the duration and the bar sit outside it
  it("Case 8 · thumbnails dimmed at rest, lit on hover or focus; the duration and the bar outside the dimmed layer", async () => {
    await watch("debate01", 0, 240, 2400);
    for (const path of ["/es/videos", "/es/videos?vista=cuadricula"]) {
      const root = await at(path);
      const thumb = item(root, "debate01");
      expect(thumb.querySelector(".art img"), path).not.toBeNull();
      // The laptop row shows the duration in its own column (board List); the grid card carries it as a badge.
      const badge = thumb.querySelector(".badge");
      if (path.includes("cuadricula")) expect(badge, path).not.toBeNull();
      expect(badge?.closest(".art") ?? null, path).toBeNull();
      const duration = [...thumb.querySelectorAll(".num")].filter((e) => /^40:00$/.test(e.textContent!.trim()));
      expect(duration.length, `${path}: the duration shows`).toBeGreaterThan(0);
      expect(duration.every((e) => !e.closest(".art")), `${path}: the duration is undimmed`).toBe(true);
      expect(thumb.querySelector(".watched")!.closest(".art"), path).toBeNull();
    }
    const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../../src/web/src/style.css"), "utf8");
    expect(css).toMatch(/\.art\s*\{[^}]*filter:\s*var\(--grade-frame\)\s+var\(--grade-under-glass\)/);
    expect(css).toMatch(/:focus-visible \.art[^{]*\{[^}]*filter:\s*none/);
    expect(css).toMatch(/@media \(hover: hover\)\s*\{[^{}]*:hover \.art[^{]*\{[^}]*filter:\s*none/);
  });
});
