// @vitest-environment jsdom
// S5 A3 · A profile says what it cannot show
//
// Story: For a video uploaded before speaking time existed, Ana's profile counts avisos per 10 minutes of video, says
// so, shows no level and reads "Tiempo de palabra: sin datos". For a video with no summary it reads "Esta ficha aún no
// existe" with a link to watch the video. In an interview, the host has no page of their own: `/es/v/intervw1/marta`
// shows the interview's guest list instead.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch.
// For the first case the owner uploads debate01 again as a helper did before speaking time existed: roles only and no
// voice turns. Ana has 6 avisos in the 60 min debate: 1,0 per 10 min of video. The interview intervw1 (guest Pablo,
// host Marta) was uploaded with no summary and no speech.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector, debateEs } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

type Collector = Awaited<ReturnType<typeof apiCollector>>;

async function open(path: string, collector?: Collector) {
  const { get } = collector ?? await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => get(String(url)));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ");

describe("S5 A3 · A profile says what it cannot show", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · no speaking time → avisos per 10 min of video, said so, no level, no debate figure, «sin datos»
  it("Case 1 · an upload without speech → «Avisos cada 10 min de vídeo» 1,0, no level, «Tiempo de palabra: sin datos»", async () => {
    const collector = await apiCollector();
    const { turns: _, ...before } = debateEs as any;
    await collector.owner({ ...before, people: { Ana: { role: "guest" }, Luis: { role: "guest" }, Marta: { role: "host" } } });
    const root = await open("/es/v/debate01/ana", collector);
    const f = text(root.querySelector('section[aria-label="Sus cifras"]'));
    expect(f).toContain("Avisos cada 10 min de vídeo");
    expect(f).toContain("1,0");
    expect(f).toMatch(/Tiempo de palabra\W*sin datos/);
    for (const level of ["pocos avisos", "bastantes avisos", "muchos avisos"]) expect(f, level).not.toContain(level);
    expect(f).not.toContain("que habla");
    expect(f).not.toContain("debate ");
  });

  // Case 2 · no summary → «Esta ficha aún no existe» and a link to watch the video, no figures
  it("Case 2 · /es/v/intervw1/pablo, with no summary → «Esta ficha aún no existe», a link to /es/v/intervw1", async () => {
    const root = await open("/es/v/intervw1/pablo");
    expect(text(root)).toContain("Esta ficha aún no existe");
    const watch = [...root.querySelectorAll("a")].find((a) => text(a).includes("Ver el vídeo con sus avisos"));
    expect(watch?.getAttribute("href")).toBe("/es/v/intervw1");
    expect(root.querySelector('section[aria-label="Sus cifras"]')).toBeNull();
  });

  // Case 3 · the interview's host → no profile: the guest list of the interview, linking to Pablo's profile
  it("Case 3 · /es/v/intervw1/marta → no profile, the guest list with a link to /es/v/intervw1/pablo", async () => {
    const root = await open("/es/v/intervw1/marta");
    const pablo = root.querySelector('a[href="/es/v/intervw1/pablo"]');
    expect(pablo, "the link to Pablo's profile").not.toBeNull();
    expect(text(pablo)).toContain("Pablo");
    expect(root.querySelector('section[aria-label="Sus cifras"]')).toBeNull();
    expect(text(root)).not.toContain("Esta ficha aún no existe");
    console.log("PASS S5 A3 · A profile says what it cannot show");
  });
});
