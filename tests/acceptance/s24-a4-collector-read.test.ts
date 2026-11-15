// S24 A4 · The owner pulls the new rows with the admin token (the collector side)
//
// Story: The owner sets `FEEDBACK_ADMIN_TOKEN` in `~/.fact-checker/.env` and runs `fact-checker feedback pull`. It
// prints "3 new marks" and writes them to a file in `~/.fact-checker/feedback/`. A second pull prints "0 new marks".
// The collector answers 401 to a read without the token or with a wrong one, and the pull then names the token and
// exits 1.
//
// Setup: the collector Worker's fetch handler, called directly, with an env whose D1 binding is Node's built-in SQLite
// with the collector's schema and whose ADMIN_TOKEN is "admin-secret". Two testers send 3 marks at two fixed times.
// The pull command is checked in test_s24_a4_feedback_pull.py.
import { afterEach, describe, expect, it, vi } from "vitest";
import worker from "../../src/collector/src/index";
import { fakeD1 } from "./s24_d1_fake";

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
