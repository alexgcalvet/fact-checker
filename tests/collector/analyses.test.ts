// The collector's /analyses routes: the first whole analysis kept, the owner's review, and only approved ones served.
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";
import worker from "../../src/collector/src/index";
import { fakeD1 } from "../support/d1_fake";
import { fakeLimit } from "../support/limit_fake";

// S28 A3 · The collector keeps the first whole analysis and guards it
//
// Story: The collector stores the owner's first upload of a video in Spanish (201) and serves it to anyone (S30:
// a stranger's upload waits for review, see tests/collector/analyses.test.ts (S30 A1)). A stranger's later upload
// read by Sonnet is refused (409) and the Opus one stays; their Opus upload over a Sonnet one waits for review (202).
// S4: the owner's own upload replaces any (tests/collector/owner-replaces.test.ts). An unfinished
// analysis, a source link that is not http(s), an unknown field (400), a body over 1 MB or with over 1,000 flags
// (413), and the 11th accepted upload of one tester in a UTC day (429) store nothing. The owner deletes the row with
// the admin token (200); a delete without it gets 401.
//
// Setup: the collector Worker's fetch handler, called directly with a Request, and an env whose D1 binding is Node's
// built-in SQLite with the collector's schema (tests/support/d1_fake.ts). No wrangler, no network.
{
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
    const env = { DB, WRITES: fakeLimit(), ADMIN_TOKEN: "admin-secret" } as any;
    // The owner's upload (TESTER, the admin token) is served at once; anyone else's (OTHER) goes through the rank rule.
    const put = (body: unknown, video = "abcdefgh", lang = "es", installId = TESTER) =>
      worker.fetch(new Request(`${BASE}/${video}?lang=${lang}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...(installId === OTHER ? {} : { Authorization: "Bearer admin-secret" }) },
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

    // Case 3 · a stranger's Opus upload over a Sonnet one → 202, pending; an unknown model ranks under Sonnet
    it("Case 3 · Opus after Sonnet → 202 pending; an unknown model after Sonnet → 409", async () => {
      const { put, get, count } = collector();
      await put(analysis("abcdefgh", "sonnet"));
      expect((await put(analysis("abcdefgh", "some-local-model"), "abcdefgh", "es", OTHER)).status).toBe(409);
      expect((await put(analysis("abcdefgh", "claude-opus-5-5"), "abcdefgh", "es", OTHER)).status).toBe(202);
      expect(((await (await get()).json()) as any).readers.parts.model).toBe("sonnet");
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
      expect((await put(analysis("video10xx"), "video10xx", "es", OTHER)).status).toBe(202);
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
}

// S30 A1 (collector part) · Only the owner's approved analyses are served
//
// Story: A stranger uploads an analysis of video "abcdefgh" in Spanish: the collector answers 202 and serves nothing
// for it. The owner runs `fact-checker shared list` and sees one line: abcdefgh, es, opus, 2 flags, the uploader's
// install id and the date. `fact-checker shared approve abcdefgh es` makes it served to anyone; `reject` on another
// one deletes it and it is never served. An upload from the owner's own helper (with the admin token in its `.env`) is
// served at once. A row shared before this slice is pending until the owner approves it.
//
// Setup: the collector Worker's fetch handler, called directly with a Request, and an env whose D1 binding is Node's
// built-in SQLite with the collector's schema (tests/support/d1_fake.ts). For the old rows, a bare SQLite
// database with the S28 table and one row, then schema.sql applied twice. No wrangler, no network. The CLI side is
// checked in tests/helper/test_sharing.py (S30 A1).
{
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
    const env = { DB: fakeD1(), WRITES: fakeLimit(), ADMIN_TOKEN: TOKEN } as any;
    const auth = (token?: string): Record<string, string> => (token ? { Authorization: `Bearer ${token}` } : {});
    const put = (body: object, { video = "abcdefgh", installId = STRANGER, token = "" } = {}) =>
      worker.fetch(new Request(`${BASE}/${video}?lang=es`, {
        method: "PUT", headers: { "Content-Type": "application/json", ...auth(token) },
        body: JSON.stringify({ install_id: installId, analysis: body }),
      }), env);
    const get = (video = "abcdefgh") => worker.fetch(new Request(`${BASE}/${video}?lang=es`), env);
    const list = (token?: string) => worker.fetch(new Request(BASE, { headers: auth(token) }), env);
    // A review names one upload, as the owner's list shows it.
    const review = async (action: "approve" | "reject", video = "abcdefgh", token = TOKEN) => {
      const { rows } = (await (await list(TOKEN)).json()) as any;
      const row = rows.find((r: any) => r.video_id === video) ?? {};
      const which = new URLSearchParams({ lang: "es", install: row.install_id ?? "", at: row.received_at ?? "" });
      return worker.fetch(new Request(`${BASE}/${video}/${action}?${which}`, { method: "POST", headers: auth(token) }), env);
    };
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

    // Case 4 · reject → deleted, never served; approving it after → 409
    it("Case 4 · reject → 200; GET still 404; nothing left to approve", async () => {
      const { put, get, list, review } = collector();
      await put(analysis("otherone"), { video: "otherone" });
      expect((await review("reject", "otherone", "")).status).toBe(401);
      expect((await review("reject", "otherone")).status).toBe(200);
      expect((await get("otherone")).status).toBe(404);
      expect(((await (await list(TOKEN)).json()) as any).rows).toEqual([]);
      expect((await review("approve", "otherone")).status).toBe(409);
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
}

// The collector takes every field that the helper shares: a field the helper adds and the Worker does not know makes
// every upload a silent 400 (S35 added people, claims and questions, and no analysis reached the collector).
{
  const shared = readFileSync(new URL("../../src/helper/fact_checker/analyses.py", import.meta.url), "utf8")
    .match(/SHARED = \(([^)]*)\)/)![1].match(/"(\w+)"/g)!.map((f) => f.slice(1, -1));

  const reader = { provider: "claude", model: "opus" };
  const values: Record<string, unknown> = {
    video_id: "abcdefgh", lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Entrevista",
    channel: "Canal", duration: 23, speakers: { SPEAKER_00: "Ana Ruiz" }, people: { "Ana Ruiz": { role: "guest" } },
    claims: { "Ana Ruiz": 26 }, questions: { "Ana Ruiz": 11 }, readers: { parts: reader }, cost_usd: 7.9,
    analysed_until: 23, flags: [],
  };

  describe("collector · shared analysis fields", () => {
    it("takes an analysis with every field of the helper's SHARED", async () => {
      expect(shared.filter((f) => !(f in values))).toEqual([]);
      const analysis = Object.fromEntries(shared.map((f) => [f, values[f]]));
      const res = await worker.fetch(new Request("https://collector.example/analyses/abcdefgh?lang=es", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ install_id: "11111111-1111-4111-8111-111111111111",
                               analysis: { ...analysis, helper_version: "0.1.0" } }),
      }), { DB: fakeD1(), WRITES: fakeLimit(), ADMIN_TOKEN: "admin-secret" } as any);
      expect(await res.json()).toEqual({ pending: true });
    });
  });
}
