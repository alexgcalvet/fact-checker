// S4 A2 · The video call shows each guest's summary
//
// Story: Anyone asks the API for the invented debate in Spanish and gets a summary for Ana and one for Luis: checked,
// the verdicts, the severities, the devices with their counts, dodged, partial, asked, and the ids of the two gravest
// flags. The answer is the one in the API examples. The interview, uploaded before summaries existed, gives no summary.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts: the debate approved in es and en, each upload with the summary of
// docs/api-examples/summary-upload.json; the interview approved in es with no summary.
import { describe, expect, it } from "vitest";
import { apiCollector, example } from "../support/api_fakes";

describe("S4 A2 · The video call shows each guest's summary", () => {
  // Case 1 · the debate in Spanish → a summary for Ana and for Luis, equal to the one of docs/api-examples/debate.json
  it("Case 1 · GET /api/videos/debate01?lang=es → the summary of Ana and Luis, equal to the example", async () => {
    const { get } = await apiCollector();
    const body = (await (await get("/api/videos/debate01?lang=es")).json()) as any;
    expect(body.guests).toEqual(["Ana", "Luis"]);
    expect(Object.keys(body.summary)).toEqual(["Ana", "Luis"]);
    expect(body.summary.Ana).toEqual({
      checked: 10,
      verdicts: { false: 2, misleading: 1, nitpick: 1, correct: 6 },
      severity: { serious: 2, moderate: 1, minor: 2 },
      devices: [{ label: "ad_hominem", count: 2 }],
      dodged: 0,
      partial: 0,
      asked: 4,
      gravest: ["false-1.0", "ad_hominem-11.0"],
    });
    expect(body.summary.Luis).toMatchObject({
      checked: 8,
      verdicts: { false: 1, misleading: 2, nitpick: 1, correct: 4 },
      gravest: ["misleading-8.0", "ad_hominem-4.0"],
    });
    expect(body.summary).toEqual((await example("debate.json")).summary);
  });

  // Case 2 · the interview, uploaded with no summary → summary null
  it("Case 2 · GET /api/videos/intervw1?lang=es → summary null", async () => {
    const { get } = await apiCollector();
    const body = (await (await get("/api/videos/intervw1?lang=es")).json()) as any;
    expect(body).toHaveProperty("summary", null);
    console.log("PASS S4 A2 · The video call shows each guest's summary");
  });
});
