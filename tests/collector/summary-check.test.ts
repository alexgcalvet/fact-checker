// Inline 2026-11-22 · A guest's tally counts only flags the upload holds
//
// Story: A stranger uploads an analysis whose guest summary counts a "false · serious" flag that is not among its
// flags. The owner reads the flags on the review page and would never see it, but the public profile card would count
// it. The collector refuses such an upload (400), in the tally's flags and in its gravest list.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts), called directly with Requests;
// the invented debate upload with its guests' summary (docs/api-examples/summary-upload.json).
import { describe, expect, it } from "vitest";
import { apiCollector, debateEs } from "../support/api_fakes";

const STRANGER = "55555555-5555-4555-8555-555555555555";
const FORGED = { verdict: "false", severity: "serious", device: null, question: null };

describe("A guest's tally counts only flags the upload holds", () => {
  it("Case 1 · a tally flag or a gravest id with no flag in the upload → 400; the real summary → 202", async () => {
    const { send } = await apiCollector();
    const put = (summary: object) => send("/analyses/newvideo?lang=es", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ install_id: STRANGER, analysis: { ...debateEs, video_id: "newvideo", summary } }),
    });
    const ana = (debateEs as any).summary.Ana;
    expect((await put({ ...debateEs.summary, Ana: { ...ana, flags: { ...ana.flags, "false-99.0": FORGED } } })).status)
      .toBe(400);
    expect((await put({ ...debateEs.summary, Ana: { ...ana, gravest: ["false-99.0", ...ana.gravest] } })).status)
      .toBe(400);
    expect((await put(debateEs.summary)).status).toBe(202);
  });
});
