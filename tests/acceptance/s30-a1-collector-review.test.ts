// S30 A1 (collector part) · Only the owner's approved analyses are served
//
// Story: A stranger uploads an analysis of video "abcdefgh" in Spanish: the collector answers 202 and serves nothing
// for it. The owner runs `fact-checker shared list` and sees one line: abcdefgh, es, opus, 2 flags, the uploader's
// install id and the date. `fact-checker shared approve abcdefgh es` makes it served to anyone; `reject` on another
// one deletes it and it is never served. An upload from the owner's own helper (with the admin token in its `.env`) is
// served at once. A row shared before this slice is pending until the owner approves it.
//
// Setup: the collector Worker's fetch handler, called directly with a Request, and an env whose D1 binding is Node's
// built-in SQLite with the collector's schema (tests/acceptance/s24_d1_fake.ts). For the old rows, a bare SQLite
// database with the S28 table and one row, then schema.sql applied twice. No wrangler, no network. The CLI side is
// checked in test_s30_a1_shared_review.py.
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";
import worker from "../../src/collector/src/index";
import { fakeD1 } from "./s24_d1_fake";

const STRANGER = "11111111-1111-4111-8111-111111111111";
const OTHER = "22222222-2222-4222-8222-222222222222";
const TOKEN = "admin-secret";
const BASE = "https://collector.example/analyses";

const flag = (i: number) => ({
  id: `false-${i}.0`, t: i, speaker: "Invitado", quote: "el paro bajó a la mitad en un año", type: "inaccuracy",
  label: "false", reason: "Motivo inventado.", confidence: 0.9, related: null,
  sources: [{ publisher: "INE", url: "https://www.ine.es/paro", date: "2026-10-01" }], note: null, on_player: true,
});
const reader = (model: string) => ({ provider: "claude", model });
const analysis = (video = "abcdefgh", model = "opus", extra: object = {}) => ({
  video_id: video, lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Entrevista",
  channel: "Canal", duration: 23, speakers: {}, cost_usd: 7.9, analysed_until: 23, helper_version: "0.1.0",
  readers: { parts: reader(model), verdict: reader(model), judge: reader(model), search: reader("sonnet") },
  flags: [flag(1), flag(2)], ...extra,
});

function collector() {
  const env = { DB: fakeD1(), ADMIN_TOKEN: TOKEN } as any;
  const auth = (token?: string): Record<string, string> => (token ? { Authorization: `Bearer ${token}` } : {});
  const put = (body: object, { video = "abcdefgh", installId = STRANGER, token = "" } = {}) =>
    worker.fetch(new Request(`${BASE}/${video}?lang=es`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...auth(token) },
      body: JSON.stringify({ install_id: installId, analysis: body }),
    }), env);
  const get = (video = "abcdefgh") => worker.fetch(new Request(`${BASE}/${video}?lang=es`), env);
  const list = (token?: string) => worker.fetch(new Request(BASE, { headers: auth(token) }), env);
  const review = (action: "approve" | "reject", video = "abcdefgh", token = TOKEN) =>
    worker.fetch(new Request(`${BASE}/${video}/${action}?lang=es`, { method: "POST", headers: auth(token) }), env);
  return { put, get, list, review };
}

describe("S30 A1 · Only the owner's approved analyses are served", () => {
  // Case 1 · a stranger's upload → 202 pending, GET 404
  it("Case 1 · a stranger's upload → 202, and GET answers 404", async () => {
    const { put, get } = collector();
    const res = await put(analysis());
    expect(res.status).toBe(202);
    expect(await res.json()).toEqual({ pending: true });
    expect((await get()).status).toBe(404);
  });

  // Case 2 · the owner lists the pending uploads → video, lang, model, flag count, install id, date; 401 without token
  it("Case 2 · GET /analyses with the token → one pending row; without it → 401", async () => {
    const { put, list } = collector();
    await put(analysis());
    expect((await list()).status).toBe(401);
    expect((await list("wrong")).status).toBe(401);
    const res = await list(TOKEN);
    expect(res.status).toBe(200);
    const { rows } = (await res.json()) as any;
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ video_id: "abcdefgh", lang: "es", model: "opus", flags: 2, install_id: STRANGER });
    expect(rows[0].received_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  // Case 3 · approve → the analysis is served to anyone, and the pending list is empty
  it("Case 3 · approve → 200; GET serves the analysis; the list is empty", async () => {
    const { put, get, list, review } = collector();
    await put(analysis());
    expect((await review("approve", "abcdefgh", "")).status).toBe(401);
    expect((await review("approve")).status).toBe(200);
    const res = await get();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(analysis());
    expect(((await (await list(TOKEN)).json()) as any).rows).toEqual([]);
  });

  // Case 4 · reject → deleted, never served; a second review of it → 404
  it("Case 4 · reject → 200; GET still 404; nothing left to approve", async () => {
    const { put, get, list, review } = collector();
    await put(analysis("otherone"), { video: "otherone" });
    expect((await review("reject", "otherone", "")).status).toBe(401);
    expect((await review("reject", "otherone")).status).toBe(200);
    expect((await get("otherone")).status).toBe(404);
    expect(((await (await list(TOKEN)).json()) as any).rows).toEqual([]);
    expect((await review("approve", "otherone")).status).toBe(404);
  });

  // Case 5 · the owner's own upload → served at once, never pending
  it("Case 5 · an upload with the admin token → 201 and served at once", async () => {
    const { put, get, list } = collector();
    expect((await put(analysis(), { token: TOKEN })).status).toBe(201);
    expect((await get()).status).toBe(200);
    expect(((await (await list(TOKEN)).json()) as any).rows).toEqual([]);
  });

  // Case 6 · a stranger's upload over a served one → stays pending, the served one is unchanged
  it("Case 6 · a stranger's better upload over a served one → pending; the served one stays", async () => {
    const { put, get } = collector();
    await put(analysis("abcdefgh", "sonnet"), { token: TOKEN });
    expect((await put(analysis("abcdefgh", "opus", { cost_usd: 1 }), { installId: OTHER })).status).toBe(202);
    expect(((await (await get()).json()) as any).readers.parts.model).toBe("sonnet");
  });
});

describe("S30 A1 · rows shared before this slice", () => {
  // Case 7 · an S28 row in `analyses` → after schema.sql (applied twice) it is pending, not served
  it("Case 7 · an old served row → pending after schema.sql, also when applied twice", () => {
    const db = new DatabaseSync(":memory:");
    db.exec(`CREATE TABLE analyses (video_id TEXT NOT NULL, lang TEXT NOT NULL, analysis TEXT NOT NULL, model TEXT,
      rank INTEGER NOT NULL, install_id TEXT NOT NULL, received_at TEXT NOT NULL, PRIMARY KEY (video_id, lang))`);
    db.prepare("INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?)")
      .run("oldvideo", "es", JSON.stringify(analysis("oldvideo")), "opus", 2, STRANGER, "2026-11-14T10:00:00.000Z");
    const schema = readFileSync(new URL("../../src/collector/schema.sql", import.meta.url), "utf8");
    db.exec(schema);
    db.exec(schema);
    expect(db.prepare("SELECT COUNT(*) AS n FROM analyses").get()).toEqual({ n: 0 });
    expect(db.prepare("SELECT video_id, lang, model, install_id FROM pending").all().map((r) => ({ ...r })))
      .toEqual([{ video_id: "oldvideo", lang: "es", model: "opus", install_id: STRANGER }]);
    // An analysis that the owner approves later stays served when schema.sql is applied again.
    db.prepare("INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?)")
      .run("newvideo", "es", JSON.stringify(analysis("newvideo")), "opus", 2, OTHER, "2026-11-16T10:00:00.000Z");
    db.exec(schema);
    expect(db.prepare("SELECT video_id FROM analyses").all().map((r) => ({ ...r }))).toEqual([{ video_id: "newvideo" }]);
  });
});
