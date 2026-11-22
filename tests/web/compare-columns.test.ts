// @vitest-environment jsdom
// S10 A2 · Three or more guests line up in columns
//
// Story: For a debate with 4 guests, `/es/v/<id>/comparar` shows one column per guest and one row per figure, every
// row on its own shared scale. With 5 guests the fifth column is reached by scrolling the table sideways inside its
// frame; nothing covers it. `/en/v/<id>/compare` shows the same in English.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch.
// The owner uploads debate04, a copy of debate01 with 4 guests: Ana 1200 s, Luis 900 s, Eva 600 s and Leo 300 s of
// speech, the host Marta 300 s, one turn each, the 12 flags shared in turn among the guests and a summary for each.
// For the 5-guest case the owner uploads it again with Noa (450 s) as a fifth guest.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector, debateEs } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

// A debate of these guests (name, seconds of speech) and the host Marta: one turn each, the flags shared in turn.
function debateOf(guests: [string, number][]) {
  const people: Record<string, object> = {};
  const turns: { start: number; end: number; person: string }[] = [];
  let at = 0;
  for (const [name, spoken_s] of [...guests, ["Marta", 300] as [string, number]]) {
    people[name] = { role: name === "Marta" ? "host" : "guest", spoken_s, turns: 1, longest_s: spoken_s };
    turns.push({ start: at, end: at + spoken_s, person: name });
    at += spoken_s;
  }
  const flags = debateEs.flags.map((f: any, i: number) => ({ ...f, speaker: guests[i % guests.length][0] }));
  const summary = Object.fromEntries(guests.map(([name]) => [name, { checked: 4, asked: 2, flags: {}, gravest: [] }]));
  const speakers = Object.fromEntries(Object.keys(people).map((name, i) => [`SPEAKER_0${i}`, name]));
  return { ...debateEs, video_id: "debate04", duration: at, analysed_until: at, speakers, people, turns, flags, summary,
    claims: null, questions: null };
}
const FOUR: [string, number][] = [["Ana", 1200], ["Luis", 900], ["Eva", 600], ["Leo", 300]];

async function open(path: string, guests: [string, number][]) {
  const collector = await apiCollector();
  await collector.owner(debateOf(guests));
  vi.stubGlobal("fetch", async (url: string | URL) => collector.get(String(url)));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ");
const columns = (root: HTMLElement) => [...root.querySelectorAll('main.compare [role="columnheader"]')];
const row = (root: HTMLElement, label: string) => {
  const head = [...root.querySelectorAll('main.compare [role="rowheader"]')].find((h) => text(h).includes(label));
  expect(head, `the row «${label}»`).toBeDefined();
  return head!.closest<HTMLElement>('[role="row"]')!;
};
const cells = (r: HTMLElement) => [...r.querySelectorAll<HTMLElement>('[role="cell"]')];
const width = (cell: HTMLElement) => parseFloat(cell.querySelector<HTMLElement>(".bar-fill, .mix")!.style.width);

describe("S10 A2 · Three or more guests line up in columns", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · 4 guests → one column per guest, in order, each linking to its profile
  it("Case 1 · /es/v/debate04/comparar → 4 columns Ana, Luis, Eva, Leo, each with «Ver su ficha»", async () => {
    const root = await open("/es/v/debate04/comparar", FOUR);
    const heads = columns(root);
    expect(heads.map((h) => text(h.querySelector("a")).split("Ver su ficha")[0].trim())).toEqual(["Ana", "Luis", "Eva", "Leo"]);
    expect(heads.map((h) => h.querySelector("a")?.getAttribute("href")))
      .toEqual(["/es/v/debate04/ana", "/es/v/debate04/luis", "/es/v/debate04/eva", "/es/v/debate04/leo"]);
    for (const h of heads) expect(text(h)).toContain("Ver su ficha");
  });

  // Case 2 · one row per figure, 4 cells each; the speaking time bars on the row's own scale (1200 : 900 : 600 : 300)
  it("Case 2 · each figure is a row of 4 cells; «Tiempo de palabra» bars in the ratio 4 : 3 : 2 : 1", async () => {
    const root = await open("/es/v/debate04/comparar", FOUR);
    for (const label of ["Tiempo de palabra", "Avisos cada 10 min que habla", "Datos correctos", "Graves cada 10 min que habla",
      "Preguntas eludidas"]) {
      expect(cells(row(root, label)), label).toHaveLength(4);
    }
    const share = cells(row(root, "Tiempo de palabra")).map(width);
    expect(share[0] / share[3]).toBeCloseTo(4, 1);
    expect(share[1] / share[3]).toBeCloseTo(3, 1);
    expect(share[2] / share[3]).toBeCloseTo(2, 1);
    // Each guest has 3 avisos: per 10 min of their own speech, 1,5 · 2,0 · 3,0 · 6,0, and the longest bar is Leo's.
    const rates = cells(row(root, "Avisos cada 10 min que habla"));
    expect(rates.map((c) => text(c).match(/\d+,\d/)?.[0])).toEqual(["1,5", "2,0", "3,0", "6,0"]);
    expect(width(rates[3]) / width(rates[0])).toBeCloseTo(4, 1);
  });

  // Case 3 · 5 guests → the fifth column sits inside the table's own sideways-scrolling frame, which nothing covers
  it("Case 3 · 5 guests → 5 columns inside a focusable frame that scrolls sideways; no sticky or overlaid part in it", async () => {
    const root = await open("/es/v/debate04/comparar", [...FOUR, ["Noa", 450]]);
    const frame = root.querySelector<HTMLElement>('main.compare [role="region"][tabindex="0"]');
    expect(frame, "the table's frame").not.toBeNull();
    expect(frame!.classList).toContain("cmp-frame");
    expect([...frame!.querySelectorAll('[role="columnheader"]')].map((h) => text(h.querySelector("a")).split("Ver su ficha")[0].trim()))
      .toEqual(["Ana", "Luis", "Eva", "Leo", "Noa"]);
    const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../../src/web/src/style.css"), "utf8");
    const rule = css.match(/\.compare \.cmp-frame\s*\{([^}]*)\}/);
    expect(rule, "the frame's rule in style.css").not.toBeNull();
    expect(rule![1]).toMatch(/overflow-x:\s*auto/);
    const inFrame = [...css.matchAll(/\.compare \.cmp-(?:frame|table|col|cell|head|row|label)[^{]*\{([^}]*)\}/g)].map((m) => m[1]).join(";");
    expect(inFrame).not.toMatch(/position:\s*(sticky|fixed|absolute)/);
  });

  // Case 4 · /en/v/debate04/compare → the same in English
  it("Case 4 · /en/v/debate04/compare → 4 columns linking to /en/ profiles, rows «Speaking time», «Correct claims»", async () => {
    const root = await open("/en/v/debate04/compare", FOUR);
    expect(columns(root).map((h) => h.querySelector("a")?.getAttribute("href")))
      .toEqual(["/en/v/debate04/ana", "/en/v/debate04/luis", "/en/v/debate04/eva", "/en/v/debate04/leo"]);
    for (const label of ["Speaking time", "Flags per 10 min they speak", "Correct claims", "Questions dodged"]) {
      expect(cells(row(root, label)), label).toHaveLength(4);
    }
    expect(text(root)).toContain("See their profile");
    console.log("PASS S10 A2 · Three or more guests line up in columns");
  });
});
