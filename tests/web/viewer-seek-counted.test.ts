// @vitest-environment jsdom
// S7 A2 · A jump to a flag's moment counts a seek
// Story: A viewer on /es/v/debate01 taps the time 20:10 of a flag, then a mark on the timeline. Two seeks are sent, with
// no consent question; the owner's visits table shows debate01, "es", today, 2 seeks.
// Setup: the invented collector (tests/support/api_fakes.ts) answers every request of the app's fetch; the same stub
// serves the fake Access key set, and the collector gets the invented TEAM_DOMAIN and POLICY_AUD. A fake YouTube player
// stands in for the embed, fake timers drive the app's poll, and browser storage starts empty: the viewer never agreed
// to share. The app is mounted at /es/v/debate01 directly (no page visit through the Worker), playing from second 50.
// The owner reads /admin/visits with an Access token.
import { act } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
const settle = () => new Promise((done) => setTimeout(done, 20));

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
});

it("sends a seek on a tap on a flag's time and on a timeline mark, with no question, and the owner sees 2 seeks", async () => {
  const { send, env } = await apiCollector();
  Object.assign(env, { TEAM_DOMAIN, POLICY_AUD });
  const keys = certsFetch();
  const posts: string[] = [];
  vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) => {
    if (String(url).startsWith(TEAM_DOMAIN)) return keys.fetch(String(url));
    if (init?.method === "POST") posts.push(String(url));
    return send(String(url), init);
  });
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  history.replaceState(null, "", "/es/v/debate01");
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  const player = FakePlayer.last!;
  await act(async () => {
    player.ready();
    player.play(50);
    vi.advanceTimersByTime(250);
  });

  // Case 1 · a tap on the time 20:10, then on a timeline mark → two seeks sent, no consent question
  await act(async () => { root.querySelector<HTMLElement>('button[aria-label="Ir a 20:10"]')!.click(); await settle(); });
  await act(async () => { root.querySelector<HTMLElement>('.lane button[aria-label^="10:30"]')!.click(); await settle(); });
  expect(posts).toEqual(["/api/visits", "/api/visits"]);
  expect(document.querySelector('[role="dialog"][aria-label="Compartir tus marcas"]')).toBeNull();

  // Case 2 · the owner's visits table → debate01, es, today, 2 seeks
  const res = await send("/admin/visits", { headers: { [HEADER]: await token() } });
  const { rows } = (await res.json()) as { rows: Record<string, unknown>[] };
  expect(rows).toContainEqual({ video_id: "debate01", lang: "es", day: new Date().toISOString().slice(0, 10), visits: 0, seeks: 2 });
  console.log("PASS S7 A2 · A jump to a flag's moment counts a seek");
});
