// @vitest-environment jsdom
// S1 A3 · A shared link previews the video
//
// Story: A chat app fetches /en/v/debate01; the page it gets is the web app, marked noindex, with the title "Invented
// debate" and the video's YouTube thumbnail in its share tags. For a video that is not approved, the tags keep the
// web's neutral title.
// Edge case: WHEN the title holds `"` and `<` THEN the share tags show them as text and the page stays valid.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts), called directly like a chat
// app's fetch. Its ASSETS binding serves the committed files of src/collector/web/ as the static assets do: a folder
// path gives its index.html, a missing file gives 404. The owner also uploads an approved video "quoted01" whose
// title holds `"` and `<`. The answer is parsed with the browser's DOMParser.
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { apiCollector, debateEn } from "../support/api_fakes";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "../../src/collector/web");
const APP = join(WEB, "app/index.html");
const QUOTED = 'Say "no" <b>now</b> & then';

const assets = {
  fetch: async (request: Request) => {
    const path = new URL(request.url).pathname;
    try {
      return new Response(await readFile(join(WEB, path.endsWith("/") ? `${path}index.html` : path)), {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    } catch {
      return new Response("not found", { status: 404 });
    }
  },
};

async function chatApp() {
  const { send, env } = await apiCollector();
  env.ASSETS = assets;
  const put = await send("/analyses/quoted01?lang=en", {
    method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer admin-secret" },
    body: JSON.stringify({ install_id: "00000000-0000-4000-8000-000000000000", analysis: { ...debateEn, video_id: "quoted01", title: QUOTED } }),
  });
  expect(put.status).toBe(201);
  return async (path: string) => {
    const res = await send(path);
    const html = await res.text();
    return { res, html, doc: new DOMParser().parseFromString(html, "text/html") };
  };
}

const meta = (doc: Document, property: string) =>
  doc.querySelector(`meta[property="${property}"], meta[name="${property}"]`)?.getAttribute("content");

describe("S1 A3 · A shared link previews the video", () => {
  // Case 1 · a chat app fetches /en/v/debate01 → the web app, noindex, title "Invented debate" and the YouTube thumbnail
  it("Case 1 · a chat app fetches /en/v/debate01 → the web app, noindex, title \"Invented debate\" and the YouTube thumbnail", async () => {
    const fetchPage = await chatApp();
    const { res, doc } = await fetchPage("/en/v/debate01");
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toContain("text/html");
    expect(res.headers.get("X-Robots-Tag")).toBe("noindex");
    expect(meta(doc, "robots")).toBe("noindex");
    expect(doc.getElementById("app")).not.toBeNull();
    expect(doc.querySelector('script[type="module"][src^="/app/"]')).not.toBeNull();
    // The owner, 2026-11-22: tab titles say DeFacto.
    expect(doc.title).toBe("Invented debate · DeFacto");
    expect(meta(doc, "og:title")).toBe("Invented debate · DeFacto");
    expect(meta(doc, "og:site_name")).toBe("DeFacto");
    expect(meta(doc, "og:image")).toBe("https://i.ytimg.com/vi/debate01/hqdefault.jpg");
  });

  // Case 2 · a chat app fetches /en/v/pending1, which is not approved → the web app with the neutral share tags of its index.html
  it("Case 2 · a chat app fetches /en/v/pending1, which is not approved → the web app with the neutral share tags of its index.html", async () => {
    const fetchPage = await chatApp();
    const { res, doc } = await fetchPage("/en/v/pending1");
    expect(res.status).toBe(200);
    const neutral = new DOMParser().parseFromString(await readFile(APP, "utf8"), "text/html");
    expect(doc.getElementById("app")).not.toBeNull();
    expect(doc.title).toBe(neutral.title);
    expect(meta(doc, "og:title")).toBe(meta(neutral, "og:title"));
    expect(meta(doc, "og:title")).not.toBe("Pendiente");
    expect(meta(doc, "og:image")).toBe(meta(neutral, "og:image"));
  });

  // Case 3 · the title holds `"` and `<` → the share tags show it as text, and the page keeps one title, its tags and the app
  it("Case 3 · the title holds `\"` and `<` → the share tags show it as text, and the page keeps one title, its tags and the app", async () => {
    const fetchPage = await chatApp();
    const { res, html, doc } = await fetchPage("/en/v/quoted01");
    expect(res.status).toBe(200);
    expect(doc.title).toBe(`${QUOTED} · DeFacto`);
    expect(meta(doc, "og:title")).toBe(`${QUOTED} · DeFacto`);
    expect(meta(doc, "og:image")).toBe("https://i.ytimg.com/vi/quoted01/hqdefault.jpg");
    expect(doc.querySelectorAll("title").length).toBe(1);
    expect(doc.querySelector("b")).toBeNull();
    expect(html).not.toContain("<b>now");
    expect(doc.getElementById("app")).not.toBeNull();
    expect(doc.querySelector('script[type="module"][src^="/app/"]')).not.toBeNull();
  });
});

// Inline 2026-11-22 · An approved video with no title keeps the neutral share tags, never the word "null"
describe("An approved video with no title keeps the neutral share tags", () => {
  it("title null → the neutral title of index.html", async () => {
    const { send, env } = await apiCollector();
    env.ASSETS = assets;
    await send("/analyses/untitled?lang=en", {
      method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer admin-secret" },
      body: JSON.stringify({ install_id: "00000000-0000-4000-8000-000000000000", analysis: { ...debateEn, video_id: "untitled", title: null } }),
    });
    const doc = new DOMParser().parseFromString(await (await send("/en/v/untitled")).text(), "text/html");
    const neutral = new DOMParser().parseFromString(await readFile(APP, "utf8"), "text/html");
    expect(doc.title).toBe(neutral.title);
    expect(meta(doc, "og:title")).toBe(meta(neutral, "og:title"));
  });
});

// Inline 2026-11-22 · A shared link shows the clean title: no live tag, no shouting (owner)
describe("A shared link shows the clean title", () => {
  it("«🔴 DIRECTO | DEBATE ELECTORAL en RTVE» → «Debate electoral en RTVE · DeFacto»", async () => {
    const { send, env } = await apiCollector();
    env.ASSETS = assets;
    await send("/analyses/livetag1?lang=en", {
      method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer admin-secret" },
      body: JSON.stringify({ install_id: "00000000-0000-4000-8000-000000000000", analysis: { ...debateEn, video_id: "livetag1", title: "🔴 DIRECTO | DEBATE ELECTORAL en RTVE" } }),
    });
    const doc = new DOMParser().parseFromString(await (await send("/en/v/livetag1")).text(), "text/html");
    expect(doc.title).toBe("Debate electoral en RTVE · DeFacto");
    expect(meta(doc, "og:title")).toBe("Debate electoral en RTVE · DeFacto");
  });
});
