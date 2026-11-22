// S5 A3 · Only the owner can hide or show a flag
//
// Story: Someone with no Access login, or a helper with no admin token, asks to hide a flag: the answer is refused and
// the flag stays. Hiding a flag id that the analysis does not hold answers "not found".
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts (the debate approved in es with 12 flags). The env gets the invented TEAM_DOMAIN and
// POLICY_AUD, and a stubbed global fetch serves the fake Access key set (tests/support/access_fake.ts). The review
// page's route is POST /admin/analyses/<id>/flags/<flag_id>/hide|show?lang= (Access JWT); the helper's route is
// POST /analyses/<id>/flags/<flag_id>/hide|show?lang= (admin token). No wrangler, no network.
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";

const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

async function collector() {
  const c = await apiCollector();
  Object.assign(c.env, { TEAM_DOMAIN, POLICY_AUD });
  const post = (path: string, headers: Record<string, string> = {}) => c.send(path, { method: "POST", headers });
  const count = async () =>
    (((await (await c.get("/api/videos/debate01/flags?lang=es")).json()) as any).flags as unknown[]).length;
  return { post, count };
}

const PAGE = "/admin/analyses/debate01/flags/false-1.0";
const HELPER = "/analyses/debate01/flags/false-1.0";

describe("S5 A3 · Only the owner can hide or show a flag", () => {
  // Case 1 · the page's route with no Access JWT, or with only the admin token → 401; the flag stays
  it("Case 1 · /admin/… hide with no login or with the admin token → 401; 12 flags", async () => {
    const { post, count } = await collector();
    expect((await post(`${PAGE}/hide?lang=es`)).status).toBe(401);
    expect((await post(`${PAGE}/hide?lang=es`, { Authorization: "Bearer admin-secret" })).status).toBe(401);
    expect((await post(`${PAGE}/hide?lang=es`, { [HEADER]: await token({}, "stranger") })).status).toBe(401);
    expect(await count()).toBe(12);
  });

  // Case 2 · the helper's route with no token or a wrong token → 401; the flag stays
  it("Case 2 · /analyses/… hide with no token or a wrong one → 401; 12 flags", async () => {
    const { post, count } = await collector();
    expect((await post(`${HELPER}/hide?lang=es`)).status).toBe(401);
    expect((await post(`${HELPER}/hide?lang=es`, { Authorization: "Bearer not-the-token" })).status).toBe(401);
    expect(await count()).toBe(12);
  });

  // Case 3 · the owner, by either route → 200, the flag leaves; show by the other route → it comes back
  it("Case 3 · Access JWT hides (11), admin token shows (12); and the other way round", async () => {
    const { post, count } = await collector();
    expect((await post(`${PAGE}/hide?lang=es`, { [HEADER]: await token() })).status).toBe(200);
    expect(await count()).toBe(11);
    expect((await post(`${HELPER}/show?lang=es`, { Authorization: "Bearer admin-secret" })).status).toBe(200);
    expect(await count()).toBe(12);
    expect((await post(`${HELPER}/hide?lang=es`, { Authorization: "Bearer admin-secret" })).status).toBe(200);
    expect(await count()).toBe(11);
    expect((await post(`${PAGE}/show?lang=es`, { [HEADER]: await token() })).status).toBe(200);
    expect(await count()).toBe(12);
  });

  // Case 4 · a flag id that the analysis does not hold, or a video with no analysis → 404 "no such flag" by either
  // route (the body tells it from a route that does not exist, whose 404 says "not found")
  it("Case 4 · unknown flag id or video → 404 no such flag; 12 flags", async () => {
    const { post, count } = await collector();
    const owner = { [HEADER]: await token() };
    const missing = async (res: Response) => {
      expect(res.status).toBe(404);
      expect(await res.json()).toEqual({ error: "no such flag" });
    };
    await missing(await post("/admin/analyses/debate01/flags/false-99.0/hide?lang=es", owner));
    await missing(await post("/analyses/debate01/flags/false-99.0/hide?lang=es", { Authorization: "Bearer admin-secret" }));
    await missing(await post("/admin/analyses/nosuchvid/flags/false-1.0/hide?lang=es", owner));
    expect(await count()).toBe(12);
    console.log("PASS S5 A3 · Only the owner can hide or show a flag");
  });
});
