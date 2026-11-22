// @vitest-environment jsdom
// S5 A2 · A guest's profile shows their own-speech figures and their avisos
//
// Story: A reader opens `/es/v/debate01/ana` (Ana spoke 28:40 of the debate's voices). The page reads Ana's share of
// speaking time, her turns, her longest turn, her avisos per 10 minutes of her own speech with its level marked
// provisional ("pocos avisos" under 5, "bastantes" to 8,9, "muchos" from 9), and the whole debate's figure beside it,
// never another person's. Her two gravest avisos are pinned first, then the rest by time; a filter bar over the list
// counts each kind ("–" for a kind she has none of, which cannot be tapped); a tap on "Retórica" lists only those, and
// the address becomes `?tipo=retorica`; a tap on one of her devices in "Lo que más repite" narrows the list to it
// (`&recurso=<rule id>`), a second tap clears it. Each aviso's time opens the viewer at that second. In the viewer,
// Ana's name on a flag links to this page.
// Copy pass 2026-11-21 (owner): «Lo más grave» is «Destacados», «Los demás, en orden» is «Los demás», «Lo que más repite» is «Lo que repite», «Ad hominem» is «Ataque personal».
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch.
// Its debate01 (60 min) carries the speech of each person: Ana 1720 s in 6 turns (longest 340 s), Luis 1490 s, the host
// Marta 350 s. Ana has 6 avisos: Falso at 10:30 (gravest 1) and 0:45, Engañoso at 20:10, Retórica (ad hominem) at 7:00
// (gravest 2) and 25:00, and a Puntualización at 14:20; Luis has 6 more. So Ana gets 2,1 avisos per 10 min of her
// speech and the debate 2,2. For the levels and the "Name (role)" case the owner uploads the debate again with other
// figures. A fake YouTube player (tests/support/youtube_fake.ts) stands in for the embed.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector, debateEs, SPEECH } from "../support/api_fakes";
import EXAMPLE from "../../docs/api-examples/debate.json";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

type Collector = Awaited<ReturnType<typeof apiCollector>>;

async function open(path: string, collector?: Collector) {
  const { get } = collector ?? await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => get(String(url)));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  FakePlayer.last = undefined;
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

// The viewer of debate01 playing at `at` seconds: the card of the flag said then shows over the video.
async function playing(at: number, collector?: Collector) {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  const root = await open("/es/v/debate01", collector);
  await act(async () => {
    FakePlayer.last!.ready();
    FakePlayer.last!.play(at);
    vi.advanceTimersByTime(250);
  });
  return root;
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ");
const figures = (root: HTMLElement) => root.querySelector<HTMLElement>('section[aria-label="Sus cifras"]')!;
const avisoTimes = (root: HTMLElement, section: string) =>
  [...root.querySelectorAll(`section[aria-label="${section}"] article a[href^="/es/v/debate01?t="]`)].map((a) => text(a).trim());
const card = (root: HTMLElement) => root.querySelector<HTMLElement>('article[aria-label="Aviso de ahora"]');
// The debate uploaded again by the owner with Ana's seconds of speech changed.
const anaSpoke = (spoken_s: number) =>
  ({ ...debateEs, people: { ...SPEECH.people, Ana: { ...SPEECH.people.Ana, spoken_s } } });

describe("S5 A2 · A guest's profile shows their own-speech figures and their avisos", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Case 1 · the video call → each person's role, seconds spoken, turns and longest turn, and the voice turns
  it("Case 1 · GET /api/videos/debate01 → people and turns, as in docs/api-examples/debate.json; the interview has none", async () => {
    const { get } = await apiCollector();
    const body = (await (await get("/api/videos/debate01?lang=es")).json()) as any;
    expect(body.people).toEqual(SPEECH.people);
    expect(body.turns).toEqual(SPEECH.turns);
    expect({ people: EXAMPLE.people, turns: EXAMPLE.turns }).toEqual(SPEECH);
    const interview = (await (await get("/api/videos/intervw1?lang=es")).json()) as any;
    expect(interview).toHaveProperty("people", null);
    expect(interview).toHaveProperty("turns", null);
  });

  // Case 2 · /es/v/debate01/ana → her share, turns, longest turn, 2,1 avisos per 10 min «pocos avisos», provisional,
  // the debate's 2,2, and no other person's figure
  it("Case 2 · /es/v/debate01/ana → 48,3 %, 6 turnos, 5:40, «2,1» pocos avisos (provisional), debate 2,2, no other person", async () => {
    const root = await open("/es/v/debate01/ana");
    expect(text(root.querySelector("h1"))).toContain("Ana");
    const f = text(figures(root));
    for (const shown of ["Tiempo de palabra", "48,3 %", "28:40", "6 turnos", "5:40", "Avisos cada 10 min que habla", "2,1",
      "pocos avisos", "debate 2,2"]) {
      expect(f, shown).toContain(shown);
    }
    expect(text(root)).toMatch(/[Pp]rovisional/);
    for (const other of ["Luis", "Marta"]) expect(f, other).not.toContain(other);
  });

  // Case 3 · Ana's avisos per 10 min of her speech at the edges → 4,9 pocos, 5,0 and 8,9 bastantes, 9,0 muchos
  it("Case 3 · 4,9, 5,0, 8,9 and 9,0 avisos per 10 min → «pocos», «bastantes», «bastantes», «muchos avisos»", async () => {
    for (const [spoken, rate, level] of [[735, "4,9", "pocos avisos"], [720, "5,0", "bastantes avisos"],
      [405, "8,9", "bastantes avisos"], [400, "9,0", "muchos avisos"]] as const) {
      const collector = await apiCollector();
      await collector.owner(anaSpoke(spoken));
      const f = text(figures(await open("/es/v/debate01/ana", collector)));
      expect(f, `${spoken} s`).toContain(rate);
      expect(f, `${spoken} s`).toContain(level);
      for (const other of ["pocos avisos", "bastantes avisos", "muchos avisos"].filter((l) => l !== level)) {
        expect(f, `${spoken} s`).not.toContain(other);
      }
    }
  });

  // Case 4 · the list of avisos → her two gravest first (10:30 and 7:00), then the rest by time
  it("Case 4 · the avisos → «Lo más grave» 10:30 and 7:00 first, then 0:45, 14:20, 20:10 and 25:00 in order", async () => {
    const root = await open("/es/v/debate01/ana");
    expect(avisoTimes(root, "Destacados")).toEqual(["10:30", "7:00"]);
    expect(avisoTimes(root, "Los demás")).toEqual(["0:45", "14:20", "20:10", "25:00"]);
  });

  // Case 5 · the filter bar → each kind with her count, «–» for a kind she has none of, which cannot be tapped; a tap on
  // «Retórica» → only her Retórica avisos and the address ?tipo=retorica, which also opens that filter; her device ×2
  // reads in «Lo que más repite», and a tap on it narrows the list and the address to it, a second tap clears it
  it("Case 5 · a tap on «Retórica» → only 7:00 and 25:00, «Ad hominem ×2», ?tipo=retorica; Evasiva reads «–»", async () => {
    let root = await open("/es/v/debate01/ana");
    const bar = () => root.querySelector<HTMLElement>('nav[aria-label="Sus avisos por tipo"]')!;
    const chip = (word: string) => [...bar().querySelectorAll("button")].find((b) => text(b).includes(word))!;
    const listed = () => [...root.querySelectorAll('main article a[href^="/es/v/debate01?t="]')].map((a) => text(a).trim());
    for (const [word, count] of [["Todos", "6"], ["Falso", "2"], ["Engañoso", "1"], ["Retórica", "2"], ["Evasiva", "–"],
      ["Puntualización", "1"], ["Contexto", "–"]]) {
      expect(chip(word), word).toBeDefined();
      expect(text(chip(word)).trim(), word).toBe(`${word} ${count}`);
      expect(chip(word).disabled, word).toBe(count === "–");
    }
    expect(chip("Todos").getAttribute("aria-pressed")).toBe("true");
    await act(async () => chip("Retórica").click());
    expect(location.search).toBe("?tipo=retorica");
    expect(chip("Retórica").getAttribute("aria-pressed")).toBe("true");
    expect(listed()).toEqual(["7:00", "25:00"]);
    expect(text(root.querySelector('section[aria-label="Retórica"]'))).toContain("ataque personal");
    const repeats = root.querySelector<HTMLElement>('section[aria-label="Lo que repite"]')!;
    expect(text(repeats)).toContain("Ataque personal ×2");
    root = await open("/es/v/debate01/ana?tipo=retorica");
    expect(chip("Retórica").getAttribute("aria-pressed")).toBe("true");
    expect(listed()).toEqual(["7:00", "25:00"]);
    // The owner uploads the debate again with her 7:00 aviso as a straw man: a tap on that device narrows the list.
    const collector = await apiCollector();
    const strawMan = JSON.parse(JSON.stringify(debateEs));
    strawMan.flags.find((f: any) => f.id === "ad_hominem-11.0").label = "straw_man";
    strawMan.summary.Ana.flags["ad_hominem-11.0"].device = "straw_man";
    await collector.owner(strawMan);
    root = await open("/es/v/debate01/ana?tipo=retorica", collector);
    const device = (name: string) => [...root.querySelectorAll<HTMLButtonElement>('section[aria-label="Lo que repite"] button')]
      .find((b) => text(b).includes(name))!;
    expect(device("Hombre de paja"), "the Hombre de paja chip").toBeDefined();
    await act(async () => device("Hombre de paja").click());
    expect(location.search).toBe("?tipo=retorica&recurso=straw_man");
    expect(device("Hombre de paja").getAttribute("aria-pressed")).toBe("true");
    expect(listed()).toEqual(["7:00"]);
    await act(async () => device("Hombre de paja").click());
    expect(location.search).toBe("?tipo=retorica");
    expect(device("Hombre de paja").getAttribute("aria-pressed")).toBe("false");
    expect(listed()).toEqual(["7:00", "25:00"]);
  });

  // Case 6 · an aviso's time → the viewer at that second
  it("Case 6 · the time 10:30 links to /es/v/debate01?t=630, and that address starts the player at 630", async () => {
    const root = await open("/es/v/debate01/ana");
    const link = [...root.querySelectorAll<HTMLAnchorElement>("article a")].find((a) => text(a).trim() === "10:30")!;
    expect(link.getAttribute("href")).toBe("/es/v/debate01?t=630");
    await open("/es/v/debate01?t=630");
    expect(FakePlayer.last!.options.playerVars.start).toBe(630);
  });

  // Case 7 · in the viewer, the card of Ana's flag at 10:30 → her name links to her profile
  it("Case 7 · the viewer's card of Ana's flag → «Ana» links to /es/v/debate01/ana", async () => {
    const root = await playing(630);
    const name = card(root)?.querySelector('a[href="/es/v/debate01/ana"]');
    expect(name, "the link on the card").not.toBeNull();
    expect(text(name)).toBe("Ana");
  });

  // Case 8 · a hidden flag → it leaves her avisos, her rate and «Lo más grave»
  it("Case 8 · the owner hides her flag at 10:30 → 1,7 avisos per 10 min and no 10:30 on her profile", async () => {
    const collector = await apiCollector();
    const hid = await collector.send("/analyses/debate01/flags/false-1.0/hide?lang=es",
      { method: "POST", headers: { Authorization: "Bearer admin-secret" } });
    expect(hid.status).toBe(200);
    const root = await open("/es/v/debate01/ana", collector);
    expect(text(figures(root))).toContain("1,7");
    expect([...avisoTimes(root, "Destacados"), ...avisoTimes(root, "Los demás")]).not.toContain("10:30");
  });

  // Case 9 · a guest named «Ana Pérez (candidata)» → her link is /es/v/debate01/ana-perez, and her profile names her
  // «Ana Pérez» with the role «candidata»
  it("Case 9 · «Ana Pérez (candidata)» → /es/v/debate01/ana-perez, named «Ana Pérez», role «candidata»", async () => {
    const collector = await apiCollector();
    await collector.owner(JSON.parse(JSON.stringify(debateEs).replaceAll('"Ana"', '"Ana Pérez (candidata)"')));
    const viewer = await playing(630, collector);
    expect(card(viewer)?.querySelector('a[href="/es/v/debate01/ana-perez"]'), "the link on the card").not.toBeNull();
    vi.useRealTimers();
    const root = await open("/es/v/debate01/ana-perez", collector);
    expect(text(root.querySelector("h1")).trim()).toBe("Ana Pérez");
    expect(text(root)).toContain("candidata");
    expect(text(figures(root))).toContain("2,1");
    console.log("PASS S5 A2 · A guest's profile shows their own-speech figures and their avisos");
  });

  // S11, owner 2026-11-22: the cover is the guest's image. In a debate her half of the thumbnail, maxres first, then hq;
  // a 120 px placeholder counts as missing; when neither loads, plan C (her name on night) stays.
  it("cover · Ana's half of the maxres thumbnail, then hq, then plan C with her name", async () => {
    const root = await open("/es/v/debate01/ana");
    const cover = root.querySelector<HTMLElement>(".cover")!;
    const img = () => cover.querySelector<HTMLImageElement>("img");
    expect(img()!.getAttribute("src")).toBe("https://i.ytimg.com/vi/debate01/maxresdefault.jpg");
    expect(img()!.dataset.half).toBe("left");
    Object.defineProperty(img()!, "naturalWidth", { value: 120 });
    await act(async () => img()!.dispatchEvent(new Event("load")));
    expect(img()!.getAttribute("src")).toBe("https://i.ytimg.com/vi/debate01/hqdefault.jpg");
    await act(async () => img()!.dispatchEvent(new Event("error")));
    expect(img()).toBeNull();
    expect(text(cover).trim()).toBe("Ana");
  });
});
