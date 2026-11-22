// S2 A1 · The list shows each approved video once, and never a pending upload
//
// Story: The owner has approved an invented debate in Spanish and English and an invented interview in Spanish; a
// tester's upload of a third video waits for review. Anyone opens the list of videos and sees two entries: the debate
// with languages "es, en", type "debate", its two guests and 12 flags; the interview with "es", type "interview", one
// guest and 5 flags. The third video is not there. The answer is the one written in the API examples.
// Edge case: WHEN a web page on any other site reads the list from a browser THEN the browser allows it.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts: the owner's helper uploaded the debate (es, en) and the interview (es) with the admin
// token, a stranger uploaded a third video that stays pending. Each request carries the Origin of another site.
import { describe, expect, it } from "vitest";
import { apiCollector, example } from "../support/api_fakes";

describe("S2 A1 · The list shows each approved video once, and never a pending upload", () => {
  // Case 1 · two approved videos and one pending upload → two entries with their languages, type, guests and flags
  it("Case 1 · GET /api/videos → the debate and the interview, not the pending video", async () => {
    const { get } = await apiCollector();
    const res = await get("/api/videos");
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body.videos).toHaveLength(2);
    const debate = body.videos.find((v: any) => v.video_id === "debate01");
    const interview = body.videos.find((v: any) => v.video_id === "intervw1");
    expect([...debate.langs].sort()).toEqual(["en", "es"]);
    expect(debate).toMatchObject({ type: "debate", flags: 12, channel: "Invented Channel", duration: 3600, published_at: "2026-11-10" });
    expect([...debate.guests].sort()).toEqual(["Ana", "Luis"]);
    expect(interview).toMatchObject({ langs: ["es"], type: "interview", guests: ["Pablo"], flags: 5 });
    expect(body.videos.map((v: any) => v.video_id)).not.toContain("pending1");
  });

  // Case 2 · the same call → exactly the answer in docs/api-examples/videos.json
  it("Case 2 · GET /api/videos → equals docs/api-examples/videos.json", async () => {
    const { get } = await apiCollector();
    expect(await (await get("/api/videos")).json()).toEqual(await example("videos.json"));
  });

  // Case 3 · a browser on another site reads it → Access-Control-Allow-Origin: *
  it("Case 3 · a request from another origin → Access-Control-Allow-Origin: *", async () => {
    const { get } = await apiCollector();
    expect((await get("/api/videos")).headers.get("Access-Control-Allow-Origin")).toBe("*");
  });
});
