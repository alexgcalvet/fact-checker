// S28 A3 · The collector keeps the first whole analysis and guards it
//
// Story: The collector stores the owner's first upload of a video in Spanish (201) and serves it to anyone (S30:
// a stranger's upload waits for review, see s30-a1-collector-review.test.ts). A later upload read
// by Sonnet is refused (409) and the Opus one stays; an Opus upload over a Sonnet one replaces it (200). An unfinished
// analysis, a source link that is not http(s), an unknown field (400), a body over 1 MB or with over 1,000 flags
// (413), and the 11th accepted upload of one tester in a UTC day (429) store nothing. The owner deletes the row with
// the admin token (200); a delete without it gets 401.
//
// Setup: the collector Worker's fetch handler, called directly with a Request, and an env whose D1 binding is Node's
// built-in SQLite with the collector's schema (tests/acceptance/s24_d1_fake.ts). No wrangler, no network.
import { describe, expect, it } from "vitest";
import worker from "../../src/collector/src/index";
import { fakeD1 } from "./s24_d1_fake";

const TESTER = "11111111-1111-4111-8111-111111111111";
const OTHER = "22222222-2222-4222-8222-222222222222";
const BASE = "https://collector.example/analyses";

const flag = (i: number, url = "https://www.ine.es/paro") => ({
  id: `false-${i}.0`, t: i, speaker: "Invitado", quote: "el paro bajó a la mitad en un año", type: "inaccuracy",
  label: "false", reason: "Motivo inventado.", confidence: 0.9, related: null,
  sources: [{ publisher: "INE", url, date: "2026-10-01" }], note: null, on_player: true,
  judge: { verdict: "keep", reason: "Se sostiene." },
});
const reader = (model: string) => ({ provider: "claude", model });
const analysis = (video = "abcdefgh", model = "opus", extra: object = {}) => ({
  video_id: video, lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Entrevista",
  channel: "Canal", duration: 23, speakers: {}, cost_usd: 7.9, analysed_until: 23, helper_version: "0.1.0",
  readers: { parts: reader(model), verdict: reader(model), judge: reader(model), search: reader("sonnet") },
  flags: [flag(1), flag(2)], ...extra,
});

function collector() {
  const DB = fakeD1();
  const env = { DB, ADMIN_TOKEN: "admin-secret" } as any;
  const put = (body: unknown, video = "abcdefgh", lang = "es", installId = TESTER) =>
    worker.fetch(new Request(`${BASE}/${video}?lang=${lang}`, {
      method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer admin-secret" },
      body: typeof body === "string" ? body : JSON.stringify({ install_id: installId, analysis: body }),
    }), env);
  const get = (video = "abcdefgh", lang = "es") => worker.fetch(new Request(`${BASE}/${video}?lang=${lang}`), env);
  const del = (token?: string, video = "abcdefgh", lang = "es") => worker.fetch(new Request(`${BASE}/${video}?lang=${lang}`, {
    method: "DELETE", headers: token ? { Authorization: `Bearer ${token}` } : {},
  }), env);
  const count = () => Number(DB.rows("SELECT COUNT(*) AS n FROM analyses")[0].n);
  return { put, get, del, count };
}

describe("S28 A3 · The collector keeps the first whole analysis and guards it", () => {
  // Case 1 · a first whole analysis → 201, served to anyone in its language only
  it("Case 1 · first upload → 201; GET in Spanish answers it, GET in English 404", async () => {
    const { put, get } = collector();
    expect((await put(analysis())).status).toBe(201);
    const res = await get();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(analysis());
    expect((await get("abcdefgh", "en")).status).toBe(404);
    expect((await get("zzzzzzzz")).status).toBe(404);
  });

  // Case 2 · a Sonnet upload over an Opus one → 409, the Opus one stays
  it("Case 2 · Sonnet after Opus → 409 and the Opus analysis stays", async () => {
    const { put, get } = collector();
    await put(analysis());
    expect((await put(analysis("abcdefgh", "sonnet"), "abcdefgh", "es", OTHER)).status).toBe(409);
    expect((await put(analysis("abcdefgh", "opus", { cost_usd: 1 }), "abcdefgh", "es", OTHER)).status).toBe(409);
    expect(((await (await get()).json()) as any).readers.parts.model).toBe("opus");
    expect(((await (await get()).json()) as any).cost_usd).toBe(7.9);
  });

  // Case 3 · an Opus upload over a Sonnet one → 200, replaced; an unknown model ranks under Sonnet
  it("Case 3 · Opus after Sonnet → 200 and replaced; an unknown model after Sonnet → 409", async () => {
    const { put, get, count } = collector();
    await put(analysis("abcdefgh", "sonnet"));
    expect((await put(analysis("abcdefgh", "some-local-model"), "abcdefgh", "es", OTHER)).status).toBe(409);
    expect((await put(analysis("abcdefgh", "claude-opus-5-5"), "abcdefgh", "es", OTHER)).status).toBe(200);
    expect(((await (await get()).json()) as any).readers.parts.model).toBe("claude-opus-5-5");
    expect(count()).toBe(1);
  });

  // Case 4 · malformed uploads → 400, nothing stored
  it("Case 4 · unfinished, a javascript: link, an unknown field, a wrong video or language, bad JSON → 400", async () => {
    const { put, count } = collector();
    const bad = [
      put(analysis("abcdefgh", "opus", { status: "running" })),
      put(analysis("abcdefgh", "opus", { flags: [flag(1, "javascript:alert(1)")] })),
      put(analysis("abcdefgh", "opus", { flags: [{ ...flag(1), related: { t: null, quote: "x", source: { publisher: "X", url: "javascript:x" } } }] })),
      put(analysis("abcdefgh", "opus", { transcript: "everything that was said" })),
      put(analysis("abcdefgh", "opus", { flags: [{ ...flag(1), confidence: 2 }] })),
      put(analysis("otherone")),
      put(analysis(), "abcdefgh", "en"),
      put(analysis(), "abcdefgh", "es", "not-a-uuid"),
      put("{not json"),
    ];
    for (const res of await Promise.all(bad)) expect(res.status).toBe(400);
    expect(count()).toBe(0);
  });

  // Case 5 · too big → 413, nothing stored
  it("Case 5 · a body over 1 MB, or 1,001 flags → 413", async () => {
    const { put, count } = collector();
    const long = analysis("abcdefgh", "opus", { title: "x".repeat(1024 * 1024) });
    expect((await put(long)).status).toBe(413);
    const many = analysis("abcdefgh", "opus", { flags: Array.from({ length: 1001 }, (_, i) => flag(i)) });
    expect((await put(many)).status).toBe(413);
    expect(count()).toBe(0);
  });

  // Case 6 · the hard stop → the 11th accepted upload of one tester in a day gets 429; another tester still uploads
  it("Case 6 · 10 uploads pass, the 11th of the same tester → 429 and nothing stored", async () => {
    const { put, count } = collector();
    for (let i = 0; i < 10; i++) expect((await put(analysis(`video${i}xx`), `video${i}xx`)).status).toBe(201);
    expect((await put(analysis("video10xx"), "video10xx")).status).toBe(429);
    expect(count()).toBe(10);
    expect((await put(analysis("video10xx"), "video10xx", "es", OTHER)).status).toBe(201);
  });

  // Case 7 · the owner deletes a row → 200 with the token, 401 without it or with a wrong one
  it("Case 7 · DELETE without the token → 401, with it → 200 and the analysis is gone", async () => {
    const { put, get, del } = collector();
    await put(analysis());
    expect((await del()).status).toBe(401);
    expect((await del("wrong")).status).toBe(401);
    expect((await get()).status).toBe(200);
    expect((await del("admin-secret")).status).toBe(200);
    expect((await get()).status).toBe(404);
  });
});
