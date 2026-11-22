// @vitest-environment jsdom
// Inline 2026-11-22 · The page "Cómo funciona" shows how the project is moving (owner)
//
// Story: A reader opens `/es/como-funciona` and, under the route of a video, sees the project in five versions (v0 to v0.4): the
// personal extension and the public web are done, "Veredictos y evidencia medibles" is in progress, "Análisis en directo" comes next, then "Feedback conectado a evaluaciones", and
// nothing follows it. Hovering a step shows its detail. `/en/how-it-works` says the same in English.
//
// Setup: the invented collector of the public API tests answers every request of the app's fetch. The web app is
// mounted at the path; the roadmap is the page's ".roadmap" list.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function steps(path: string) {
  const { send } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) => send(String(url), init));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  await act(async () => { await mount(document.getElementById("app")!, FakePlayer as any); await new Promise((done) => setTimeout(done, 20)); });
  return [...document.querySelectorAll<HTMLElement>(".roadmap > li")].map((li) => [li.className, li.querySelector(".rm-state")!.textContent, li.querySelector(".rm-name")!.textContent]);
}

describe("The page shows how the project is moving", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("Case 1 · /es/como-funciona → five steps: two done, one in progress, one next", async () => {
    expect(await steps("/es/como-funciona")).toEqual([
      ["rm-done", "v0 · Hecho", "Extensión personal"], ["rm-done", "v0.1 · Hecho", "Web pública"],
      ["rm-now", "v0.2 · En curso", "Veredictos y evidencia medibles"], ["rm-next", "v0.3 · Después", "Análisis en directo"],
      ["rm-next", "v0.4 · Después", "Feedback conectado a evaluaciones"],
    ]);
  });

  it("Case 2 · /en/how-it-works → the same five steps in English", async () => {
    expect(await steps("/en/how-it-works")).toEqual([
      ["rm-done", "v0 · Done", "Personal extension"], ["rm-done", "v0.1 · Done", "Public web"],
      ["rm-now", "v0.2 · In progress", "Measurable verdicts and evidence"], ["rm-next", "v0.3 · Next", "Live analysis"],
      ["rm-next", "v0.4 · Next", "Feedback connected to evaluations"],
    ]);
  });
});
