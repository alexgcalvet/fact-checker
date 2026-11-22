// @vitest-environment jsdom
// S11 A4 · The owner swaps a debate's halves (the web)
//
// Story: In a real debate the thumbnail shows the second guest on the left, so each guest's card shows the other's
// face. In /admin, on an approved debate of two guests, the owner flips the "Caras: intercambiar izquierda/derecha"
// switch. After that, each guest's card face in the viewer, 4:5 plate and profile cover use the other half: Ana, the
// first guest, gets the right half and Luis the left one. Flipping it back restores the speaker order. An interview,
// and a debate whose switch is never touched, keep the speaker order.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) stands in for the app's fetch.
// Its debate01 has the guests Ana and Luis, in that order; intervw1 has the one guest Pablo, which the owner uploads
// again with a summary of Pablo so that his profile exists. To show the owner's swap,
// the fetch adds `swap: true` to the opened video in the answers of GET /api/videos/<id> and GET /api/videos, as the
// collector serves them after the switch (s11-a4-swap-collector.test.ts proves that part). A fake YouTube player stands
// in for the embed, and a fake of the drawing library (modern-screenshot) for the PNG. jsdom loads no image, so every
// thumbnail stays in place.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector, interviewEs } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

vi.mock("../../src/web/node_modules/modern-screenshot/dist/index.mjs", () => ({
  domToBlob: async () => new Blob(["png"], { type: "image/png" }),
}));

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

// An invented summary of Pablo: one false claim of six checked.
const PABLO = {
  checked: 6, asked: 2, gravest: ["false-1.0"],
  flags: { "false-1.0": { verdict: "false", severity: "serious", device: null, question: null } },
};

async function open(path: string, swap: boolean) {
  const { get, owner } = await apiCollector();
  await owner({ ...interviewEs, summary: { Pablo: PABLO } });
  const id = path.split("/")[3];
  vi.stubGlobal("fetch", async (url: string | URL) => {
    const res = await get(String(url));
    const at = new URL(String(url), "https://collector.example").pathname;
    if (!swap || (at !== `/api/videos/${id}` && at !== "/api/videos")) return res;
    const body = (await res.json()) as any;
    if (body.videos) for (const v of body.videos) if (v.video_id === id) v.swap = true;
    if (body.video_id === id) body.swap = true;
    return new Response(JSON.stringify(body), { status: res.status, headers: res.headers });
  });
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="app"></div>';
  FakePlayer.last = undefined;
  const root = document.getElementById("app")!;
  await act(() => mount(root, FakePlayer as any));
  if (FakePlayer.last) await act(async () => FakePlayer.last!.ready());
  return root;
}

// The half of each guest's face in the viewer's guest cards, in their order: "left", "right" or "" (the centre).
const faces = (root: HTMLElement) =>
  [...root.querySelectorAll<HTMLElement>(".guest-card .face")].map((f) =>
    f.classList.contains("left") ? "left" : f.classList.contains("right") ? "right" : "");
// The half that an image shows: its data-half, which must agree with the class that crops it.
const halfOf = (img: HTMLImageElement) => {
  const h = img.dataset.half ?? "";
  expect(["left", "right"].filter((c) => img.classList.contains(c)).join("")).toBe(h);
  return h;
};
// The half that the profile's cover shows.
const cover = (root: HTMLElement) => {
  const img = root.querySelector<HTMLImageElement>(".cover img");
  return img ? halfOf(img) : "";
};
// The half that the 4:5 card's plate shows, after "Descargar ficha" and "Vertical 4:5".
async function plate() {
  const press = async (name: string) => {
    const b = [...document.querySelectorAll<HTMLElement>('button, [role="radio"]')].find((x) => text(x) === name);
    if (!b) throw new Error(`no control "${name}"`);
    await act(async () => b.click());
  };
  await press("Descargar ficha");
  await press("Vertical 4:5");
  const images = [...document.querySelectorAll<HTMLImageElement>('[data-card] [data-part="plate"] img')];
  expect(images.length).toBeGreaterThan(0);
  return [...new Set(images.map(halfOf))];
}

describe("S11 A4 · The owner swaps a debate's halves (the web)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  // Case 1 · switch never touched → the speaker order: Ana left, Luis right, in the viewer, the cover and the plate
  it("Case 1 · no swap → viewer faces left, right; Ana's cover and plate left; Luis's cover and plate right", async () => {
    expect(faces(await open("/es/v/debate01", false))).toEqual(["left", "right"]);
    const ana = await open("/es/v/debate01/ana", false);
    expect(cover(ana)).toBe("left");
    expect(await plate()).toEqual(["left"]);
    expect(cover(await open("/es/v/debate01/luis", false))).toBe("right");
    expect(await plate()).toEqual(["right"]);
  });

  // Case 2 · the owner swapped the halves → Ana right, Luis left, in the viewer, the cover and the plate
  it("Case 2 · swap → viewer faces right, left; Ana's cover and plate right; Luis's cover and plate left", async () => {
    expect(faces(await open("/es/v/debate01", true))).toEqual(["right", "left"]);
    const ana = await open("/es/v/debate01/ana", true);
    expect(cover(ana)).toBe("right");
    expect(await plate()).toEqual(["right"]);
    const luis = await open("/es/v/debate01/luis", true);
    expect(cover(luis)).toBe("left");
    expect(await plate()).toEqual(["left"]);
  });

  // Case 3 · an interview, with or without the swap → the whole thumbnail on the face, the cover and the plate
  it("Case 3 · interview, swap or not → the viewer face is the centre; Pablo's cover and plate show the whole thumbnail", async () => {
    for (const swap of [false, true]) {
      expect(faces(await open("/es/v/intervw1", swap))).toEqual([""]);
      const pablo = await open("/es/v/intervw1/pablo", swap);
      expect(pablo.querySelector(".cover img")).not.toBeNull();
      expect(cover(pablo)).toBe("");
      expect(await plate()).toEqual([""]);
    }
  });
});
