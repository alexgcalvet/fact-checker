// S34 A2 · A serious card says "grave" in its title
//
// Story: The person plays a video whose file holds a serious false figure, a moderate misleading one and a
// puntualización. The first card reads "Falso · grave" ("False · serious" in English), the second reads "Engañoso",
// and the puntualización stays grey with no severity word. The side panel rows read the same.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel mounted as the content script
// mounts them, with a judged flag file of three flags on the player: a false figure at second 10 (keep, serious), a
// misleading figure at second 30 (keep, moderate) and a false figure at second 50 (nitpick). The interface speaks
// Spanish unless a case picks English in the settings. Playback moves to one second after each flag.
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { mountOverlay, settings } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const flag = (id: string, t: number, label: string, judge: object) => ({
  id, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type: "inaccuracy", label,
  reason: `Motivo del segundo ${t}.`, confidence: 0.9, on_player: true, related: null, sources: [], note: null, judge,
});
const flagFile = {
  video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [
    flag("false-10.0", 10, "false", { verdict: "keep", reason: "Bajó del 12 % al 11 %.", severity: "serious" }),
    flag("misleading-30.0", 30, "misleading", { verdict: "keep", reason: "Cuenta solo un año.", severity: "moderate" }),
    flag("false-50.0", 50, "false", { verdict: "nitpick", reason: "Se aprobó en abril de 2019" }),
  ],
} as any;

function page(lang: "es" | "en" = "es") {
  settings.lang = lang;
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  let now = 0;
  Object.defineProperty(video, "currentTime", { get: () => now, set: (t) => { now = t; }, configurable: true });
  const overlay = mountOverlay(player, video, () => flagFile, () => {});
  mountPanel(overlay.layer, video, () => flagFile, overlay.show);
  const at = (t: number) => {
    now = t;
    video.dispatchEvent(new Event("timeupdate"));
    return [...player.querySelectorAll<HTMLElement>(".fc-card")];
  };
  const row = (t: number) => [...player.querySelectorAll<HTMLElement>(".fc-row")]
    .find((r) => r.textContent!.includes(`frase del segundo ${t}`))!;
  return { at, row };
}

/** True when the colour is a grey: its red, green and blue are within 24 of each other. */
function grey(css: string): boolean {
  const hex = css.match(/#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i);
  const dec = css.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  const rgb = hex ? hex.slice(1).map((h) => parseInt(h, 16)) : dec ? dec.slice(1).map(Number) : null;
  if (!rgb) return false;
  return Math.max(...rgb) - Math.min(...rgb) <= 24;
}

afterEach(() => { settings.lang = null; });

describe("S34 A2 · A serious card says \"grave\" in its title", () => {
  // Case 1 · the serious false figure → its card and its panel row read "Dato falso · grave"
  it("Case 1 · the serious false figure → \"Dato falso · grave\" on the card and the row", () => {
    const { at, row } = page();
    const cards = at(11);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Dato falso · grave");
    expect(row(10).textContent).toContain("Dato falso · grave");
  });

  // Case 2 · the moderate misleading figure → "Dato engañoso" with no severity word, on the card and the row
  it("Case 2 · the moderate misleading figure → \"Dato engañoso\", no severity word", () => {
    const { at, row } = page();
    const cards = at(31);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Dato engañoso");
    expect(cards[0].textContent).not.toMatch(/grave|moderad/);
    expect(row(30).textContent).toContain("Dato engañoso");
    expect(row(30).textContent).not.toMatch(/grave|moderad/);
  });

  // Case 3 · the puntualización → a grey card titled "Puntualización", no severity word, on the card and the row
  it("Case 3 · the puntualización → grey, \"Puntualización\", no severity word", () => {
    const { at, row } = page();
    const cards = at(51);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Puntualización");
    expect(cards[0].textContent).not.toContain("grave");
    expect(grey(cards[0].style.borderLeft || cards[0].style.borderColor)).toBe(true);
    expect(row(50).textContent).toContain("Puntualización");
    expect(row(50).textContent).not.toContain("grave");
  });

  // Case 4 · the serious false figure in English → "False claim · serious" on the card and the row
  it("Case 4 · the serious false figure in English → \"False claim · serious\"", () => {
    const { at, row } = page("en");
    const cards = at(11);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("False claim · serious");
    expect(row(10).textContent).toContain("False claim · serious");
    expect(at(31)[0].textContent).not.toContain("serious");
  });
});
