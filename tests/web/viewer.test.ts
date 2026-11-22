// @vitest-environment jsdom
// The viewer (S1): what shows over the video, the panel in full screen, and our own control bar on the player.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch, and
// a fake YouTube player (tests/support/youtube_fake.ts) for the embed. Fake timers drive the app's 250 ms poll; React's
// act lets each render finish. The app is mounted at /es/v/debate01, and the video plays from second 50: the flag at
// 0:45 ("cifra inventada 5") is the one being said. The judge's nitpick at 16:20 is a context note.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { clusters } from "../../src/web/src/Viewer";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function playing(at = 50, path = "/es/v/debate01") {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL) => get(String(url)));
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  const player = FakePlayer.last!;
  await act(async () => {
    player.ready();
    player.play(at);
    vi.advanceTimersByTime(250);
  });
  return { root, player };
}

const button = (root: HTMLElement, label: string) => root.querySelector<HTMLElement>(`button[aria-label="${label}"]`)!;
const card = (root: HTMLElement) => root.querySelector<HTMLElement>('.stage article[aria-label="Aviso de ahora"]');
const click = (el: HTMLElement) => act(async () => el.click());

describe("the viewer over the video", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Owner review 2026-11-22: under the byline, one card per guest (face crop, name, role, "Ficha →") leads to the
  // profile; "Comparar" comes last, only with two or more guests.
  it('shows a card per guest of a debate, each face its half of the thumbnail, then "Comparar"', async () => {
    const { root } = await playing();
    const cards = [...root.querySelectorAll<HTMLAnchorElement>(".about .guest-card")];
    expect(cards.map((a) => a.getAttribute("href"))).toEqual(["/es/v/debate01/ana", "/es/v/debate01/luis"]);
    expect(cards.map((a) => a.querySelector(".guest-name")!.textContent)).toEqual(["Ana", "Luis"]);
    for (const a of cards) {
      expect(a.textContent).toContain("Ficha →");
      const img = a.querySelector("img")!;
      expect(img.getAttribute("src")).toBe("https://i.ytimg.com/vi/debate01/hqdefault.jpg");
      expect(img.getAttribute("alt")).toBe("");
      expect(img.getAttribute("aria-hidden")).toBe("true");
    }
    expect(cards.map((a) => a.querySelector(".face")!.className)).toEqual(["face left", "face right"]);
    const row = root.querySelector(".about .guests")!;
    expect(row.lastElementChild!.getAttribute("href")).toBe("/es/v/debate01/comparar");
  });

  it("shows one card in an interview, for the guest, with the centre of the thumbnail and no Comparar", async () => {
    const { root } = await playing(50, "/es/v/intervw1");
    const cards = [...root.querySelectorAll<HTMLAnchorElement>(".about .guest-card")];
    expect(cards.map((a) => a.getAttribute("href"))).toEqual(["/es/v/intervw1/pablo"]);
    expect(cards[0].querySelector(".face")!.className).toBe("face");
    expect(root.querySelector('.about a[href$="/comparar"]')).toBeNull();
  });

  it("embeds YouTube without its own controls, so its full screen never hides ours", async () => {
    const { player } = await playing();
    expect(player.options.playerVars).toMatchObject({ controls: 0, fs: 0, playsinline: 1 });
  });

  it("shows the flag being said as a card with the panel open, until the setting turns it off", async () => {
    const { root } = await playing();
    expect(card(root)?.textContent).toContain("cifra inventada 5");
    await click(button(root, "Ajustes de los avisos"));
    await click(root.querySelector<HTMLElement>('[role="dialog"] input[type="checkbox"]')!);
    expect(card(root)).toBeNull();
  });

  it("shows the flag being said as a card once the panel is hidden, and drops it once read", async () => {
    const { root, player } = await playing();
    await click(button(root, "Ocultar el panel de avisos"));
    expect(card(root)?.textContent).toContain("cifra inventada 5");
    expect(card(root)?.textContent).toContain("Falso");
    await act(async () => {
      player.reach(60);
      vi.advanceTimersByTime(250);
    });
    expect(card(root)).toBeNull();
  });

  it("opens the panel as a side sheet in full screen, where a flag seeks, and × closes it", async () => {
    const { root, player } = await playing();
    await click(button(root, "Pantalla completa"));
    expect(root.querySelector(".stage.full")).not.toBeNull();
    expect(card(root)?.textContent).toContain("cifra inventada 5");
    await click(button(root, "Abrir el panel de avisos"));
    const sheet = root.querySelector<HTMLElement>('.stage aside[aria-label="Avisos"]')!;
    expect(sheet.querySelectorAll("li > article").length).toBe(12);
    await click(sheet.querySelector<HTMLElement>('button[aria-label="Ir a 20:10"]')!);
    expect(player.seeks).toEqual([[1210, true]]);
    await click(sheet.querySelector<HTMLElement>('button[aria-label="Cerrar"]')!);
    expect(root.querySelector(".stage aside")).toBeNull();
  });

  it("shows a judge's nitpick as a card named Puntualización, with its reason, the judge's note and its source", async () => {
    const { root } = await playing(985);
    expect(root.querySelector(".stage .pill")).toBeNull();
    const shown = card(root)!;
    expect(shown.textContent).toContain("Puntualización");
    expect(shown.textContent).toContain("Puntualización: Invented judge reason.");
    expect(shown.querySelector("a.source")).not.toBeNull();
  });

  it("plays and pauses from our own bar, and a mark on the bar seeks there", async () => {
    const { root, player } = await playing();
    await click(button(root, "Pausa"));
    expect(player.pauses).toBe(1);
    await click(button(root, "20:10 · Engañoso"));
    expect(player.seeks).toEqual([[1210, true]]);
    expect(root.querySelector('aside button.text[aria-expanded="true"]')?.textContent).toContain("Engañoso");
  });

  it("leaves context notes off the bar, and a click a few pixels from a mark goes to that flag and opens it", async () => {
    const { root, player } = await playing();
    expect(root.querySelector('.lane button[aria-label^="16:20"]')).toBeNull();
    // The lane is 3600 px for the 3600 s video: 1 px is 1 s. A click at 1214 s lands 4 px past the flag at 20:10.
    const lane = root.querySelector<HTMLElement>(".lane")!;
    lane.getBoundingClientRect = () => ({ left: 0, width: 3600 }) as DOMRect;
    await act(async () => lane.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: 1214 })));
    expect(player.seeks.at(-1)).toEqual([1210, true]);
    expect(root.querySelector('aside button.text[aria-expanded="true"]')?.textContent).toContain("Engañoso");
    // Far from any flag, it seeks to the point itself.
    await act(async () => lane.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: 3000 })));
    expect(player.seeks.at(-1)).toEqual([3000, true]);
  });

  it("counts nitpicks among the flags in the panel head, and the filter splits them (Puntualización) from context notes", async () => {
    const { root } = await playing();
    const panel = root.querySelector<HTMLElement>('aside[aria-label="Avisos"]')!;
    const rows = () => [...panel.querySelectorAll<HTMLElement>("li > article")];
    const named = (word: string) => rows().filter((r) => [...r.querySelectorAll(".head .word")].some((w) => w.textContent === word)).length;
    const [notes, nitpicks] = [named("Contexto"), named("Puntualización")];
    expect(nitpicks).toBeGreaterThan(0);
    // A nitpick counts as a flag; only the plain context notes stay out of the count.
    expect(panel.querySelector("h2")!.textContent).toBe(`${rows().length - notes} avisos`);
    const chip = (word: string) => [...panel.querySelectorAll<HTMLElement>('[role="group"] button')].find((b) => b.textContent!.startsWith(word))!;
    // The invented debate has nitpicks and no plain context note, so it shows no Contexto chip.
    expect(chip("Contexto")?.textContent ?? null).toBe(notes ? `Contexto ${notes}` : null);
    expect(chip("Puntualización").textContent).toBe(`Puntualización ${nitpicks}`);
    await click(chip("Puntualización"));
    expect(rows().length).toBe(nitpicks);
    expect(named("Puntualización")).toBe(nitpicks);
  });

  it("joins only the marks within 12 px of a cluster's first mark, so a dense video keeps its marks apart", () => {
    // A 100 s video on an 800 px lane: 12 px is 1.5 s. Flags every 0.6 s form threes; they never chain into one cluster.
    const flag = (t: number, label = "misleading") => ({ id: String(t), t, speaker: "A", quote: "q", type: "inaccuracy", label }) as any;
    const out = clusters([0, 0.6, 1.2, 1.8, 2.4].map((t) => flag(t)).concat(flag(3, "false")), 100, 800);
    expect(out.map((c) => c.flags.map((f) => f.t))).toEqual([[0, 0.6, 1.2], [1.8, 2.4, 3]]);
    expect(out.map((c) => c.mark)).toEqual(["enganoso", "falso"]);
    // The last cluster leads with its false claim, at 3 s: its mark sits there, and a click opens it.
    expect(out.map((c) => c.lead.t)).toEqual([0, 3]);
  });

  it("turns captions on by loading a new player at the same second, as the API allows only on load", async () => {
    const { root, player } = await playing();
    await click(button(root, "Subtítulos"));
    expect(player.destroyed).toBe(true);
    const next = FakePlayer.last!;
    expect(next).not.toBe(player);
    expect(next.options.playerVars).toMatchObject({ cc_load_policy: 1, start: 50, autoplay: 1 });
  });

  it("sets the volume from our slider, and the mute button mutes", async () => {
    const { root, player } = await playing();
    const slider = root.querySelector<HTMLInputElement>('input[aria-label="Volumen"]')!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(slider, "40");
      slider.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(player.volume).toBe(40);
    await click(button(root, "Silenciar"));
    expect(player.muted).toBe(true);
  });

  it("rests the bar 3 s after the last pointer while playing, wakes it on a pointer move, and never rests it while paused", async () => {
    const { root, player } = await playing();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const stage = root.querySelector<HTMLElement>(".stage")!;
    const wait = (ms: number) => act(async () => vi.advanceTimersByTime(ms));
    const move = () => act(async () => stage.dispatchEvent(new Event("pointermove", { bubbles: true })));
    await move();
    await wait(2900);
    expect(stage.classList.contains("resting")).toBe(false);
    await wait(200);
    expect(stage.classList.contains("resting")).toBe(true);
    await move();
    expect(stage.classList.contains("resting")).toBe(false);
    await act(async () => {
      player.pauseVideo();
      player.options.events.onStateChange({ target: player, data: 2 });
    });
    await wait(10000);
    expect(stage.classList.contains("resting")).toBe(false);
  });
});

// The viewer's say on a flag (S2), past the acceptance tests: the viewer already agreed to share, and the card over the
// video at second 1212 is the flag at 20:10.
describe("the viewer's say on a flag", () => {
  async function saying(fails = 0) {
    const { send } = await apiCollector();
    const posts: string[] = [];
    vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        if (fails-- > 0) return Promise.reject(new TypeError("offline"));
        posts.push(String(url));
      }
      return send(String(url), init);
    });
    localStorage.setItem("fc-share", "yes");
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    history.replaceState(null, "", "/es/v/debate01");
    document.body.innerHTML = '<div id="app"></div>';
    const root = document.getElementById("app")!;
    await act(() => mount(root, FakePlayer as any));
    await act(async () => {
      FakePlayer.last!.ready();
      FakePlayer.last!.play(1212);
      vi.advanceTimersByTime(250);
    });
    return { root, posts };
  }
  const named = (box: HTMLElement, text: string) => [...box.querySelectorAll<HTMLElement>("button")].find((b) => b.textContent!.trim() === text)!;
  const tap = (el: HTMLElement) => act(async () => { el.click(); await new Promise((done) => setTimeout(done, 20)); });
  const type = (box: HTMLTextAreaElement, text: string) => act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, text);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });

  afterEach(() => {
    localStorage.clear();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('folds a sent mark into one line, and "Cambiar" brings the pills back with the mark pressed', async () => {
    const { root } = await saying();
    await tap(named(card(root)!, "Correcto"));
    expect(card(root)!.querySelector(".mine")!.textContent).toBe("Tu marca: Correcto · Cambiar");
    await tap(named(card(root)!, "Cambiar"));
    expect(named(card(root)!, "Correcto").getAttribute("aria-pressed")).toBe("true");
  });

  it("opens the box with the focus in it, and Esc closes it unsent", async () => {
    const { root, posts } = await saying();
    await tap(named(card(root)!, "Matizar"));
    const box = card(root)!.querySelector("textarea")!;
    expect(document.activeElement).toBe(box);
    await act(async () => { box.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(card(root)!.querySelector("textarea")).toBeNull();
    expect(posts).toEqual([]);
  });

  it('keeps the text when a send fails, and "Reintentar" sends it', async () => {
    const { root, posts } = await saying(1);
    await tap(named(card(root)!, "Matizar"));
    await type(card(root)!.querySelector("textarea")!, "Falta el año");
    await tap(named(card(root)!, "Enviar"));
    expect(card(root)!.textContent).toContain("No se pudo enviar");
    expect(card(root)!.querySelector("textarea")!.value).toBe("Falta el año");
    await tap(named(card(root)!, "Reintentar"));
    expect(posts).toEqual(["/api/feedback"]);
    expect(card(root)!.textContent).toContain("Tu marca: Matizado");
  });
});

// The viewer on a phone in portrait (brand spec §19.7): a stubbed matchMedia answers the phone's query, and the page
// scrolls the window, which jsdom cannot: scrollTo is a spy. The video plays from second 50, so the flag at 0:45 is
// being said.
describe("the viewer on a phone", () => {
  let scrolls: ReturnType<typeof vi.fn>;
  async function onPhone(at = 50) {
    vi.stubGlobal("matchMedia", (media: string) => ({ matches: media.includes("max-width"), media, addEventListener() {}, removeEventListener() {} }));
    scrolls = vi.fn();
    vi.stubGlobal("scrollTo", scrolls);
    return playing(at);
  }
  const strip = (root: HTMLElement) => root.querySelector<HTMLElement>('.now[aria-label="Aviso de ahora"]');
  const sheet = (label: string) => document.querySelector<HTMLElement>(`[role="dialog"][aria-label="${label}"]`);
  const named = (box: HTMLElement, text: string) => [...box.querySelectorAll<HTMLElement>("button")].find((b) => b.textContent!.trim() === text)!;
  const follow = (root: HTMLElement) => root.querySelector<HTMLInputElement>('.panel-head input[role="switch"]')!;

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("draws no card over the video: the Ahora strip under it shows the flag being said, then a quiet line between flags", async () => {
    const { root, player } = await onPhone();
    expect(card(root)).toBeNull();
    expect(root.querySelector(".stage .notice")).toBeNull();
    expect(strip(root)!.textContent).toContain("Falso");
    expect(strip(root)!.textContent).toContain("0:45");
    expect(strip(root)!.textContent).toContain("cifra inventada 5");
    await act(async () => {
      player.reach(60);
      vi.advanceTimersByTime(250);
    });
    expect(strip(root)!.textContent).toBe("Sin avisos en este tramo");
  });

  it('shows or hides the strip with "Mostrar el aviso actual", and offers no card size or side', async () => {
    const { root } = await onPhone();
    await click(button(root, "Ajustes de los avisos"));
    const settings = root.querySelector<HTMLElement>('[role="dialog"][aria-label="Ajustes de los avisos"]')!;
    expect(settings.textContent).toContain("Mostrar el aviso actual");
    expect(settings.querySelector('[aria-label="Tamaño del texto"]')).toBeNull();
    await click(settings.querySelector<HTMLElement>('input[type="checkbox"]')!);
    expect(strip(root)).toBeNull();
  });

  it("opens the flag of the strip in a sheet with its actions; writing pauses the video, cancel plays it, and × closes the sheet", async () => {
    const { root, player } = await onPhone();
    await click(strip(root)!.querySelector("button")!);
    const open = sheet("Aviso de ahora")!;
    expect(open.textContent).toContain("cifra inventada 5");
    expect(["Correcto", "Injusto", "Matizar"].every((a) => named(open, a))).toBe(true);
    await click(named(open, "Matizar"));
    expect(player.pauses).toBe(1);
    await click(named(open, "Cancelar"));
    expect(player.state).toBe(1);
    await click(button(open, "Cerrar"));
    expect(sheet("Aviso de ahora")).toBeNull();
  });

  it("seeks and opens the sheet on a tap on a row, and Esc closes it", async () => {
    const { root, player } = await onPhone();
    await click(button(root, "Ir a 20:10"));
    expect(player.seeks).toEqual([[1210, true]]);
    expect(sheet("Aviso de ahora")!.textContent).toContain("Engañoso");
    expect(named(sheet("Aviso de ahora")!, "Correcto")).toBeDefined();
    await act(async () => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); });
    expect(sheet("Aviso de ahora")).toBeNull();
  });

  // Owner, 2026-11-22: the guests' cards stay on the page, under the byline; "Más" no longer holds them.
  it('shows the guests under the byline, leaves the verdict summary out, and "Más" opens the title, the summary and the AI line', async () => {
    const { root } = await onPhone();
    expect(root.querySelector(".summary")).toBeNull();
    expect(root.querySelector(".about .guests")).not.toBeNull();
    await click(named(root.querySelector(".about")!, "Más"));
    const info = sheet("Sobre el vídeo")!;
    expect(info.querySelector(".info-title")!.textContent).toBe(root.querySelector("h1")!.textContent);
    expect(info.querySelector(".guests")).toBeNull();
    expect(info.querySelector(".summary")).not.toBeNull();
    expect(info.textContent).toContain("Análisis automático con IA");
  });

  it('turns "Seguir el vídeo" off on a manual scroll, without the floating pill, and on again with a jump to the lit row', async () => {
    const { root } = await onPhone();
    expect(follow(root).checked).toBe(true);
    await act(async () => root.querySelector("ol")!.dispatchEvent(new Event("touchmove", { bubbles: true })));
    expect(follow(root).checked).toBe(false);
    expect(root.querySelector(".back")).toBeNull();
    scrolls.mockClear();
    await click(follow(root));
    expect(follow(root).checked).toBe(true);
    expect(scrolls).toHaveBeenCalledOnce();
  });
});
