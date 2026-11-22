// @vitest-environment jsdom
// S4 A3 · An English reader learns the analysis is only in Spanish
//
// Story: A reader opens `/en/v/intervw1`, analysed only in Spanish. Between the header and the video a note reads
// "This analysis is only in Spanish for now. Quotes and explanations are shown in Spanish." with a link "Abrir en
// español" to `/es/v/intervw1`. Its × hides it for the rest of the session. `/en/v/debate01`, analysed in English,
// shows no note.
// Copy pass 2026-11-21 (owner): "Quotes and explanations are shown in Spanish." moves to the note text's tooltip.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch:
// intervw1 is approved in Spanish only, debate01 in Spanish and English. A fake YouTube player
// (tests/support/youtube_fake.ts) stands in for the embed. The web app is mounted through its own `mount` export; a
// new mount in the same session stands in for a reload. Each case starts a new session.
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function open(path: string) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", async (url: string | URL) => get(String(url)));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  FakePlayer.last = undefined;
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  return root;
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const note = (root: HTMLElement) => root.querySelector('[role="note"]');

describe("S4 A3 · An English reader learns the analysis is only in Spanish", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · /en/v/intervw1 → the note between the header and the video, with "Abrir en español"
  it("Case 1 · /en/v/intervw1 → the note in English, between the header and the video, with «Abrir en español»", async () => {
    const root = await open("/en/v/intervw1");
    const n = note(root);
    expect(n, "the note").not.toBeNull();
    expect(text(n)).toContain("This analysis is only in Spanish for now.");
    expect(n!.querySelector('[data-tip="Quotes and explanations are shown in Spanish."]'), "the second sentence in a tooltip").not.toBeNull();
    const link = [...n!.querySelectorAll("a")].find((a) => a.textContent === "Abrir en español");
    expect(link?.getAttribute("href")).toBe("/es/v/intervw1");
    expect(link?.getAttribute("hreflang")).toBe("es");
    const header = root.querySelector("header")!;
    const video = root.querySelector("main")!;
    expect(header.compareDocumentPosition(n!) & Node.DOCUMENT_POSITION_FOLLOWING, "after the header").toBeTruthy();
    expect(n!.compareDocumentPosition(video) & Node.DOCUMENT_POSITION_FOLLOWING, "before the video").toBeTruthy();
  });

  // Case 2 · its × → the note goes, and stays gone on a reload in the same session
  it("Case 2 · a click on its × → the note goes, and a reload in the same session shows none", async () => {
    const root = await open("/en/v/intervw1");
    await act(async () => note(root)!.querySelector<HTMLButtonElement>('button[aria-label="Close"]')!.click());
    expect(note(root)).toBeNull();
    expect(note(await open("/en/v/intervw1"))).toBeNull();
  });

  // Case 3 · /en/v/debate01, analysed in English → no note
  it("Case 3 · /en/v/debate01 → no note", async () => {
    const root = await open("/en/v/debate01");
    expect(root.querySelector(".viewer"), "the viewer").not.toBeNull();
    expect(note(root)).toBeNull();
  });
});
