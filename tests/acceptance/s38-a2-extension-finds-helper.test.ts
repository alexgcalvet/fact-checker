// S38 A2 · A taken port moves the helper and the extension follows (the extension side)
//
// Story: Another program holds port 8765. The helper starts at login on 8766 instead, and on YouTube the "Analizar
// este vídeo" button starts an analysis whose flag file appears in the helper home. With all five ports 8765–8769
// taken, the helper log says so in one line and the helper stops; it does not restart in a loop.
//
// Setup: the real service worker with a stub `chrome` and a stub `fetch` that plays the local ports. Another program
// answers every address on its port with an HTML 404. The helper answers `/health` with its name, and the analyse
// request with "running". A port with nothing on it refuses the connection (fetch rejects with a TypeError, as Chrome
// does). The helper side is checked in test_s38_a2_port_fallback.py.
import { afterAll, describe, expect, it, vi } from "vitest";

const RUNNING = { video_id: "abc123", status: "running" };
const ports: Record<number, "foreign" | "helper"> = { 8765: "foreign", 8766: "helper" };
const urls: string[] = [];
let listener: any;

vi.stubGlobal("fetch", vi.fn(async (url: string) => {
  urls.push(url);
  const { port, pathname } = new URL(url);
  const holder = ports[Number(port)];
  if (!holder) throw new TypeError("Failed to fetch");
  if (holder === "foreign") return { ok: false, status: 404, json: async () => { throw new SyntaxError("HTML"); } };
  return { ok: true, status: 200, json: async () => (pathname === "/health" ? { app: "fact-checker" } : RUNNING) };
}));
vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (f: any) => { listener = f; } } } });
afterAll(() => { vi.unstubAllGlobals(); });

const send = (req: object) => new Promise<any>((done) => listener(req, {}, done));

describe("S38 A2 · the extension finds the helper on the next port", () => {
  // Case 1 · another program holds 8765, the helper is on 8766 → the analyse request reaches 8766 and answers running
  it("Case 1 · a foreign program on 8765 → the analyse request goes to the helper on 8766", async () => {
    vi.resetModules();
    await import("../../src/extension/src/sw");
    const reply = await send({ kind: "analyze", videoId: "abc123", from: 0, lang: "es" });
    expect(reply).toEqual({ ok: true, data: RUNNING });
    expect(urls).toContain("http://127.0.0.1:8766/health");
    expect(urls.at(-1)).toBe("http://127.0.0.1:8766/videos/abc123?from=0&lang=es");
  });

  // Case 2 · the next request → straight to 8766, with no new search
  it("Case 2 · the next request → straight to the kept port 8766", async () => {
    urls.length = 0;
    const reply = await send({ kind: "flags", videoId: "abc123", at: 5 });
    expect(reply).toEqual({ ok: true, data: RUNNING });
    expect(urls).toEqual(["http://127.0.0.1:8766/videos/abc123?at=5"]);
  });

  // Case 3 · the helper moves to 8767 → the failed request looks again and reaches 8767
  it("Case 3 · the helper moves to 8767 → the extension looks again and follows", async () => {
    urls.length = 0;
    delete ports[8766];
    ports[8767] = "helper";
    const reply = await send({ kind: "flags", videoId: "abc123", at: 6 });
    expect(reply).toEqual({ ok: true, data: RUNNING });
    expect(urls.at(-1)).toBe("http://127.0.0.1:8767/videos/abc123?at=6");
  });

  // Case 4 · no helper on any of the five ports → the service worker answers down
  it("Case 4 · no helper on 8765–8769 → down", async () => {
    delete ports[8767];
    const reply = await send({ kind: "flags", videoId: "abc123", at: 7 });
    expect(reply).toEqual({ ok: false, down: true });
  });
});
