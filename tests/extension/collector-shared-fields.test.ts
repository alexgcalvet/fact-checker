// The collector takes every field that the helper shares: a field the helper adds and the Worker does not know makes
// every upload a silent 400 (S35 added people, claims and questions, and no analysis reached the collector).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import worker from "../../src/collector/src/index";
import { fakeD1 } from "../acceptance/s24_d1_fake";

const shared = readFileSync(new URL("../../src/helper/fact_checker/analyses.py", import.meta.url), "utf8")
  .match(/SHARED = \(([^)]*)\)/)![1].match(/"(\w+)"/g)!.map((f) => f.slice(1, -1));

const reader = { provider: "claude", model: "opus" };
const values: Record<string, unknown> = {
  video_id: "abcdefgh", lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Entrevista",
  channel: "Canal", duration: 23, speakers: { SPEAKER_00: "Ana Ruiz" }, people: { "Ana Ruiz": { role: "guest" } },
  claims: { "Ana Ruiz": 26 }, questions: { "Ana Ruiz": 11 }, readers: { parts: reader }, cost_usd: 7.9,
  analysed_until: 23, flags: [],
};

describe("collector · shared analysis fields", () => {
  it("takes an analysis with every field of the helper's SHARED", async () => {
    expect(shared.filter((f) => !(f in values))).toEqual([]);
    const analysis = Object.fromEntries(shared.map((f) => [f, values[f]]));
    const res = await worker.fetch(new Request("https://collector.example/analyses/abcdefgh?lang=es", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ install_id: "11111111-1111-4111-8111-111111111111",
                             analysis: { ...analysis, helper_version: "0.1.0" } }),
    }), { DB: fakeD1(), ADMIN_TOKEN: "admin-secret" } as any);
    expect(await res.json()).toEqual({ pending: true });
  });
});
