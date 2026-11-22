// Inline 2026-11-22 · The owner turns a video off and on for the public (the collector)
//
// Story: The owner sees an approved debate they do not want on the page yet. In /admin they switch "Visible en la web"
// off. The public API stops serving it: it leaves the video list, its video, its flags and its seeks answer 404, and
// its share tags turn neutral. The review page still lists it, marked off, so the owner can switch it back on. Other
// videos are untouched, and without the owner's login nothing changes.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts (debate01 in es and en, intervw1 in es); the fake Access key set.
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";

const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

async function collector() {
  const c = await apiCollector();
  Object.assign(c.env, { TEAM_DOMAIN, POLICY_AUD, ASSETS: { fetch: async () => new Response("<title>x</title>") } });
  const owner = { [HEADER]: await token() };
  const power = (video: string, action: string, headers: Record<string, string> = owner, method = "POST") =>
    c.send(`/admin/videos/${video}/active/${action}`, { method, headers });
  const status = async (path: string) => (await c.get(path)).status;
  const listed = async () => (((await (await c.get("/api/videos")).json()) as any).videos as any[]).map((v) => v.video_id);
  const approved = async () =>
    (((await (await c.send("/admin/approved", { headers: owner })).json()) as any).rows as any[]).filter((r) => r.video_id === "debate01");
  return { power, status, listed, approved, c };
}

describe("The owner turns a video off and on for the public", () => {
  it("Case 1 · off → gone from the list, the video, its flags and its seeks, in both languages; others stay", async () => {
    const { power, status, listed, c } = await collector();
    expect(await listed()).toContain("debate01");
    expect((await power("debate01", "off")).status).toBe(200);
    expect(await listed()).toEqual(["intervw1"]);
    expect(await status("/api/videos/debate01?lang=es")).toBe(404);
    expect(await status("/api/videos/debate01?lang=en")).toBe(404);
    expect(await status("/api/videos/debate01/flags?lang=es")).toBe(404);
    const seek = await c.send("/api/visits", { method: "POST", body: JSON.stringify({ video_id: "debate01", lang: "es", kind: "seek" }) });
    expect(seek.status).toBe(404);
    expect(await status("/api/videos/intervw1?lang=es")).toBe(200);
  });

  it("Case 2 · off → /admin/approved still lists it with active false; on brings it back", async () => {
    const { power, status, approved, listed } = await collector();
    for (const row of await approved()) expect(row.active).toBe(true);
    await power("debate01", "off");
    const rows = await approved();
    expect(rows).toHaveLength(2);
    for (const row of rows) expect(row.active).toBe(false);
    expect((await power("debate01", "on")).status).toBe(200);
    expect(await status("/api/videos/debate01?lang=es")).toBe(200);
    expect(await listed()).toContain("debate01");
  });

  it("Case 3 · no login or the admin token only → 401; a pending or unknown video → 404; GET → 405", async () => {
    const { power, status } = await collector();
    expect((await power("debate01", "off", {})).status).toBe(401);
    expect((await power("debate01", "off", { Authorization: "Bearer admin-secret" })).status).toBe(401);
    expect(await status("/api/videos/debate01?lang=es")).toBe(200);
    expect((await power("pending1", "off")).status).toBe(404);
    expect((await power("nothere1", "off")).status).toBe(404);
    expect((await power("debate01", "off", undefined, "GET")).status).toBe(405);
    expect((await power("debate01", "other")).status).toBe(404);
  });
});
