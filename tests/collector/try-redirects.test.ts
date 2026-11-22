// @vitest-environment jsdom
// S7 A3 · An old test page link opens the viewer
// Story: Someone with a Spanish browser opens an old link /try/debate01 and lands on /es/v/debate01; with an English
// browser, on /en/v/debate01. /try/try.js no longer exists.
// Setup: the invented collector (tests/support/api_fakes.ts), called directly like a browser with its Accept-Language;
// its ASSETS binding serves the committed files of src/collector/web/.
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";
import { ORIGIN, apiCollector } from "../support/api_fakes";

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

it("redirects an old /try/ link to the viewer in the browser's language, and the test page is gone", async () => {
  const { send, env } = await apiCollector();
  env.ASSETS = assets;

  // Case 1 · a Spanish browser opens /try/debate01 → a permanent redirect to /es/v/debate01
  const es = await send("/try/debate01", { headers: { "Accept-Language": "es-ES,es;q=0.9" }, redirect: "manual" });
  expect(es.status).toBe(301);
  expect(es.headers.get("Location")).toBe(`${ORIGIN}/es/v/debate01`);

  // Case 2 · an English browser → /en/v/debate01
  const en = await send("/try/debate01", { headers: { "Accept-Language": "en-GB" }, redirect: "manual" });
  expect(en.status).toBe(301);
  expect(en.headers.get("Location")).toBe(`${ORIGIN}/en/v/debate01`);

  // Case 3 · /try/try.js → not found, and the page's files are gone
  expect((await send("/try/try.js")).status).toBe(404);
  expect(existsSync(join(WEB, "try"))).toBe(false);
  console.log("PASS S7 A3 · An old test page link opens the viewer");
});
