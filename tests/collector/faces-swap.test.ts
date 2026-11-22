// S11 A4 · The owner swaps a debate's halves (the collector)
//
// Story: In a real debate the thumbnail shows the second guest on the left, so each guest's card shows the other's
// face. In /admin, on an approved debate of two guests, the owner flips the "Caras: intercambiar izquierda/derecha"
// switch. After that, each guest's card face in the viewer, 4:5 plate and profile cover use the other half: Ana, the
// first guest, gets the right half and Luis the left one. Flipping it back restores the speaker order. An interview,
// and a debate whose switch is never touched, keep the speaker order.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts: debate01 (guests Ana and Luis) approved in es and en, intervw1 approved in es, pending1
// waiting for review. The env gets the invented TEAM_DOMAIN and POLICY_AUD, and a stubbed global fetch serves the fake
// Access key set (tests/support/access_fake.ts). The switch calls POST /admin/videos/<id>/faces/swap|keep with the
// owner's Access JWT. No wrangler, no network.
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";

const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

async function collector() {
  const c = await apiCollector();
  Object.assign(c.env, { TEAM_DOMAIN, POLICY_AUD });
  const owner = { [HEADER]: await token() };
  const flip = (video: string, action: string, headers: Record<string, string> = owner, method = "POST") =>
    c.send(`/admin/videos/${video}/faces/${action}`, { method, headers });
  const video = async (id: string, lang = "es") => ((await (await c.get(`/api/videos/${id}?lang=${lang}`)).json()) as any);
  const listed = async (id: string) =>
    (((await (await c.get("/api/videos")).json()) as any).videos as any[]).find((v) => v.video_id === id);
  const approved = async (id: string) =>
    (((await (await c.send("/admin/approved", { headers: owner })).json()) as any).rows as any[]).filter((r) => r.video_id === id);
  return { flip, video, listed, approved };
}

describe("S11 A4 · The owner swaps a debate's halves (the collector)", () => {
  // Case 1 · nothing flipped → swap is false in the video, the list and the review page
  it("Case 1 · untouched debate → swap false in /api/videos/<id>, /api/videos and /admin/approved", async () => {
    const { video, listed, approved } = await collector();
    expect((await video("debate01")).swap).toBe(false);
    expect((await listed("debate01")).swap).toBe(false);
    expect((await video("intervw1")).swap).toBe(false);
    for (const row of await approved("debate01")) expect(row.swap).toBe(false);
  });

  // Case 2 · the owner flips the switch → swap is true for the debate in both languages and in the list; the interview keeps false
  it("Case 2 · POST …/faces/swap with the Access JWT → 200; swap true in es, en, the list and /admin/approved", async () => {
    const { flip, video, listed, approved } = await collector();
    expect((await flip("debate01", "swap")).status).toBe(200);
    expect((await video("debate01", "es")).swap).toBe(true);
    expect((await video("debate01", "en")).swap).toBe(true);
    expect((await listed("debate01")).swap).toBe(true);
    const rows = await approved("debate01");
    expect(rows).toHaveLength(2);
    for (const row of rows) expect(row.swap).toBe(true);
    expect((await video("intervw1")).swap).toBe(false);
    expect((await listed("intervw1")).swap).toBe(false);
  });

  // Case 3 · flipped twice, then back → the speaker order again
  it("Case 3 · swap twice, then keep → swap false again", async () => {
    const { flip, video, listed } = await collector();
    expect((await flip("debate01", "swap")).status).toBe(200);
    expect((await flip("debate01", "swap")).status).toBe(200);
    expect((await video("debate01")).swap).toBe(true);
    expect((await flip("debate01", "keep")).status).toBe(200);
    expect((await video("debate01")).swap).toBe(false);
    expect((await listed("debate01")).swap).toBe(false);
  });

  // Case 4 · no Access login, or only the admin token → 401, and nothing changes
  it("Case 4 · no JWT or the admin token only → 401; swap stays false", async () => {
    const { flip, video } = await collector();
    expect((await flip("debate01", "swap", {})).status).toBe(401);
    expect((await flip("debate01", "swap", { Authorization: "Bearer admin-secret" })).status).toBe(401);
    expect((await video("debate01")).swap).toBe(false);
  });

  // Case 5 · a video that is not approved → 404; a GET → 405; another action → 404
  it("Case 5 · pending or unknown video → 404; GET → 405; …/faces/other → 404", async () => {
    const { flip } = await collector();
    expect((await flip("pending1", "swap")).status).toBe(404);
    expect((await flip("nosuchvid", "swap")).status).toBe(404);
    expect((await flip("debate01", "swap", undefined, "GET")).status).toBe(405);
    expect((await flip("debate01", "other")).status).toBe(404);
  });
});
