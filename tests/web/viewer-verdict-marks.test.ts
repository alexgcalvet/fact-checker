// @vitest-environment jsdom
// S1 A2 · Each flag shows its CALVET verdict mark
//
// Story: In the same viewer, on the timeline and in the panel, a false claim shows "Falso", a misleading one
// "Engañoso", an ad hominem "Retórica", a dodged question "Evasiva", a disputed claim "Engañoso" with "Dato discutido"
// under it; a context flag shows "Contexto" and a judge's nitpick "Puntualización" with the context mark, both in the
// panel only, with no mark on the timeline; a flag at 55 % shows its word dimmed with "confianza baja"; in English the
// words are False, Misleading, Rhetoric, Evasive, Context, Nitpick.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch.
// Its debate has false, misleading and ad hominem flags and two nitpicks; the flags answer of debate01 gets four
// invented flags more, far apart on the timeline: a dodged question at 33:20, a context flag at 40:00, a disputed
// claim at 46:40 and a misleading claim at 55 % at 53:20. A fake YouTube player (tests/support/youtube_fake.ts) stands
// in for the embed. The web app is mounted through its own `mount` export at /es/v/debate01 or /en/v/debate01.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const invented = (id: string, t: number, type: string, label: string, confidence = 0.8, sources: object[] = []) => ({
  id, t, speaker: "Ana", quote: `invented ${label}`, type, label, reason: "Invented reason.", confidence, related: null, sources,
  judge: { verdict: "keep", reason: "Invented judge reason." },
});
const SOURCE = (publisher: string) => ({ publisher, url: "https://example.org/data", date: "2026-10-01" });
const EXTRA = [
  invented("dodged-13.0", 2000, "question", "dodged"),
  invented("person-14.0", 2400, "context", "person"),
  invented("disputed-15.0", 2800, "inaccuracy", "disputed", 0.8, [SOURCE("Invented Office"), SOURCE("Invented Institute")]),
  invented("misleading-16.0", 3200, "inaccuracy", "misleading", 0.55, [SOURCE("Invented Office")]),
];

async function open(path: string) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => {
    const res = await get(String(url));
    if (!String(url).includes("/flags")) return res;
    const answer = await res.json() as { flags: object[] };
    return Response.json({ ...answer, flags: [...answer.flags, ...EXTRA] });
  });
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  FakePlayer.last = undefined;
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  await act(async () => FakePlayer.last!.ready());
  return root;
}

const go = (lang: "es" | "en") => (lang === "es" ? "Ir a" : "Go to");
const row = (root: HTMLElement, lang: "es" | "en", time: string) =>
  [...root.querySelectorAll<HTMLElement>('aside li > article')].find((r) => r.querySelector(`button[aria-label="${go(lang)} ${time}"]`))!;
const lane = (root: HTMLElement, time: string) =>
  [...root.querySelectorAll<HTMLElement>('[role="group"][aria-label^="Avisos en el tiempo"] button, [role="group"][aria-label^="Flags over time"] button')]
    .find((b) => b.getAttribute("aria-label")!.startsWith(`${time} · `))!;
const word = (el: HTMLElement, text: string) => [...el.querySelectorAll<HTMLElement>("span")].find((s) => s.textContent === text);

// The time of a flag, the mark it must show and its word in Spanish and in English.
const KINDS: [string, string, string, string, string][] = [
  ["false claim", "10:30", "falso", "Falso", "False"],
  ["misleading claim", "20:10", "enganoso", "Engañoso", "Misleading"],
  ["ad hominem", "5:00", "retorica", "Retórica", "Rhetoric"],
  ["dodged question", "33:20", "evasiva", "Evasiva", "Evasive"],
  ["context flag", "40:00", "contexto", "Contexto", "Context"],
  ["judge's nitpick", "16:20", "contexto", "Puntualización", "Nitpick"],
  ["disputed claim", "46:40", "enganoso", "Engañoso", "Misleading"],
];

describe("S1 A2 · Each flag shows its CALVET verdict mark", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the Spanish viewer's panel → each flag's row shows its mark and its Spanish word
  it("Case 1 · the Spanish viewer's panel → each flag's row shows its mark and its Spanish word", async () => {
    const root = await open("/es/v/debate01");
    for (const [kind, time, mark, es] of KINDS) {
      const r = row(root, "es", time);
      expect(r?.querySelector(`[data-mark="${mark}"]`), `${kind} mark`).not.toBeNull();
      expect(word(r, es), `${kind} word`).toBeDefined();
    }
    expect(word(row(root, "es", "16:20"), "Contexto"), "the nitpick is not called Contexto").toBeUndefined();
  });

  // Case 2 · the Spanish viewer's timeline → each flag's mark has its mark and names its Spanish word; a context note has no mark
  it("Case 2 · the Spanish viewer's timeline → each flag's mark has its mark and names its Spanish word; a context note has no mark", async () => {
    const root = await open("/es/v/debate01");
    for (const [kind, time, mark, es] of KINDS) {
      const m = lane(root, time);
      if (mark === "contexto") {
        expect(m ?? null, `${kind} off the timeline`).toBeNull();
        continue;
      }
      expect(m?.getAttribute("aria-label"), `${kind} label`).toBe(`${time} · ${es}`);
      expect(m.querySelector(`[data-mark="${mark}"]`), `${kind} mark`).not.toBeNull();
    }
    expect(root.querySelectorAll('.lane [data-mark="contexto"]').length, "no context mark on the timeline").toBe(0);
  });

  // Case 3 · the disputed claim → Engañoso, with "Dato discutido" under it
  it("Case 3 · the disputed claim → Engañoso, with \"Dato discutido\" under it", async () => {
    const r = row(await open("/es/v/debate01"), "es", "46:40");
    expect(word(r, "Engañoso")).toBeDefined();
    expect(r.textContent).toContain("Dato discutido");
    expect(row(await open("/es/v/debate01"), "es", "20:10").textContent).not.toContain("Dato discutido");
  });

  // Case 4 · the misleading claim at 55 % → its word dimmed, with "confianza baja"; one at 80 % keeps its colour
  it("Case 4 · the misleading claim at 55 % → its word dimmed, with \"confianza baja\"; one at 80 % keeps its colour", async () => {
    const root = await open("/es/v/debate01");
    const low = row(root, "es", "53:20");
    expect(low.querySelector('[data-mark="enganoso"]')).not.toBeNull();
    expect(low.textContent).toContain("55 %");
    expect(low.textContent).toContain("confianza baja");
    expect(word(low, "Engañoso")!.style.color).toBe("var(--t4)");
    const sure = row(root, "es", "20:10");
    expect(sure.textContent).not.toContain("confianza baja");
    expect(word(sure, "Engañoso")!.style.color).toBe("var(--st-enganoso-text)");
  });

  // Case 5 · the English viewer → the words False, Misleading, Rhetoric, Evasive, Context and Nitpick, in the panel and on the timeline
  it("Case 5 · the English viewer → the words False, Misleading, Rhetoric, Evasive, Context and Nitpick, in the panel and on the timeline", async () => {
    const root = await open("/en/v/debate01");
    for (const [kind, time, mark, , en] of KINDS) {
      const r = row(root, "en", time);
      expect(r?.querySelector(`[data-mark="${mark}"]`), `${kind} mark`).not.toBeNull();
      expect(word(r, en), `${kind} word`).toBeDefined();
      if (mark !== "contexto") expect(lane(root, time)?.getAttribute("aria-label"), `${kind} label`).toBe(`${time} · ${en}`);
      else expect(lane(root, time) ?? null, `${kind} off the timeline`).toBeNull();
    }
    expect(root.querySelectorAll('.lane [data-mark="contexto"]').length, "no context mark on the timeline").toBe(0);
  });
});
