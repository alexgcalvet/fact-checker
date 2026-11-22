// @vitest-environment jsdom
// S10 A1 · Two guests face each other on one scale
//
// Story: A reader opens `/es/v/debate01/comparar` (Ana spoke 28:40 and Luis 24:50 of the debate's voices). Each figure
// is one row of a balance: Ana's value and bar on the left, the label on the spine, Luis's bar and value on the right,
// both bars on the same scale. The rows read speaking time (48,3 % and 41,9 %), avisos per 10 minutes of own speech
// with a mirrored mix bar and each one's provisional level (2,1 and 2,4), datos correctos (60 % and 50 %), graves per
// 10 minutes, preguntas eludidas with one cell per question, and what each one repeats most. Each row shows the debate's
// own figure (2,2 avisos, 56 % correct) and nothing says who speaks or errs most. Each guest's header links to their
// profile ("Ver su ficha"). Under the rows, "Quién habla y cuándo" shows every voice's lane, the host's included, and
// each voice's turns.
// Copy pass 2026-11-21 (owner): the row is «Lo que repite» and «Ad hominem» is «Ataque personal».
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch.
// Its debate01 (60 min) carries the speech of each person: Ana 1720 s in 6 turns, Luis 1490 s in 5, the host Marta
// 350 s in 5. Ana has 6 avisos (Falso 2, Engañoso 1, Retórica 2, Puntualización 1), 6 of 10 checked claims correct,
// 2 serious and 4 questions, none eluded; Luis has 6 avisos (Falso 1, Engañoso 2, Retórica 2, Puntualización 1), 4 of 8
// correct, 2 serious and 3 questions. Both repeat ad hominem twice. A fake YouTube player stands in for the embed.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function open(path: string) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => get(String(url)));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ");
// A row of the balance by the label on its spine: its cells in order, left to right.
const row = (root: HTMLElement, label: string) => {
  const head = [...root.querySelectorAll('main.compare [role="rowheader"]')].find((h) => text(h).includes(label));
  expect(head, `the row «${label}»`).toBeDefined();
  return head!.closest<HTMLElement>('[role="row"]')!;
};
const cells = (r: HTMLElement) => [...r.querySelectorAll<HTMLElement>('[role="cell"]')];
// The bars of a row, left to right: a plain bar or a mix bar, each as wide as its value on the row's scale.
const bars = (r: HTMLElement) => cells(r).map((c) => parseFloat(c.querySelector<HTMLElement>(".bar-fill, .mix")!.style.width));

describe("S10 A1 · Two guests face each other on one scale", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · /es/v/debate01/comparar → each guest's header links to their profile with «Ver su ficha», Ana left, Luis right
  it("Case 1 · /es/v/debate01/comparar → «Ver su ficha» links to /es/v/debate01/ana (left) and /es/v/debate01/luis (right)", async () => {
    const root = await open("/es/v/debate01/comparar");
    const links = [...root.querySelectorAll<HTMLAnchorElement>("main.compare a")].filter((a) => text(a).includes("Ver su ficha"));
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/es/v/debate01/ana", "/es/v/debate01/luis"]);
    expect(text(links[0])).toContain("Ana");
    expect(text(links[1])).toContain("Luis");
  });

  // Case 2 · the speaking time row → 48,3 % left, the label on the spine, 41,9 % right, bars on one scale
  it("Case 2 · «Tiempo de palabra» → 48,3 % · label · 41,9 %, bars in the ratio 48,3 : 41,9", async () => {
    const r = row(await open("/es/v/debate01/comparar"), "Tiempo de palabra");
    const [left, right] = cells(r);
    expect(text(left)).toContain("48,3 %");
    expect(text(right)).toContain("41,9 %");
    const t = text(r);
    expect(t.indexOf("48,3 %")).toBeLessThan(t.indexOf("Tiempo de palabra"));
    expect(t.indexOf("Tiempo de palabra")).toBeLessThan(t.indexOf("41,9 %"));
    const [a, b] = bars(r);
    expect(a / b).toBeCloseTo(1720 / 1490, 1);
  });

  // Case 3 · the avisos row → 2,1 and 2,4 «pocos avisos», a mirrored mix bar (Falso next to the spine on both sides) on
  // one scale, and the debate's 2,2
  it("Case 3 · «Avisos cada 10 min que habla» → 2,1 and 2,4, «pocos avisos» each, mirrored mix bars, debate 2,2", async () => {
    const r = row(await open("/es/v/debate01/comparar"), "Avisos cada 10 min que habla");
    const [left, right] = cells(r);
    expect(text(left)).toContain("2,1");
    expect(text(right)).toContain("2,4");
    expect(text(left)).toContain("pocos avisos");
    expect(text(right)).toContain("pocos avisos");
    expect(text(r)).toContain("debate 2,2");
    const [mixLeft, mixRight] = [...r.querySelectorAll<HTMLElement>(".mix")];
    const segs = (mix: HTMLElement) => [...mix.querySelectorAll(".seg")].map((s) => [...s.classList].find((c) => c.startsWith("m-")));
    expect(segs(mixLeft).at(-1), "the left bar's segment next to the spine").toBe("m-falso");
    expect(segs(mixRight)[0], "the right bar's segment next to the spine").toBe("m-falso");
    const [a, b] = bars(r);
    expect(a / b).toBeCloseTo((6 / 1720) / (6 / 1490), 1);
  });

  // Case 4 · datos correctos, graves and preguntas eludidas → 60 % and 50 % with the debate's 56 %; 0,7 and 0,8 graves;
  // 0 de 4 with 4 question cells and 0 de 3 with 3
  it("Case 4 · «Datos correctos» 60 % · 50 %, debate 56 %; graves 0,7 · 0,8; «Preguntas eludidas» 0 de 4 · 0 de 3, one cell per question", async () => {
    const root = await open("/es/v/debate01/comparar");
    const correct = row(root, "Datos correctos");
    expect(text(cells(correct)[0])).toContain("60 %");
    expect(text(cells(correct)[1])).toContain("50 %");
    expect(text(correct)).toContain("debate 56 %");
    const graves = row(root, "Graves cada 10 min que habla");
    expect(text(cells(graves)[0])).toContain("0,7");
    expect(text(cells(graves)[1])).toContain("0,8");
    const eluded = row(root, "Preguntas eludidas");
    expect(text(cells(eluded)[0])).toContain("0 de 4");
    expect(text(cells(eluded)[1])).toContain("0 de 3");
    const [qLeft, qRight] = [...eluded.querySelectorAll(".questions")];
    expect(qLeft.querySelectorAll(".q")).toHaveLength(4);
    expect(qRight.querySelectorAll(".q")).toHaveLength(3);
  });

  // Case 5 · what each one repeats most → «Ad hominem ×2» on both sides
  it("Case 5 · «Lo que más repite» → «Ad hominem ×2» for Ana and for Luis", async () => {
    const r = row(await open("/es/v/debate01/comparar"), "Lo que repite");
    expect(text(cells(r)[0])).toContain("Ataque personal ×2");
    expect(text(cells(r)[1])).toContain("Ataque personal ×2");
  });

  // Case 6 · the whole page → no ranking: nothing says who speaks, errs or wins most; the disclosure line shows
  it("Case 6 · the page → no «quien más habla», «ganador» or position; «Análisis automático con IA» shows", async () => {
    const t = text(await open("/es/v/debate01/comparar"));
    expect(t).not.toMatch(/(quien|la que|el que) más (habla|se equivoca|avisos)|ganador|\bgana\b|\bpuesto\b|\b1\.º/i);
    expect(t).toContain("Análisis automático con IA");
  });

  // Case 7 · «Quién habla y cuándo» → a lane for Ana, Luis and the host Marta with 6, 5 and 5 turns, their times and
  // turn counts, nobody highlighted
  it("Case 7 · «Quién habla y cuándo» → Ana 6 turns 28:40, Luis 5 turns 24:50, Marta (mod.) 5 turns 5:50", async () => {
    const root = await open("/es/v/debate01/comparar");
    const voices = root.querySelector<HTMLElement>('main.compare section[aria-label="Quién habla y cuándo"]');
    expect(voices, "the voices section").not.toBeNull();
    const lane = (name: string) => [...voices!.querySelectorAll<HTMLElement>(".voice-row")]
      .find((r) => text(r.querySelector(".voice-name")).startsWith(name))!;
    for (const [name, turns, time] of [["Ana", 6, "28:40"], ["Luis", 5, "24:50"], ["Marta", 5, "5:50"]] as const) {
      expect(lane(name), name).toBeDefined();
      expect(lane(name).querySelectorAll(".turn"), name).toHaveLength(turns);
      const figures = [...lane(name).querySelectorAll(".cell")].map((c) => text(c).trim());
      expect(figures, name).toContain(time);
      expect(figures, name).toContain(String(turns));
    }
    expect(text(lane("Marta"))).toContain("mod.");
    expect(voices!.querySelector(".voice-row.me"), "a highlighted person").toBeNull();
    console.log("PASS S10 A1 · Two guests face each other on one scale");
  });
});
