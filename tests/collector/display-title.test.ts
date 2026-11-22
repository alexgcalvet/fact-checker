// @vitest-environment jsdom
// Inline 2026-11-22 · Each video has a display title: the clean title, or the owner's own (owner)
//
// Story: The owner uploads a video whose YouTube title shouts: «DIRECTO | ANA y LUIS en CANAL INVENTADO - DEBATE
// COMPLETO». The API keeps that raw title and adds the display title «Ana y Luis en Canal Inventado - Debate completo»:
// sentence case, with the names of our own data (the guests Ana and Luis, the channel Canal Inventado). The list, the
// video and the share tags use it. The owner then writes their own display title in /admin; it wins everywhere. An
// empty one gives the clean title back. Without the owner's login nothing changes.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts plus the shouting upload; the fake Access key set (tests/support/access_fake.ts); the
// static assets served from src/collector/web/ for the share tags.
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector, debateEs } from "../support/api_fakes";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "../../src/collector/web");
const RAW = "DIRECTO | ANA y LUIS en CANAL INVENTADO - DEBATE COMPLETO";
const CLEAN = "Ana y Luis en Canal Inventado - Debate completo";
const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

async function collector() {
  const c = await apiCollector();
  Object.assign(c.env, { TEAM_DOMAIN, POLICY_AUD, ASSETS: { fetch: async (r: Request) => {
    const path = new URL(r.url).pathname;
    return new Response(await readFile(join(WEB, path.endsWith("/") ? `${path}index.html` : path)));
  } } });
  await c.send("/analyses/shout001?lang=es", {
    method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer admin-secret" },
    body: JSON.stringify({ install_id: "00000000-0000-4000-8000-000000000000",
      analysis: { ...debateEs, video_id: "shout001", title: RAW, channel: "Canal Inventado" } }),
  });
  const owner = { [HEADER]: await token() };
  const name = (title: string, headers: Record<string, string> = owner) => c.send("/admin/videos/shout001/title", {
    method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
  const video = async () => (await (await c.get("/api/videos/shout001?lang=es")).json()) as any;
  const listed = async () => ((await (await c.get("/api/videos")).json()) as any).videos.find((v: any) => v.video_id === "shout001");
  const shared = async () => new DOMParser().parseFromString(await (await c.send("/es/v/shout001")).text(), "text/html").title;
  return { name, video, listed, shared };
}

describe("Each video has a display title", () => {
  it("Case 1 · a shouting title → raw kept; display title clean, with the names of our data, in the API and the share tags", async () => {
    const { video, listed, shared } = await collector();
    expect((await video()).title).toBe(RAW);
    expect((await video()).display_title).toBe(CLEAN);
    expect((await listed()).display_title).toBe(CLEAN);
    expect(await shared()).toBe(`${CLEAN} · DeFacto`);
  });

  it("Case 2 · the owner's display title wins; an empty one gives the clean title back; no login → 401", async () => {
    const { name, video, listed, shared } = await collector();
    expect((await name("Debate a dos, en Canal Inventado")).status).toBe(200);
    expect((await video()).display_title).toBe("Debate a dos, en Canal Inventado");
    expect((await listed()).display_title).toBe("Debate a dos, en Canal Inventado");
    expect(await shared()).toBe("Debate a dos, en Canal Inventado · DeFacto");
    expect((await name("Otro", {})).status).toBe(401);
    expect((await name("")).status).toBe(200);
    expect((await video()).display_title).toBe(CLEAN);
  });
});
