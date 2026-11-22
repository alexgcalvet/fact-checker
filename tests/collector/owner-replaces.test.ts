// S4 A3 · The owner's upload replaces the stored analysis
//
// Story: The owner runs `fact-checker shared upload <video> es` for a video already approved, read by the same model.
// The collector keeps the new upload, with its summary and prompts, in place of the old one. A stranger's upload of
// that video by the same model is still refused.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts: the interview approved in es, read by opus, with helper version 0.1.0, no prompts file
// and no summary. The new upload is that interview by opus again, with the prompts version and file of
// docs/api-examples/prompts.json and a summary of Pablo.
import { describe, expect, it } from "vitest";
import { apiCollector, example, interviewEs } from "../support/api_fakes";

const OWNER = "00000000-0000-4000-8000-000000000000";
const STRANGER = "55555555-5555-4555-8555-555555555555";
const PABLO = {
  checked: 6, asked: 2, gravest: ["false-1.0"],
  flags: { "false-1.0": { verdict: "false", severity: "serious", device: null, question: null } },
};
const put = (send: any, body: object, admin: boolean) => send("/analyses/intervw1?lang=es", {
  method: "PUT",
  headers: { "Content-Type": "application/json", ...(admin ? { Authorization: "Bearer admin-secret" } : {}) },
  body: JSON.stringify(body),
});

describe("S4 A3 · The owner's upload replaces the stored analysis", () => {
  // Case 1 · the owner uploads the approved interview again, same model → 200; the API serves its summary and prompts
  it("Case 1 · the owner's upload by the same model → 200, the API gives the new summary and prompts version", async () => {
    const { get, send } = await apiCollector();
    const prompts = await example("prompts.json");
    const analysis = { ...interviewEs, helper_version: prompts.version, summary: { Pablo: PABLO } };
    const res = await put(send, { install_id: OWNER, analysis, prompts }, true);
    expect(res.status).toBe(200);
    const body = (await (await get("/api/videos/intervw1?lang=es")).json()) as any;
    expect(body.prompts).toBe(prompts.version);
    expect(body.summary.Pablo).toMatchObject({ checked: 6, verdicts: { false: 1, correct: 5 }, gravest: ["false-1.0"] });
    expect((await get(`/api/prompts/${encodeURIComponent(prompts.version)}`)).status).toBe(200);
  });

  // Case 2 · the owner uploads it again read by a worse model (sonnet) → 200; the owner is the review
  it("Case 2 · the owner's upload by a worse model → 200, the API gives its summary", async () => {
    const { get, send } = await apiCollector();
    const readers = { ...interviewEs.readers, parts: { provider: "claude", model: "sonnet" } };
    const analysis = { ...interviewEs, readers, summary: { Pablo: PABLO } };
    expect((await put(send, { install_id: OWNER, analysis }, true)).status).toBe(200);
    const body = (await (await get("/api/videos/intervw1?lang=es")).json()) as any;
    expect(body.summary.Pablo).toMatchObject({ checked: 6, asked: 2 });
  });

  // Case 3 · a stranger uploads the same interview by the same model → 409, the stored one stays
  it("Case 3 · a stranger's upload by the same model → 409, the API still gives no summary", async () => {
    const { get, send } = await apiCollector();
    const analysis = { ...interviewEs, summary: { Pablo: PABLO } };
    expect((await put(send, { install_id: STRANGER, analysis }, false)).status).toBe(409);
    const body = (await (await get("/api/videos/intervw1?lang=es")).json()) as any;
    expect(body).toHaveProperty("summary", null);
    console.log("PASS S4 A3 · The owner's upload replaces the stored analysis");
  });
});
