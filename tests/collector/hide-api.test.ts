// S5 A1 · A hidden flag leaves the public API and its guest's numbers
//
// Story: The owner hides the flag at second 1210 of the invented debate in Spanish, a misleading claim of Ana's. Anyone
// then gets 11 flags from the flags call, 11 in the list of videos, and Ana's summary shows one misleading claim less and
// one correct claim more, with the same claims checked; the hidden flag is not among her gravest. The owner shows it again
// and all of it comes back.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts: the debate approved in es and en (12 flags each, with the guests' summary of
// docs/api-examples/summary-upload.json). The flag at second 1210 is Ana's `misleading-3.0`; Case 4 hides a false
// claim, Ana's gravest. The
// owner hides and shows with the invented admin token of the fake. The list of videos shows the newest language (en),
// so the list case hides the flag in both languages.
import { describe, expect, it } from "vitest";
import SUMMARY from "../../docs/api-examples/summary-upload.json";
import { apiCollector, example } from "../support/api_fakes";

const OWNER = { Authorization: "Bearer admin-secret" };

async function collector() {
  const c = await apiCollector();
  const flags = async (lang = "es") => ((await (await c.get(`/api/videos/debate01/flags?lang=${lang}`)).json()) as any);
  const video = async (lang = "es") => ((await (await c.get(`/api/videos/debate01?lang=${lang}`)).json()) as any);
  const listed = async () =>
    (((await (await c.get("/api/videos")).json()) as any).videos as any[]).find((v) => v.video_id === "debate01");
  const owner = (id: string, action: "hide" | "show", lang = "es") =>
    c.send(`/analyses/debate01/flags/${id}/${action}?lang=${lang}`, { method: "POST", headers: OWNER });
  return { flags, video, listed, owner };
}

describe("S5 A1 · A hidden flag leaves the public API and its guest's numbers", () => {
  // Case 1 · hide the flag at second 1210 in es → the flags call gives 11 flags without it; the English one keeps 12
  it("Case 1 · hide the flag at 1210 → 11 flags in es, none of them it; en still 12", async () => {
    const { flags, owner } = await collector();
    const target = (await flags()).flags.find((f: any) => f.t === 1210);
    expect(target).toMatchObject({ id: "misleading-3.0", speaker: "Ana" });
    expect((await owner(target.id, "hide")).status).toBe(200);
    const after = await flags();
    expect(after.flags).toHaveLength(11);
    expect(after.flags.map((f: any) => f.id)).not.toContain(target.id);
    expect(after.cursor).toBe("11");
    expect((await flags("en")).flags).toHaveLength(12);
  });

  // Case 2 · the same hide → Ana: same checked, one claim less of the flag's verdict, one correct more; Luis as before
  it("Case 2 · hide the flag at 1210 → Ana's summary counts its claim as correct; Luis unchanged", async () => {
    const { video, owner } = await collector();
    const before = (await video()).summary;
    const { verdict, severity } = SUMMARY.Ana.flags["misleading-3.0"];
    expect((await owner("misleading-3.0", "hide")).status).toBe(200);
    const { summary } = await video();
    expect(summary.Ana.checked).toBe(before.Ana.checked);
    expect(summary.Ana.verdicts).toEqual({
      ...before.Ana.verdicts, [verdict]: before.Ana.verdicts[verdict] - 1, correct: before.Ana.verdicts.correct + 1,
    });
    expect(summary.Ana.severity).toEqual({ ...before.Ana.severity, [severity]: before.Ana.severity[severity] - 1 });
    expect(summary.Luis).toEqual(before.Luis);
  });

  // Case 3 · hide it in both languages → the list of videos counts 11 flags
  it("Case 3 · hide the flag in es and en → /api/videos lists the debate with 11 flags", async () => {
    const { listed, owner } = await collector();
    expect((await listed()).flags).toBe(12);
    expect((await owner("misleading-3.0", "hide", "es")).status).toBe(200);
    expect((await owner("misleading-3.0", "hide", "en")).status).toBe(200);
    expect((await listed()).flags).toBe(11);
  });

  // Case 4 · hide Ana's gravest flag, a false claim → it leaves her gravest, the next one moves up, one false claim less
  it("Case 4 · hide false-1.0 → Ana's gravest is ad_hominem-11.0 then false-5.0; false 1, correct 7", async () => {
    const { video, owner } = await collector();
    expect((await owner("false-1.0", "hide")).status).toBe(200);
    const { summary } = await video();
    expect(summary.Ana.gravest).toEqual(["ad_hominem-11.0", "false-5.0"]);
    expect(summary.Ana.verdicts).toEqual({ false: 1, misleading: 1, nitpick: 1, correct: 7 });
    expect(summary.Ana.checked).toBe(10);
  });

  // Case 5 · show both again → 12 flags, 12 in the list, and the summary of the API examples
  it("Case 5 · show again → 12 flags in es and in the list; the summary equals the example", async () => {
    const { flags, video, listed, owner } = await collector();
    for (const lang of ["es", "en"]) await owner("misleading-3.0", "hide", lang);
    await owner("false-1.0", "hide");
    for (const lang of ["es", "en"]) expect((await owner("misleading-3.0", "show", lang)).status).toBe(200);
    expect((await owner("false-1.0", "show")).status).toBe(200);
    expect((await flags()).flags).toHaveLength(12);
    expect((await listed()).flags).toBe(12);
    expect((await video()).summary).toEqual((await example("debate.json")).summary);
    console.log("PASS S5 A1 · A hidden flag leaves the public API and its guest's numbers");
  });
});
