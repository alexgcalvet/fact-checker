// S2 A2 · One video comes in the asked language, or in the other one with a note
//
// Story: Anyone asks for the debate in English and gets its English title, channel, duration, date, type and guests,
// marked as English. They ask for the interview in English: it exists only in Spanish, so they get the Spanish one,
// marked as Spanish and as asked in English. A video that is unknown, or only pending, gives "not found". Both answers
// are the ones in the API examples.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts: the debate approved in es and en, the interview in es only, a third video pending.
import { describe, expect, it } from "vitest";
import { apiCollector, example } from "../support/api_fakes";

describe("S2 A2 · One video comes in the asked language, or in the other one with a note", () => {
  // Case 1 · the debate in English → its English fields, lang "en", no `requested`
  it("Case 1 · GET /api/videos/debate01?lang=en → the English debate, equal to docs/api-examples/debate.json", async () => {
    const { get } = await apiCollector();
    const res = await get("/api/videos/debate01?lang=en");
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body).toMatchObject({ video_id: "debate01", lang: "en", title: "Invented debate", type: "debate", duration: 3600 });
    expect(body).not.toHaveProperty("requested");
    expect(body).toEqual(await example("debate.json"));
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe("*");
  });

  // Case 2 · the interview in English, which exists only in Spanish → the Spanish one, lang "es", requested "en"
  it("Case 2 · GET /api/videos/intervw1?lang=en → the Spanish interview with requested en, equal to the example", async () => {
    const { get } = await apiCollector();
    const res = await get("/api/videos/intervw1?lang=en");
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body).toMatchObject({ video_id: "intervw1", lang: "es", requested: "en", title: "Entrevista inventada", guests: ["Pablo"] });
    expect(body).toEqual(await example("interview-en.json"));
  });

  // Case 3 · an unknown video, or one only pending → 404
  it("Case 3 · an unknown or only pending video → 404", async () => {
    const { get } = await apiCollector();
    expect((await get("/api/videos/unknown1?lang=es")).status).toBe(404);
    expect((await get("/api/videos/pending1?lang=es")).status).toBe(404);
  });
});
