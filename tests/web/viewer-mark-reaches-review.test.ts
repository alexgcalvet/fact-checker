// @vitest-environment jsdom
// S2 A2 · A mark from the panel or the card reaches the review page
//
// Story: After agreeing, a viewer taps "Injusto" on the card over the video for the flag at 20:10, writes "La cifra es
// del INE de 2024" and saves. The owner's review page lists a web mark "unfair" on that flag with that reason, and a
// flag comment naming the flag's rule. A mark "Correcto" from an open row of the panel shows there as "correct". The
// flag then shows the viewer's mark. Edge case: WHEN the collector's daily stop refuses the mark THEN the viewer reads
// that marks are closed for today, and the flag keeps their mark.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch; the same stub serves the fake Cloudflare Access key set (tests/support/access_fake.ts), and the
// collector gets the invented TEAM_DOMAIN and POLICY_AUD. A fake YouTube player (tests/support/youtube_fake.ts) stands
// in for the embed, and fake timers drive the app's 250 ms poll. Browser storage starts empty. The web app is mounted
// at /es/v/debate01 and plays from second 1212: the card over the video is the flag at 20:10 (misleading-3.0, label
// misleading). The panel row "Ir a 10:30" opens the flag at 10:30 (false-1.0). Whenever the question "Compartir tus
// marcas" shows, the viewer answers "Sí". The reason box is the flag's textarea, saved with "Guardar". The owner reads
// /admin/marks and /admin/feedback with an Access token. For the edge case, 10 web ids first send 5,000 marks, as the
// collector's daily stop allows.
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const REASON = "La cifra es del INE de 2024";
const settle = () => new Promise((done) => setTimeout(done, 20));

async function collector() {
  const { send, env } = await apiCollector();
  Object.assign(env, { TEAM_DOMAIN, POLICY_AUD });
  const keys = certsFetch();
  vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) =>
    String(url).startsWith(TEAM_DOMAIN) ? keys.fetch(String(url)) : send(String(url), init));
  const owner = async (path: string) => {
    const res = await send(path, { headers: { [HEADER]: await token() } });
    expect(res.status).toBe(200);
    return (await res.json()).rows as Record<string, unknown>[];
  };
  return { send, env, owner };
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

const question = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Compartir tus marcas"]');
const named = (box: HTMLElement, text: string) =>
  [...box.querySelectorAll<HTMLElement>("button")].find((b) => b.textContent!.trim() === text)!;
// A tap, then "Sí" if the question shows.
async function tap(el: HTMLElement) {
  await act(async () => { el.click(); await settle(); });
  const box = question();
  if (box) await act(async () => { named(box, "Sí").click(); await settle(); });
}
async function type(box: HTMLTextAreaElement, text: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, text);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
const card = (root: HTMLElement) => root.querySelector<HTMLElement>('.stage article[aria-label="Aviso de ahora"]')!;
async function row(root: HTMLElement, time: string) {
  await act(async () => root.querySelector<HTMLElement>(`aside[aria-label="Avisos"] button[aria-label="Ir a ${time}"]`)!.click());
  return root.querySelector<HTMLElement>('aside[aria-label="Avisos"] button.text[aria-expanded="true"]')!.closest("article")!;
}
// "Injusto" on the card at 20:10, the reason, then "Guardar".
async function unfair(root: HTMLElement) {
  await tap(named(card(root), "Injusto"));
  await type(card(root).querySelector("textarea")!, REASON);
  await tap(named(card(root), "Guardar"));
}

describe("S2 A2 · A mark from the panel or the card reaches the review page", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Case 1 · "Injusto" with a reason on the card → the review page lists a web mark unfair on 20:10 with the reason
  it('Case 1 · "Injusto" with a reason on the card → the review page lists a web mark unfair on 20:10 with the reason', async () => {
    const { owner } = await collector();
    await unfair(await open(1212));
    const marks = await owner("/admin/marks");
    expect(marks).toHaveLength(1);
    expect(marks[0]).toMatchObject({
      video_id: "debate01", flag_id: "misleading-3.0", t: 1210, verdict: "unfair", reason: REASON, helper_version: "web",
    });
  });

  // Case 2 · the same "Injusto" → the review page lists a flag comment on 20:10 with the rule misleading and the reason
  it('Case 2 · the same "Injusto" → the review page lists a flag comment on 20:10 with the rule misleading and the reason', async () => {
    const { owner } = await collector();
    await unfair(await open(1212));
    const comments = await owner("/admin/feedback");
    expect(comments).toHaveLength(1);
    expect(comments[0]).toMatchObject({ kind: "flag", video_id: "debate01", flag_id: "misleading-3.0", rule: "misleading", text: REASON });
    const [mark] = await owner("/admin/marks");
    expect(comments[0].install_id).toBe(mark.install_id);
  });

  // Case 3 · after saving → the card shows the viewer's mark "Tu marca: Injusto"
  it('Case 3 · after saving → the card shows the viewer\'s mark "Tu marca: Injusto"', async () => {
    await collector();
    const root = await open(1212);
    await unfair(root);
    expect(card(root).textContent).toContain("Tu marca: Injusto");
  });

  // Case 4 · "Correcto" in the open row of 10:30 → the review page lists a web mark correct on 10:30, and the row shows it
  it('Case 4 · "Correcto" in the open row of 10:30 → the review page lists a web mark correct on 10:30, and the row shows it', async () => {
    const { owner } = await collector();
    const root = await open(1212);
    await tap(named(await row(root, "10:30"), "Correcto"));
    const marks = await owner("/admin/marks");
    expect(marks.map((m) => [m.flag_id, m.verdict, m.helper_version])).toEqual([["false-1.0", "correct", "web"]]);
    expect(await owner("/admin/feedback")).toEqual([]);
    const open10 = root.querySelector<HTMLElement>('aside[aria-label="Avisos"] button.text[aria-expanded="true"]')!.closest("article")!;
    expect(open10.textContent).toContain("Tu marca: Correcto");
  });

  // Case 5 · a closed row → no actions; the actions show on the card and in an open row only
  it("Case 5 · a closed row → no actions; the actions show on the card and in an open row only", async () => {
    await collector();
    const root = await open(1212);
    const rows = [...root.querySelectorAll<HTMLElement>('aside[aria-label="Avisos"] li > article')];
    expect(rows.every((r) => !named(r, "Correcto"))).toBe(true);
    expect(named(card(root), "Correcto")).toBeDefined();
  });

  // Case 6 · the daily stop refuses the mark → the viewer reads that marks are closed for today; the card keeps the mark
  it("Case 6 · the daily stop refuses the mark → the viewer reads that marks are closed for today; the card keeps the mark", async () => {
    const { send, env } = await collector();
    const mark = (flagId: string) => ({
      video_id: "debate01", flag_id: flagId, t: 45, type: "inaccuracy", label: "false", quote: "cifra inventada 5",
      confidence: 0.8, verdict: "correct", reason: "", provider: null, model: null,
    });
    for (let id = 0; id < 10; id++) {
      await send("/marks", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ install_id: crypto.randomUUID(), helper_version: "web",
          marks: Array.from({ length: 500 }, (_, i) => mark(`f-${i}.0`)) }),
      });
    }
    const count = () => Number(env.DB.rows("SELECT COUNT(*) AS n FROM marks")[0].n);
    expect(count()).toBe(5000);

    const root = await open(1212);
    await tap(named(card(root), "Correcto"));
    expect(root.textContent).toContain("Hoy ya no se aceptan más marcas");
    expect(card(root).textContent).toContain("Tu marca: Correcto");
    expect(count()).toBe(5000);
  }, 30000);
});
