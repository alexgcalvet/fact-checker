// @vitest-environment jsdom
// The list: an old sort link keeps its order (copy pass, 2026-11-21)
//
// Story: The sort "Más avisos graves primero" (`?orden=graves`) is now "Más Falso y Engañoso primero"
// (`?orden=falso-enganoso`). A reader who opens an old `/es/videos?orden=graves` link sees the videos with the most Falso and
// Engañoso first, and the address becomes `/es/videos?orden=falso-enganoso` without a new history entry.
// S12 route move 2026-11-21
//
// Setup: a fake answer of `GET /api/videos` with three invented videos whose Falso + Engañoso differ from their dates.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const video = (video_id: string, published_at: string, falso: number, enganoso: number) => ({
  video_id, title: `Vídeo ${video_id}`, channel: "Canal inventado", duration: 3600, published_at, type: "debate", guests: [],
  flags: falso + enganoso, langs: ["es"], counts: { falso, enganoso, retorica: 0, evasiva: 0, puntualizacion: 0, contexto: 0 },
});
const VIDEOS = [video("new0001", "2026-11-20", 1, 0), video("mid00001", "2026-11-15", 2, 5), video("old00001", "2026-11-01", 0, 3)];

describe("The list: an old sort link keeps its order", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · /es/videos?orden=graves → by Falso + Engañoso, the address replaced by ?orden=falso-enganoso
  it("Case 1 · /es/videos?orden=graves → most Falso and Engañoso first, address /es/videos?orden=falso-enganoso, no new history entry", async () => {
    vi.stubGlobal("fetch", async (url: string | URL) =>
      (String(url) === "/api/videos" ? Response.json({ videos: VIDEOS }) : new Response("{}", { status: 404 })));
    history.replaceState(null, "", "/es/videos?orden=graves");
    const entries = history.length;
    document.body.innerHTML = '<div id="app"></div>';
    const root = document.getElementById("app")!;
    await act(() => mount(root, FakePlayer as any));
    const order = [...new Set([...root.querySelectorAll<HTMLAnchorElement>('a[href^="/es/v/"]')].map((a) => a.getAttribute("href")!.slice(6)))];
    expect(order).toEqual(["mid00001", "old00001", "new0001"]);
    expect(location.pathname + location.search).toBe("/es/videos?orden=falso-enganoso");
    expect(history.length).toBe(entries);
    const sort = [...root.querySelectorAll('[role="search"] [aria-haspopup="listbox"]')].find((b) => b.textContent!.startsWith("Orden"))!;
    expect(sort.textContent).toContain("Más Falso y Engañoso primero");
  });
});
