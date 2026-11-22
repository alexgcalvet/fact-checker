// @vitest-environment jsdom
// S7 A1 · Opening a video page counts a visit
// Story: Someone opens /es/v/debate01 twice and /en/v/debate01 once today. The owner opens /admin and its visits table
// shows debate01, "es", today, 2 visits; and debate01, "en", today, 1 visit.
// Edge case: WHEN someone opens /es/v/nope (no approved video) THEN the table shows no row for it.
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts), called directly like a browser;
// its ASSETS binding serves the committed files of src/collector/web/. The collector gets the invented TEAM_DOMAIN and
// POLICY_AUD, and a stubbed fetch serves the fake Access key set. The owner reads /admin/visits, the rows of the
// review page's visits table, with an Access token.
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, expect, it, vi } from "vitest";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "../../src/collector/web");
const assets = {
  fetch: async (request: Request) => {
    const path = new URL(request.url).pathname;
    try {
      return new Response(await readFile(join(WEB, path.endsWith("/") ? `${path}index.html` : path)));
    } catch {
      return new Response("not found", { status: 404 });
    }
  },
};
const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

it("counts each visit of an approved video page per language and day, and none for an unknown video", async () => {
  const { send, env } = await apiCollector();
  Object.assign(env, { TEAM_DOMAIN, POLICY_AUD, ASSETS: assets });
  for (const path of ["/es/v/debate01", "/es/v/debate01", "/en/v/debate01", "/es/v/nope"]) {
    expect((await send(path)).status).toBe(200);
  }
  const res = await send("/admin/visits", { headers: { [HEADER]: await token() } });
  expect(res.status).toBe(200);
  const { rows } = (await res.json()) as { rows: Record<string, unknown>[] };
  const today = new Date().toISOString().slice(0, 10);

  // Case 1 · two visits in Spanish, one in English → two rows for debate01, today
  expect(rows).toContainEqual({ video_id: "debate01", lang: "es", day: today, visits: 2, seeks: 0 });
  expect(rows).toContainEqual({ video_id: "debate01", lang: "en", day: today, visits: 1, seeks: 0 });

  // Case 2 · a visit of /es/v/nope → no row for it
  expect(rows.some((r) => r.video_id === "nope")).toBe(false);
  expect(rows).toHaveLength(2);
  console.log("PASS S7 A1 · Opening a video page counts a visit");
});
