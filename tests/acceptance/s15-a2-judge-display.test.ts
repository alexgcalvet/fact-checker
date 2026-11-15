// S15 A2 · The player and the panel follow the judge unless the person marked the flag
//
// Story: On a page that mimics the YouTube player, the flag file has a kept fallacy, a false figure judged
// "puntualización", a dropped flag and a dropped flag the person marked correct. The fallacy shows as usual; the
// "puntualización" shows as a small grey card titled "Puntualización" with the judge's reason; the dropped flag
// never shows on the player and appears struck through in the panel as "Descartado por el juez"; the flag marked
// correct shows as found.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel mounted as the content
// script mounts them, with a fixed flag file of four flags on the player: a fallacy at second 10 (judge: keep), a
// false figure at second 30 (judge: nitpick), a false figure at second 50 (judge: drop) and a false figure at
// second 70 (judge: drop, marked correct). Playback moves to one second after each flag.
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const NITPICK = "49,8 M frente a 49,4 M, el fondo se sostiene";
const flag = (id: string, t: number, type: string, label: string, judge: object, mark?: string) => ({
  id, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type, label, reason: `Motivo del segundo ${t}.`,
  confidence: 0.9, on_player: true, related: null, sources: [], note: null, judge, ...(mark ? { mark } : {}),
});
const flagFile = {
  video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [
    flag("ad_hominem-10.0", 10, "fallacy", "ad_hominem", { verdict: "keep", reason: "Se sostiene." }),
    flag("false-30.0", 30, "inaccuracy", "false", { verdict: "nitpick", reason: NITPICK }),
    flag("false-50.0", 50, "inaccuracy", "false", { verdict: "drop", reason: "El propio orador lo corrige." }),
    flag("false-70.0", 70, "inaccuracy", "false", { verdict: "drop", reason: "Error menor." }, "correct"),
  ],
} as any;

function page() {
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

describe("S15 A2 · The player and the panel follow the judge unless the person marked the flag", () => {
  // Case 1 · the kept fallacy at its second → its usual card
  it("Case 1 · the kept fallacy at its second → its usual card", () => {
    const { at } = page();
    const cards = at(11);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Ad hominem");
    expect(cards[0].textContent).toContain("Motivo del segundo 10.");
  });

  // Case 2 · the false figure judged "puntualización" → a grey card titled "Puntualización" with the judge's reason
  it("Case 2 · the \"puntualización\" → a grey card titled \"Puntualización\" with the judge's reason", () => {
    const { at } = page();
    const cards = at(31);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Puntualización");
    expect(cards[0].textContent).toContain(NITPICK);
    expect(cards[0].textContent).not.toContain("Dato falso");
    expect(grey(cards[0].style.borderLeft || cards[0].style.borderColor)).toBe(true);
  });

  // Case 3 · the dropped flag at its second → no card on the player
  it("Case 3 · the dropped flag at its second → no card on the player", () => {
    const { at } = page();
    expect(at(51).length).toBe(0);
  });

  // Case 4 · the dropped flag in the panel → struck through, with "Descartado por el juez"
  it("Case 4 · the dropped flag in the panel → struck through, with \"Descartado por el juez\"", () => {
    const { row } = page();
    const dropped = row(50);
    expect(dropped.textContent).toContain("Descartado por el juez");
    const struck = [dropped, ...dropped.querySelectorAll<HTMLElement>("*")]
      .some((el) => el.style.textDecoration.includes("line-through") && el.textContent!.includes("frase del segundo 50"));
    expect(struck).toBe(true);
  });

  // Case 5 · the dropped flag the person marked correct → its card as found, and a plain row in the panel
  it("Case 5 · the dropped flag marked correct → its card as found, and a plain row", () => {
    const { at, row } = page();
    const cards = at(71);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Dato falso");
    expect(cards[0].textContent).toContain("Motivo del segundo 70.");
    const plain = row(70);
    expect(plain.textContent).not.toContain("Descartado por el juez");
    expect([plain, ...plain.querySelectorAll<HTMLElement>("*")].some((el) => el.style.textDecoration.includes("line-through"))).toBe(false);
  });
});
