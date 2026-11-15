// S27 A4 · Each card asks the question with two large buttons
//
// Story: A person with a Spanish browser sees a fallacy card: its foot reads "¿Es justo este aviso?" with the buttons
// "✓ De acuerdo" and "✗ No", taller than the card's other text buttons. In English they read "Is this flag fair?",
// "✓ Agree", "✗ Disagree". A click on "✓ De acuerdo" marks the flag correct as today, and a marked card says
// "Marcaste: ✓ De acuerdo" with "cambiar".
//
// Setup: a jsdom page with a player and a video at second 43, the browser language set per case (navigator.language),
// and the overlay mounted with one fallacy flag at second 42 and a mark callback that records what it gets. The sizes
// come from the overlay's own style sheet through getComputedStyle.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

const flagFile = (mark?: string) => ({
  video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
    label: "ad_hominem", reason: "Ataca.", confidence: 0.85, on_player: true, related: null, sources: [], note: null,
    ...(mark ? { mark } : {}) }],
}) as any;

async function page(language: string, mark?: string) {
  Object.defineProperty(navigator, "language", { value: language, configurable: true });
  vi.resetModules();
  const { mountOverlay } = await import("../../src/extension/src/overlay");
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  const sent: [string, string, string][] = [];
  const file = flagFile(mark);
  mountOverlay(player, video, () => file, (flag, verdict, reason) => { sent.push([flag.id, verdict, reason]); });
  Object.defineProperty(video, "currentTime", { value: 43, configurable: true });
  video.dispatchEvent(new Event("timeupdate"));
  const card = () => player.querySelector<HTMLElement>(".fc-card")!;
  const button = (text: string) =>
    [...card().querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent!.trim() === text);
  const height = (el: Element) => parseFloat(getComputedStyle(el).height);
  return { card, button, height, sent };
}

afterEach(() => { Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true }); });

describe("S27 A4 · Each card asks the question with two large buttons", () => {
  // Case 1 · a Spanish browser → "¿Es justo este aviso?" with "✓ De acuerdo" and "✗ No"
  it("Case 1 · Spanish browser → the question and the two buttons in Spanish", async () => {
    const { card, button } = await page("es-ES");
    expect(card().textContent).toContain("¿Es justo este aviso?");
    expect(button("✓ De acuerdo")).toBeDefined();
    expect(button("✗ No")).toBeDefined();
  });

  // Case 2 · the two buttons → taller than the card's text buttons (Guardar, Cancelar)
  it("Case 2 · the vote buttons are at least 1.25 times as tall as the card's text buttons", async () => {
    const { button, height } = await page("es-ES");
    const agree = height(button("✓ De acuerdo")!);
    const disagree = height(button("✗ No")!);
    button("✗ No")!.click();
    const save = height(button("Guardar")!);
    expect(save).toBeGreaterThan(0);
    expect(agree).toBeGreaterThanOrEqual(save * 1.25);
    expect(disagree).toBe(agree);
  });

  // Case 3 · an English browser → "Is this flag fair?" with "✓ Agree" and "✗ Disagree"
  it("Case 3 · English browser → the question and the two buttons in English, no Spanish", async () => {
    const { card, button } = await page("en-US");
    expect(card().textContent).toContain("Is this flag fair?");
    expect(button("✓ Agree")).toBeDefined();
    expect(button("✗ Disagree")).toBeDefined();
    expect(card().textContent).not.toContain("¿Es justo");
  });

  // Case 4 · a click on "✓ De acuerdo" → the flag is marked correct at once, with no reason
  it("Case 4 · ✓ De acuerdo → marked correct, the buttons give way to the mark", async () => {
    const { card, button, sent } = await page("es-ES");
    button("✓ De acuerdo")!.click();
    expect(sent).toEqual([["ad_hominem-42.0", "correct", ""]]);
    expect(card().textContent).toContain("Marcado: correcto");
    expect(button("✓ De acuerdo")).toBeUndefined();
  });

  // Case 5 · a card marked before → "Marcaste: ✓ De acuerdo" and "cambiar", which brings the question back
  it("Case 5 · a marked card → \"Marcaste: ✓ De acuerdo\" and \"cambiar\"; cambiar asks again", async () => {
    const { card, button } = await page("es-ES", "correct");
    expect(card().textContent).toContain("Marcaste: ✓ De acuerdo");
    expect(card().textContent).not.toContain("¿Es justo este aviso?");
    button("cambiar")!.click();
    expect(card().textContent).toContain("¿Es justo este aviso?");
    expect(button("✓ De acuerdo")).toBeDefined();
  });
});
