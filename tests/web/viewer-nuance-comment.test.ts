// @vitest-environment jsdom
// S2 A3 · "Matizar" sends a comment on the flag
//
// Story: After agreeing, a viewer taps "Matizar" on the flag at 20:10, writes "Falta decir que es interanual" and sends
// it. The owner's review page lists a flag comment on that flag with that text and no rule, and no mark.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch; the same stub serves the fake Cloudflare Access key set (tests/support/access_fake.ts), and the
// collector gets the invented TEAM_DOMAIN and POLICY_AUD. A fake YouTube player (tests/support/youtube_fake.ts) stands
// in for the embed, and fake timers drive the app's 250 ms poll. Browser storage starts empty. The web app is mounted
// at /es/v/debate01 and plays from second 1212: the card over the video is the flag at 20:10 (misleading-3.0). Whenever
// the question "Compartir tus marcas" shows, the viewer answers "Sí". The comment box is the flag's textarea, sent
// with "Enviar". The owner reads /admin/feedback and /admin/marks with an Access token.
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const TEXT = "Falta decir que es interanual";
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
  return { owner };
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
async function tap(el: HTMLElement) {
  await act(async () => { el.click(); await settle(); });
  const box = question();
  if (box) await act(async () => { named(box, "Sí").click(); await settle(); });
}
const card = (root: HTMLElement) => root.querySelector<HTMLElement>('.stage article[aria-label="Aviso de ahora"]')!;

// "Matizar" on the card at 20:10, the comment, then "Enviar".
async function nuance(root: HTMLElement) {
  await tap(named(card(root), "Matizar"));
  const box = card(root).querySelector("textarea")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, TEXT);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await tap(named(card(root), "Enviar"));
}

describe('S2 A3 · "Matizar" sends a comment on the flag', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Case 1 · "Matizar" with a comment on 20:10 → the review page lists one flag comment on that flag, the text, no rule
  it('Case 1 · "Matizar" with a comment on 20:10 → the review page lists one flag comment on that flag, the text, no rule', async () => {
    const { owner } = await collector();
    await nuance(await open(1212));
    const comments = await owner("/admin/feedback");
    expect(comments).toHaveLength(1);
    expect(comments[0]).toMatchObject({ kind: "flag", video_id: "debate01", flag_id: "misleading-3.0", rule: null, text: TEXT });
  });

  // Case 2 · the same comment → no mark on the review page
  it("Case 2 · the same comment → no mark on the review page", async () => {
    const { owner } = await collector();
    await nuance(await open(1212));
    expect(await owner("/admin/marks")).toEqual([]);
  });
});
