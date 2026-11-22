// @vitest-environment jsdom
// S2 A1 · The viewer agrees once before anything is sent
//
// Story: On /es/v/debate01, a viewer opens the flag at 20:10 and taps "Correcto". A question asks whether to send their
// marks anonymously, with a link to the privacy page. They answer "Sí": the mark is sent, and a later mark on another
// flag is sent with no question. Another viewer answers "No": nothing is sent, and they are not asked again on that
// browser.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch, which records each one. A fake YouTube player (tests/support/youtube_fake.ts) stands in for the embed,
// and fake timers drive the app's 250 ms poll. Browser storage starts empty. The web app is mounted through its own
// `mount` export at /es/v/debate01 and plays from second 1212: the card over the video is the flag at 20:10
// (misleading-3.0). The panel row "Ir a 10:30" opens the flag at 10:30 (false-1.0). The question is a dialog named
// "Compartir tus marcas" with the buttons "Sí" and "No".
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const settle = () => new Promise((done) => setTimeout(done, 20));

async function collector() {
  const { send, env } = await apiCollector();
  const sent: string[] = [];
  vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) => {
    sent.push(`${init?.method ?? "GET"} ${url}`);
    return send(String(url), init);
  });
  // The consent covers marks and comments; a seek (S7) is an anonymous counter with no id, sent without it.
  const posts = () => sent.filter((s) => s.startsWith("POST") && s !== "POST /api/visits");
  const rows = () => env.DB.rows("SELECT * FROM marks") as Record<string, unknown>[];
  return { posts, rows };
}

async function open(at: number) {
  history.replaceState(null, "", "/es/v/debate01");
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  const player = FakePlayer.last!;
  await act(async () => {
    player.ready();
    player.play(at);
    vi.advanceTimersByTime(250);
  });
  return root;
}

const click = (el: HTMLElement) => act(async () => { el.click(); await settle(); });
const card = (root: HTMLElement) => root.querySelector<HTMLElement>('.stage article[aria-label="Aviso de ahora"]')!;
const named = (box: HTMLElement, text: string) =>
  [...box.querySelectorAll<HTMLElement>("button")].find((b) => b.textContent!.trim() === text)!;
const question = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Compartir tus marcas"]');
// Opens the panel row of `time` and returns it.
async function row(root: HTMLElement, time: string) {
  await click(root.querySelector<HTMLElement>(`aside[aria-label="Avisos"] button[aria-label="Ir a ${time}"]`)!);
  return root.querySelector<HTMLElement>('aside[aria-label="Avisos"] button.text[aria-expanded="true"]')!.closest("article")!;
}

describe("S2 A1 · The viewer agrees once before anything is sent", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Case 1 · "Correcto" on the card at 20:10 → a question with Sí, No and the privacy link; nothing sent yet
  it('Case 1 · "Correcto" on the card at 20:10 → a question with Sí, No and the privacy link; nothing sent yet', async () => {
    const { posts, rows } = await collector();
    const root = await open(1212);
    expect(card(root).textContent).toContain("Engañoso");
    await click(named(card(root), "Correcto"));
    const box = question()!;
    expect(box).not.toBeNull();
    expect(named(box, "Sí")).toBeDefined();
    expect(named(box, "No")).toBeDefined();
    expect(box.querySelector<HTMLAnchorElement>("a")!.href).toContain("PRIVACY");
    expect(posts()).toEqual([]);
    expect(rows()).toEqual([]);
  });

  // Case 2 · "Sí" → the mark is sent; a later mark on the flag at 10:30 → sent with no question
  it('Case 2 · "Sí" → the mark is sent; a later mark on the flag at 10:30 → sent with no question', async () => {
    const { posts, rows } = await collector();
    const root = await open(1212);
    await click(named(card(root), "Correcto"));
    await click(named(question()!, "Sí"));
    expect(question()).toBeNull();
    expect(rows().map((r) => [r.flag_id, r.verdict])).toEqual([["misleading-3.0", "correct"]]);

    await click(named(await row(root, "10:30"), "Correcto"));
    expect(question()).toBeNull();
    expect(posts().filter((p) => p === "POST /marks")).toHaveLength(2);
    expect(rows().map((r) => r.flag_id).sort()).toEqual(["false-1.0", "misleading-3.0"]);
  });

  // Case 3 · "No" → nothing is sent; another mark, also after a reload → no question and nothing sent
  it('Case 3 · "No" → nothing is sent; another mark, also after a reload → no question and nothing sent', async () => {
    const { posts, rows } = await collector();
    const root = await open(1212);
    await click(named(card(root), "Correcto"));
    await click(named(question()!, "No"));
    expect(question()).toBeNull();

    await click(named(await row(root, "10:30"), "Injusto"));
    expect(question()).toBeNull();

    const again = await open(1212);
    await click(named(card(again), "Correcto"));
    expect(question()).toBeNull();
    expect(posts()).toEqual([]);
    expect(rows()).toEqual([]);
  });
});
