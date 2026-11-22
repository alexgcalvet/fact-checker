// S2 A3 · The flags come in order with a cursor, and the cursor gives nothing new
//
// Story: Anyone asks for the flags of the debate in Spanish and gets its 12 flags in the order of their second, a
// cursor, and "not live". They ask again with that cursor and get no flag and the same cursor. The first answer is the
// one in the API examples.
// Edge case: WHEN the cursor is not one that the API gave THEN the answer is "bad cursor" (400), never every flag again.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts. The debate's 12 Spanish flags are stored out of order of their second.
import { describe, expect, it } from "vitest";
import { apiCollector, debateEs, example } from "../support/api_fakes";

describe("S2 A3 · The flags come in order with a cursor, and the cursor gives nothing new", () => {
  // Case 1 · no cursor → the 12 flags ordered by second, a cursor, live false; equal to the example
  it("Case 1 · GET /api/videos/debate01/flags?lang=es → 12 flags by second, a cursor, live false", async () => {
    const { get } = await apiCollector();
    const res = await get("/api/videos/debate01/flags?lang=es");
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body.flags).toHaveLength(12);
    const seconds = body.flags.map((f: any) => f.t);
    expect(seconds).toEqual([...debateEs.flags.map((f: any) => f.t)].sort((a, b) => a - b));
    expect(typeof body.cursor).toBe("string");
    expect(body.live).toBe(false);
    expect(body).toEqual(await example("debate-flags.json"));
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe("*");
  });

  // Case 2 · again with that cursor → no flag, the same cursor
  it("Case 2 · the returned cursor → no flag and the same cursor", async () => {
    const { get } = await apiCollector();
    const first = (await (await get("/api/videos/debate01/flags?lang=es")).json()) as any;
    const res = await get(`/api/videos/debate01/flags?lang=es&after=${encodeURIComponent(first.cursor)}`);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ flags: [], cursor: first.cursor, live: false });
  });

  // Case 3 · a cursor the API never gave → 400
  it("Case 3 · a made-up cursor → 400 bad cursor", async () => {
    const { get } = await apiCollector();
    for (const after of ["nonsense", "-1", "999"]) {
      expect((await get(`/api/videos/debate01/flags?lang=es&after=${after}`)).status, after).toBe(400);
    }
  });

  // Case 4 · a language with no analysis, or a pending video → 404
  it("Case 4 · the interview in English, or the pending video → 404", async () => {
    const { get } = await apiCollector();
    expect((await get("/api/videos/intervw1/flags?lang=en")).status).toBe(404);
    expect((await get("/api/videos/pending1/flags?lang=es")).status).toBe(404);
  });
});
