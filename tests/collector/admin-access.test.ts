// S1 A1 · Only a valid Cloudflare Access login reaches the review page and its calls
//
// Story: A request to the review page or to one of its calls carries the token that Cloudflare Access adds after the
// owner's login: it gets the page or the list. The same request with no token, an expired token, a token for another
// application, or a token signed by another key gets 401. A request to the review page with only the owner's admin
// token gets 401; the owner's helper lists /analyses with the admin token as before.
//
// Setup: the collector Worker's fetch handler, called directly with a Request. The env has the D1 fake
// (tests/support/d1_fake.ts) with one stranger's pending upload, the invented TEAM_DOMAIN and POLICY_AUD, the admin
// token, and an ASSETS binding whose fetch answers a small HTML page. A stubbed global fetch serves the fake key set
// at <TEAM_DOMAIN>/cdn-cgi/access/certs (tests/support/access_fake.ts). No wrangler, no network.
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import worker from "../../src/collector/src/index";
import { CERTS, HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { fakeD1 } from "../support/d1_fake";
import { fakeLimit } from "../support/limit_fake";

const ORIGIN = "https://collector.example";
const STRANGER = "11111111-1111-4111-8111-111111111111";
const PAGE = "<!doctype html><title>Review</title>";

const analysis = {
  video_id: "abcdefgh", lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Entrevista",
  channel: "Canal", duration: 23, speakers: { SPEAKER_00: "Ana" }, cost_usd: 0.5, analysed_until: 23,
  helper_version: "0.1.0", readers: { parts: { provider: "claude", model: "opus" } },
  flags: [{ id: "false-1.0", t: 1, speaker: "Ana", quote: "una cifra", type: "inaccuracy", label: "false",
            reason: "Motivo inventado.", confidence: 0.9, related: null, sources: [] }],
};

const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

async function collector() {
  const assets = { fetch: async () => new Response(PAGE, { headers: { "Content-Type": "text/html" } }) };
  const env = { DB: fakeD1(), WRITES: fakeLimit(), ADMIN_TOKEN: "admin-secret", TEAM_DOMAIN, POLICY_AUD, ASSETS: assets } as any;
  const put = await worker.fetch(new Request(`${ORIGIN}/analyses/abcdefgh?lang=es`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ install_id: STRANGER, analysis }),
  }), env);
  expect(put.status).toBe(202);
  const call = (path: string, headers: Record<string, string> = {}, method = "GET") =>
    worker.fetch(new Request(`${ORIGIN}${path}`, { method, headers }), env);
  const pending = () => env.DB.rows("SELECT video_id FROM pending").length;
  return { call, pending };
}

const access = async (claims: Record<string, unknown> = {}, signer: "team" | "stranger" = "team") =>
  ({ [HEADER]: await token(claims, signer) });

describe("S1 A1 · Only a valid Cloudflare Access login reaches the review page and its calls", () => {
  // Case 1 · a valid Access token → the page from ASSETS, and the pending list
  it("Case 1 · a valid token → GET /admin gives the page; GET /admin/pending gives the list", async () => {
    const { call } = await collector();
    const page = await call("/admin", await access());
    expect(page.status).toBe(200);
    expect(await page.text()).toBe(PAGE);
    const list = await call("/admin/pending", await access());
    expect(list.status).toBe(200);
    const { rows } = (await list.json()) as any;
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ video_id: "abcdefgh", lang: "es" });
  });

  // Case 2 · no token → 401 on the page, the list, one upload, approve and reject; nothing is reviewed
  it("Case 2 · no token → 401 on every /admin route, and the upload stays pending", async () => {
    const { call, pending } = await collector();
    expect((await call("/admin")).status).toBe(401);
    expect((await call("/admin/pending")).status).toBe(401);
    expect((await call("/admin/pending/abcdefgh?lang=es")).status).toBe(401);
    expect((await call("/admin/pending/abcdefgh/approve?lang=es", {}, "POST")).status).toBe(401);
    expect((await call("/admin/pending/abcdefgh/reject?lang=es", {}, "POST")).status).toBe(401);
    expect(pending()).toBe(1);
  });

  // Case 3 · an expired token → 401
  it("Case 3 · an expired token → 401", async () => {
    const { call } = await collector();
    const past = Math.floor(Date.now() / 1000) - 7200;
    const expired = await access({ iat: past, nbf: past, exp: past + 3600 });
    expect((await call("/admin", expired)).status).toBe(401);
    expect((await call("/admin/pending", expired)).status).toBe(401);
  });

  // Case 4 · a token for another Access application (another AUD tag) → 401
  it("Case 4 · a token for another application → 401", async () => {
    const { call } = await collector();
    const other = await access({ aud: ["another-application-aud-tag"] });
    expect((await call("/admin", other)).status).toBe(401);
    expect((await call("/admin/pending", other)).status).toBe(401);
  });

  // Case 5 · a token signed by a key outside the team's key set → 401
  it("Case 5 · a token signed by another key → 401", async () => {
    const { call, pending } = await collector();
    const forged = await access({}, "stranger");
    expect((await call("/admin", forged)).status).toBe(401);
    expect((await call("/admin/pending", forged)).status).toBe(401);
    expect((await call("/admin/pending/abcdefgh/approve?lang=es", forged, "POST")).status).toBe(401);
    expect(pending()).toBe(1);
  });

  // Case 6 · FR-001: a token from another issuer → 401, and the Worker asks keys only of TEAM_DOMAIN
  it("Case 6 · a token from another team → 401; the only key URL fetched is TEAM_DOMAIN's", async () => {
    const { call } = await collector();
    const elsewhere = await access({ iss: "https://attacker.example.cloudflareaccess.com" });
    expect((await call("/admin/pending", elsewhere)).status).toBe(401);
    expect(keys.urls.length).toBeGreaterThan(0);
    expect(new Set(keys.urls)).toEqual(new Set([CERTS]));
  });

  // Case 7 · only the owner's admin token on the page and its calls → 401
  it("Case 7 · the admin token alone → 401 on /admin and /admin/pending", async () => {
    const { call } = await collector();
    const admin = { Authorization: "Bearer admin-secret" };
    expect((await call("/admin", admin)).status).toBe(401);
    expect((await call("/admin/pending", admin)).status).toBe(401);
  });

  // Case 8 · the owner's helper lists /analyses with the admin token as before; no token → 401
  it("Case 8 · GET /analyses with the admin token → 200 with the pending row; without it → 401", async () => {
    const { call } = await collector();
    expect((await call("/analyses")).status).toBe(401);
    expect((await call("/analyses", await access())).status).toBe(401);
    const res = await call("/analyses", { Authorization: "Bearer admin-secret" });
    expect(res.status).toBe(200);
    expect(((await res.json()) as any).rows).toHaveLength(1);
  });
});

// Inline 2026-11-22 · Another site cannot make the owner's browser act on the review page
//
// Story: The owner, logged in through Access, visits another site. Its page posts Reject to the review page with the
// owner's cookie. The collector answers 403 and the upload stays pending; the review page's own post still works.
describe("Another site cannot make the owner's browser act on the review page", () => {
  it("POST reject with another Origin → 403, still pending; with the collector's Origin → 200", async () => {
    const { call, pending } = await collector();
    const owner = await access();
    expect((await call("/admin/pending/abcdefgh/reject?lang=es", { ...owner, Origin: "https://evil.example" }, "POST")).status)
      .toBe(403);
    expect(pending()).toBe(1);
    expect((await call("/admin/pending/abcdefgh/reject?lang=es", { ...owner, Origin: ORIGIN }, "POST")).status).toBe(200);
    expect(pending()).toBe(0);
  });
});
