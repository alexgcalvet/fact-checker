// S34 A3 · Quiet mode shows serious flags only
//
// Story: The person turns on quiet mode, now called "Solo graves", on the same video. The serious card shows; the
// moderate one does not. While the analysis is still running and nothing is judged yet, a flag shows only with a
// confidence of 90 % or more, as before.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel mounted as the content script
// mounts them. A judged file holds a serious false figure at second 10 (confidence 0.85) and a moderate misleading
// figure at second 30 (confidence 0.95). A running file holds two unjudged false figures: second 10 (confidence 0.92)
// and second 30 (confidence 0.85). The person turns quiet mode on with its box in ⚙ of the side panel. Playback moves
// to one second after each flag.
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { mountOverlay, settings } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";

const flag = (t: number, label: string, confidence: number, judge?: object) => ({
  id: `${label}-${t}.0`, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type: "inaccuracy", label,
  reason: `Motivo del segundo ${t}.`, confidence, on_player: true, related: null, sources: [], note: null,
  ...(judge ? { judge } : {}),
});
const judgedFile = {
  video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
  flags: [flag(10, "false", 0.85, { verdict: "keep", reason: "Bajó del 12 % al 11 %.", severity: "serious" }),
    flag(30, "misleading", 0.95, { verdict: "keep", reason: "Cuenta solo un año.", severity: "moderate" })],
} as any;
const runningFile = {
  video_id: "abcdefgh", published_at: "2026-11-10", status: "running", stop_reason: null,
  flags: [flag(10, "false", 0.92), flag(30, "false", 0.85)],
} as any;

function page(flagFile: object, lang: "es" | "en" = "es") {
  settings.lang = lang;
  settings.quiet = false;
  document.body.innerHTML = '<div id="movie_player"><video></video></div>';
  const player = document.getElementById("movie_player")!;
  const video = player.querySelector("video")!;
  Object.defineProperty(video, "duration", { value: 100, configurable: true });
  let now = 0;
  Object.defineProperty(video, "currentTime", { get: () => now, set: (t) => { now = t; }, configurable: true });
  const overlay = mountOverlay(player, video, () => flagFile as any, () => {});
  mountPanel(overlay.layer, video, () => flagFile as any, overlay.show);
  // The person opens the side panel and its ⚙; the quiet box is the one checkbox before the language choice.
  player.querySelector<HTMLElement>(".fc-panel-tab")!.click();
  [...player.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent === "⚙")!.click();
  const quietBox = () => player.querySelector<HTMLLabelElement>(".fc-settings label")!;
  const quietOn = () => quietBox().querySelector("input")!.click();
  const at = (t: number) => {
    now = t;
    video.dispatchEvent(new Event("timeupdate"));
    return [...player.querySelectorAll<HTMLElement>(".fc-card")];
  };
  return { at, quietBox, quietOn };
}

afterEach(() => { settings.lang = null; settings.quiet = false; });

describe("S34 A3 · Quiet mode shows serious flags only", () => {
  // Case 1 · the quiet box in ⚙ → it reads "Solo graves" ("Serious only" in English)
  it("Case 1 · the quiet box → \"Solo graves\" / \"Serious only\"", () => {
    expect(page(judgedFile).quietBox().textContent!.trim()).toBe("Solo graves");
    expect(page(judgedFile, "en").quietBox().textContent!.trim()).toBe("Serious only");
  });

  // Case 2 · quiet mode on a judged file → the serious card shows, even below 90 %
  it("Case 2 · quiet mode, the serious flag at 85 % → its card shows", () => {
    const { at, quietOn } = page(judgedFile);
    quietOn();
    expect(settings.quiet).toBe(true);
    const cards = at(11);
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain("Dato falso");
  });

  // Case 3 · quiet mode on a judged file → the moderate card does not show, even at 95 %
  it("Case 3 · quiet mode, the moderate flag at 95 % → no card", () => {
    const { at, quietOn } = page(judgedFile);
    quietOn();
    expect(at(31).length).toBe(0);
  });

  // Case 4 · quiet mode while the analysis runs, nothing judged → a flag at 92 % shows, a flag at 85 % does not
  it("Case 4 · quiet mode, unjudged flags → only the one at 90 % or more shows", () => {
    const { at, quietOn } = page(runningFile);
    quietOn();
    expect(at(11).length).toBe(1);
    expect(at(31).length).toBe(0);
  });

  // Case 5 · quiet mode off → both judged cards show as usual
  it("Case 5 · quiet mode off → both judged cards show", () => {
    const { at } = page(judgedFile);
    expect(at(11).length).toBe(1);
    expect(at(31).length).toBe(1);
  });
});
