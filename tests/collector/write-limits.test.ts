// Inline 2026-11-22 · Free ids cannot flood the collector
//
// Story: Anyone can make install ids and web ids for free. One address sends writes in a loop: past 30 in a minute it
// gets 429, and another address still gets in. Marks sent with a new id each time stop for everyone at 5,000 a UTC
// day, whatever helper version they say. Strangers' uploads stop once 200 wait for review, so the database cannot fill.
//
// Setup: the collector Worker's fetch handler, called directly with a Request; the D1 fake (tests/support/d1_fake.ts);
// a rate limit fake that lets 30 calls in per key (tests/support/limit_fake.ts), or every call. No wrangler, no network.
import { describe, expect, it } from "vitest";
import worker from "../../src/collector/src/index";
import { fakeD1 } from "../support/d1_fake";
import { fakeLimit } from "../support/limit_fake";

const ORIGIN = "https://collector.example";
const id = (n: number) => `${n.toString(16).padStart(8, "0")}-1111-4111-8111-111111111111`;
const mark = (i: number) => ({
  video_id: "abcdefgh", flag_id: `a-${i}.0`, t: 42, type: "fallacy", label: "ad_hominem", quote: "usted no sabe nada",
  confidence: 0.85, verdict: "unfair", reason: "no", provider: "claude", model: "opus",
});
const analysis = (video: string) => ({
  video_id: video, lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Vídeo inventado",
  channel: "Canal", duration: 60, analysed_until: 60, helper_version: "0.1.0", speakers: {},
  readers: { parts: { provider: "claude", model: "opus" } }, cost_usd: 0.1, flags: [],
});

function collector(max = Infinity) {
  const env = { DB: fakeD1(), ADMIN_TOKEN: "admin-secret", WRITES: fakeLimit(max) } as any;
  const marks = (installId: string, sent: object[], ip = "203.0.113.1", version = "0.1.0") =>
    worker.fetch(new Request(`${ORIGIN}/marks`, {
      method: "POST", headers: { "Content-Type": "application/json", "CF-Connecting-IP": ip },
      body: JSON.stringify({ install_id: installId, helper_version: version, marks: sent }),
    }), env);
  const upload = (installId: string, video: string) =>
    worker.fetch(new Request(`${ORIGIN}/analyses/${video}?lang=es`, {
      method: "PUT", headers: { "Content-Type": "application/json", "CF-Connecting-IP": `198.51.100.${installId.length}` },
      body: JSON.stringify({ install_id: installId, analysis: analysis(video) }),
    }), env);
  return { marks, upload };
}

describe("Free ids cannot flood the collector", () => {
  it("Case 1 · the 31st write of one address in a minute → 429; another address still gets in", async () => {
    const { marks } = collector(30);
    for (let i = 0; i < 30; i++) expect((await marks(id(i), [mark(i)])).status).toBe(200);
    expect((await marks(id(99), [mark(99)])).status).toBe(429);
    expect((await marks(id(99), [mark(99)], "203.0.113.2")).status).toBe(200);
  });

  it("Case 2 · marks from new ids, any helper version → all stop at 5,000 a day", async () => {
    const { marks } = collector();
    const batch = (start: number) => Array.from({ length: 500 }, (_, i) => mark(start + i));
    for (let n = 0; n < 10; n++) expect((await marks(id(n), batch(n * 500), "203.0.113.1", "x")).status).toBe(200);
    expect((await marks(id(10), [mark(9999)], "203.0.113.1", "x")).status).toBe(429);
  });

  it("Case 3 · 200 strangers' uploads wait for review → the 201st gets 429; a waiting one can still be sent again", async () => {
    const { upload } = collector();
    for (let n = 0; n < 200; n++) expect((await upload(id(n), `video${String(n).padStart(3, "0")}`)).status).toBe(202);
    expect((await upload(id(500), "video999")).status).toBe(429);
    expect((await upload(id(0), "video000")).status).toBe(202);
  });
});
