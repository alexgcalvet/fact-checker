// @vitest-environment jsdom
// S10 A3 · The comparison is reachable and says when it cannot compare
//
// Story: In the viewer of debate01, the guest row reads "Invitados: Ana · Luis · Comparar", and the guest switcher of
// each profile ends with "Comparar"; both lead to the comparison. An interview shows no "Comparar", and
// `/es/v/intervw1/comparar` shows its guest list instead. A debate uploaded before speaking time existed shows "Sin
// tiempo de palabra no se puede comparar" with links to each guest's profile, and no figures.
// Owner review 2026-11-21: the viewer's guest row drops its "Invitados:" label; the pills and "Comparar" stay.
// Owner review 2026-11-22: the pills become guest cards ("Ana … Ficha →"); "Comparar" still ends the row.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch, and
// a fake YouTube player (tests/support/youtube_fake.ts) for the embed. debate01 has the guests Ana and Luis and the host
// Marta; the interview intervw1 has the guest Pablo and the host Marta. For the last case the owner uploads debate01
// again as a helper did before speaking time existed: roles only and no voice turns.
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
const linksTo = (root: HTMLElement, href: string) => [...root.querySelectorAll(`a[href="${href}"]`)];

describe("S10 A3 · The comparison is reachable and says when it cannot compare", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the viewer of debate01 → «Invitados: Ana · Luis · Comparar», «Comparar» linking to the comparison
  it("Case 1 · /es/v/debate01 → «Invitados» Ana, Luis, then «Comparar» linking to /es/v/debate01/comparar", async () => {
    const root = await open("/es/v/debate01");
    const compare = linksTo(root, "/es/v/debate01/comparar");
    expect(compare, "the link to the comparison").toHaveLength(1);
    expect(text(compare[0]).trim()).toBe("Comparar");
    // The guest row: the nearest block around the link that names the guests.
    const row = compare[0].closest(".guests")!;
    expect(text(row)).toMatch(/^Ana.*Luis.*Comparar$/);
    expect(text(row)).not.toContain("Invitados");
    expect(text(row)).not.toMatch(/Marta/);
  });

  // Case 2 · a profile's guest switcher → Ana, Luis, then «Comparar» linking to the comparison
  it("Case 2 · /es/v/debate01/ana → the switcher «Invitados» ends with «Comparar» linking to /es/v/debate01/comparar", async () => {
    const root = await open("/es/v/debate01/ana");
    const links = [...root.querySelectorAll('nav[aria-label="Invitados"] a')];
    expect(links.map((a) => text(a).trim())).toEqual(["Ana", "Luis", "Comparar"]);
    expect(links.at(-1)!.getAttribute("href")).toBe("/es/v/debate01/comparar");
  });

  // Case 3 · the interview → no «Comparar» in its viewer, and /es/v/intervw1/comparar shows its guest list
  it("Case 3 · /es/v/intervw1 has no «Comparar»; /es/v/intervw1/comparar → the guest list, a link to /es/v/intervw1/pablo", async () => {
    const viewer = await open("/es/v/intervw1");
    expect(text(viewer)).not.toContain("Comparar");
    expect(linksTo(viewer, "/es/v/intervw1/comparar")).toHaveLength(0);
    const root = await open("/es/v/intervw1/comparar");
    expect(linksTo(root, "/es/v/intervw1/pablo"), "the link to Pablo's profile").toHaveLength(1);
    expect(root.querySelector('[role="table"]')).toBeNull();
    expect(text(root)).not.toContain("Tiempo de palabra");
  });

  // Case 4 · a debate without speaking time → «Sin tiempo de palabra no se puede comparar», links to each profile, no figures
  it("Case 4 · debate01 uploaded without speech → «Sin tiempo de palabra no se puede comparar», links to ana and luis, no table", async () => {
    const collector = await apiCollector();
    const { turns: _, ...before } = debateEs as any;
    await collector.owner({ ...before, people: { Ana: { role: "guest" }, Luis: { role: "guest" }, Marta: { role: "host" } } });
    const root = await open("/es/v/debate01/comparar", collector);
    expect(text(root)).toContain("Sin tiempo de palabra no se puede comparar");
    expect(linksTo(root, "/es/v/debate01/ana")).toHaveLength(1);
    expect(linksTo(root, "/es/v/debate01/luis")).toHaveLength(1);
    expect(root.querySelector('[role="table"]')).toBeNull();
    expect(text(root)).not.toContain("Avisos cada 10 min");
    console.log("PASS S10 A3 · The comparison is reachable and says when it cannot compare");
  });
});
