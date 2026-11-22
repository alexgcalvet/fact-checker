// S5 A2 · A hidden flag never reaches another helper, also when hidden before approval
//
// Story: The owner hides a flag of a pending upload, then approves it. A helper that downloads the analysis gets every
// flag but that one. A flag hidden in an approved analysis also leaves the download.
//
// Setup: the collector Worker called directly, on the D1 fake, holding the invented videos of
// tests/support/api_fakes.ts: a stranger's pending upload `pending1` (es, 2 flags: false-1.0 and false-2.0) and the
// debate approved in es (12 flags, with the guests' summary). The owner hides, approves and re-uploads with the invented
// admin token of the fake; a helper downloads with GET /analyses/<id>?lang=es and no token.
import { describe, expect, it } from "vitest";
import { apiCollector, debateEs } from "../support/api_fakes";

const OWNER = { Authorization: "Bearer admin-secret" };

async function collector() {
  const c = await apiCollector();
  const hide = (video: string, id: string) =>
    c.send(`/analyses/${video}/flags/${id}/hide?lang=es`, { method: "POST", headers: OWNER });
  const download = async (video: string) => {
    const res = await c.send(`/analyses/${video}?lang=es`);
    expect(res.status).toBe(200);
    return (await res.json()) as any;
  };
  return { ...c, hide, download };
}

describe("S5 A2 · A hidden flag never reaches another helper, also when hidden before approval", () => {
  // Case 1 · hide a flag of the pending upload, then approve → the download and the flags call hold the other flag only
  it("Case 1 · hide false-2.0 while pending, approve → the download holds false-1.0 only", async () => {
    const { send, get, hide, download } = await collector();
    expect((await hide("pending1", "false-2.0")).status).toBe(200);
    const { rows } = (await (await send("/analyses", { headers: OWNER })).json()) as any;
    const which = new URLSearchParams({ lang: "es", install: rows[0].install_id, at: rows[0].received_at });
    expect((await send(`/analyses/pending1/approve?${which}`, { method: "POST", headers: OWNER })).status).toBe(200);
    expect((await download("pending1")).flags.map((f: any) => f.id)).toEqual(["false-1.0"]);
    const api = (await (await get("/api/videos/pending1/flags?lang=es")).json()) as any;
    expect(api.flags.map((f: any) => f.id)).toEqual(["false-1.0"]);
  });

  // Case 2 · hide a flag of the approved debate → the download has 11 flags, its summary drops it, the rest is unchanged
  it("Case 2 · hide false-1.0 of the approved debate → the download has 11 flags, none of them it", async () => {
    const { hide, download } = await collector();
    const before = await download("debate01");
    expect((await hide("debate01", "false-1.0")).status).toBe(200);
    const after = await download("debate01");
    expect(after.flags).toHaveLength(11);
    expect(after.flags.map((f: any) => f.id)).not.toContain("false-1.0");
    expect(after.flags).toEqual(before.flags.filter((f: any) => f.id !== "false-1.0"));
    expect(Object.keys(after.summary.Ana.flags)).not.toContain("false-1.0");
    expect(after.summary.Ana.gravest).not.toContain("false-1.0");
    expect(after.summary.Ana.checked).toBe(before.summary.Ana.checked);
    const { flags: _a, summary: _b, ...rest } = after;
    const { flags: _c, summary: _d, ...was } = before;
    expect(rest).toEqual(was);
  });

  // Case 3 · the owner uploads the same debate again → the hide still holds
  it("Case 3 · hide false-1.0, then the owner's re-upload → the download still lacks it", async () => {
    const { send, hide, download } = await collector();
    expect((await hide("debate01", "false-1.0")).status).toBe(200);
    const res = await send("/analyses/debate01?lang=es", {
      method: "PUT", headers: { "Content-Type": "application/json", ...OWNER },
      body: JSON.stringify({ install_id: "00000000-0000-4000-8000-000000000000", analysis: debateEs }),
    });
    expect(res.status).toBe(200);
    expect((await download("debate01")).flags.map((f: any) => f.id)).not.toContain("false-1.0");
    console.log("PASS S5 A2 · A hidden flag never reaches another helper, also when hidden before approval");
  });
});
