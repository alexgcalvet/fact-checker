// The collector's /marks route: a tester's marks in, the owner's new rows out.
import { afterEach, describe, expect, it, vi } from "vitest";
import worker from "../../src/collector/src/index";
import { fakeD1 } from "../support/d1_fake";

// S24 A3 · The collector keeps valid marks and refuses bad requests
//
// Story: The owner's collector gets 2 valid marks from one tester and stores 2 rows. The same mark sent again with
// another verdict replaces its row. A request with a verdict "maybe", one with 501 marks, one over 256 KB, and the
// 21st accepted request of one tester in one day are each refused (400, 413, 413, 429) and store nothing.
//
// Setup: the collector Worker's fetch handler, called directly with a Request, and an env whose D1 binding is Node's
// built-in SQLite with the collector's schema (tests/support/d1_fake.ts). No wrangler, no network.
{
  const TESTER = "11111111-1111-4111-8111-111111111111";
  const OTHER = "22222222-2222-4222-8222-222222222222";

  const mark = (flagId: string, verdict = "unfair", quote = "usted no sabe nada de esto") => ({
    video_id: "abcdefgh", flag_id: flagId, t: 42, type: "fallacy", label: "ad_hominem", quote,
    confidence: 0.85, verdict, reason: "no es un ataque", provider: "claude", model: "opus",
  });

  function collector() {
    const DB = fakeD1();
    const env = { DB, ADMIN_TOKEN: "admin-secret" } as any;
    const post = (installId: string, marks: unknown[], extra: object = {}) =>
      worker.fetch(new Request("https://collector.example/marks", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ install_id: installId, helper_version: "0.1.0", marks, ...extra }),
      }), env);
    const rows = () => DB.rows("SELECT install_id, video_id, flag_id, verdict FROM marks ORDER BY flag_id, install_id");
    return { post, rows };
  }

  describe("S24 A3 · The collector keeps valid marks and refuses bad requests", () => {
    it("Case 1 · 2 valid marks → 200 {stored: 2} and 2 rows", async () => {
      const { post, rows } = collector();
      const res = await post(TESTER, [mark("a-1.0"), mark("a-2.0", "correct")]);
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ stored: 2 });
      expect(rows()).toEqual([
        { install_id: TESTER, video_id: "abcdefgh", flag_id: "a-1.0", verdict: "unfair" },
        { install_id: TESTER, video_id: "abcdefgh", flag_id: "a-2.0", verdict: "correct" },
      ]);
    });

    it("Case 2 · the same mark again with another verdict → its row is replaced; another tester's mark is its own row", async () => {
      const { post, rows } = collector();
      await post(TESTER, [mark("a-1.0"), mark("a-2.0", "correct")]);
      expect((await post(TESTER, [mark("a-1.0", "correct")])).status).toBe(200);
      expect((await post(OTHER, [mark("a-1.0")])).status).toBe(200);
      expect(rows()).toEqual([
        { install_id: TESTER, video_id: "abcdefgh", flag_id: "a-1.0", verdict: "correct" },
        { install_id: OTHER, video_id: "abcdefgh", flag_id: "a-1.0", verdict: "unfair" },
        { install_id: TESTER, video_id: "abcdefgh", flag_id: "a-2.0", verdict: "correct" },
      ]);
    });

    it("Case 3 · a bad field (verdict \"maybe\", an unknown field, a bad install id, a long quote) → 400 and nothing stored", async () => {
      const { post, rows } = collector();
      const bad = [
        post(TESTER, [mark("a-1.0"), mark("a-2.0", "maybe")]),
        post(TESTER, [{ ...mark("a-1.0"), email: "x@example.com" }]),
        post("not-a-uuid", [mark("a-1.0")]),
        post(TESTER, [mark("a-1.0", "unfair", "x".repeat(1001))]),
        post(TESTER, [mark("a-1.0")], { name: "Ana" }),
      ];
      for (const res of await Promise.all(bad)) expect(res.status).toBe(400);
      expect(rows()).toEqual([]);
    });

    it("Case 4 · 501 marks → 413 and nothing stored", async () => {
      const { post, rows } = collector();
      const res = await post(TESTER, Array.from({ length: 501 }, (_, i) => mark(`a-${i}.0`)));
      expect(res.status).toBe(413);
      expect(rows()).toEqual([]);
    });

    it("Case 5 · a request over 256 KB (300 marks of 1,000-character quotes) → 413 and nothing stored", async () => {
      const { post, rows } = collector();
      const res = await post(TESTER, Array.from({ length: 300 }, (_, i) => mark(`a-${i}.0`, "unfair", "y".repeat(1000))));
      expect(res.status).toBe(413);
      expect(rows()).toEqual([]);
    });

    it("Case 6 · the 21st accepted request of one tester in one day → 429 and nothing stored; another tester still gets in", async () => {
      const { post, rows } = collector();
      for (let i = 0; i < 20; i++) expect((await post(TESTER, [mark(`a-${i}.0`)])).status).toBe(200);
      const over = await post(TESTER, [mark("a-99.0")]);
      expect(over.status).toBe(429);
      expect(rows().some((r) => r.flag_id === "a-99.0")).toBe(false);
      expect(rows().length).toBe(20);
      expect((await post(OTHER, [mark("a-99.0")])).status).toBe(200);
    });

    it("Case 7 · a refused request (400) does not count toward the day's 20", async () => {
      const { post } = collector();
      for (let i = 0; i < 5; i++) await post(TESTER, [mark("a-1.0", "maybe")]);
      for (let i = 0; i < 20; i++) expect((await post(TESTER, [mark(`a-${i}.0`)])).status).toBe(200);
    });
  });
}

// S24 A4 · The owner pulls the new rows with the admin token (the collector side)
//
// Story: The owner sets `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env` and runs `fact-checker feedback pull`. It
// prints "3 new marks" and writes them to a file in `~/.fact-checker/feedback/`. A second pull prints "0 new marks".
// The collector answers 401 to a read without the token or with a wrong one, and the pull then names the token and
// exits 1.
//
// Setup: the collector Worker's fetch handler, called directly, with an env whose D1 binding is Node's built-in SQLite
// with the collector's schema and whose ADMIN_TOKEN is "admin-secret". Two testers send 3 marks at two fixed times.
// The pull command is checked in tests/helper/test_sharing.py (S24 A4).
describe("S24 A4 · The owner pulls the new rows with the admin token (the collector side)", () => {
  const TESTER = "11111111-1111-4111-8111-111111111111";
  const OTHER = "22222222-2222-4222-8222-222222222222";
  const mark = (flagId: string) => ({
    video_id: "abcdefgh", flag_id: flagId, t: 42, type: "fallacy", label: "ad_hominem", quote: "frase inventada",
    confidence: 0.85, verdict: "unfair", reason: "", provider: null, model: "opus",
  });

  async function collector() {
    const env = { DB: fakeD1(), ADMIN_TOKEN: "admin-secret" } as any;
    const post = (installId: string, marks: unknown[]) => worker.fetch(new Request("https://collector.example/marks", {
      method: "POST", body: JSON.stringify({ install_id: installId, helper_version: "0.1.0", marks }),
    }), env);
    const read = (since: string, token?: string) => worker.fetch(new Request(
      `https://collector.example/marks?since=${encodeURIComponent(since)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }), env);
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-15T10:00:00.000Z"));
    await post(TESTER, [mark("a-1.0"), mark("a-2.0")]);
    vi.setSystemTime(new Date("2026-11-15T11:30:00.000Z"));
    await post(OTHER, [mark("a-1.0")]);
    return read;
  }

  afterEach(() => { vi.useRealTimers(); });

  describe("S24 A4 · The owner pulls the new rows with the admin token (the collector side)", () => {
    it("Case 1 · a read with no token → 401 and no rows", async () => {
      const read = await collector();
      const res = await read("1970-01-01T00:00:00.000Z");
      expect(res.status).toBe(401);
      expect(JSON.stringify(await res.json())).not.toContain("a-1.0");
    });

    it("Case 2 · a read with a wrong token → 401", async () => {
      const read = await collector();
      expect((await read("1970-01-01T00:00:00.000Z", "wrong-token")).status).toBe(401);
    });

    it("Case 3 · the admin token → 200 with the 3 rows, each with its tester, time and every mark field", async () => {
      const read = await collector();
      const res = await read("1970-01-01T00:00:00.000Z", "admin-secret");
      expect(res.status).toBe(200);
      const { rows } = (await res.json()) as { rows: Record<string, unknown>[] };
      expect(rows.length).toBe(3);
      expect(rows[2]).toEqual({ install_id: OTHER, helper_version: "0.1.0", received_at: "2026-11-15T11:30:00.000Z",
        ...mark("a-1.0") });
    });

    it("Case 4 · since the first time → only the row received after it", async () => {
      const read = await collector();
      const { rows } = (await (await read("2026-11-15T10:00:00.000Z", "admin-secret")).json()) as { rows: any[] };
      expect(rows.map((r) => [r.install_id, r.flag_id])).toEqual([[OTHER, "a-1.0"]]);
    });
  });
});
