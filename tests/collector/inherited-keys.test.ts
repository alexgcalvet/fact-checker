// Inline 2026-11-22 · A field name that every object inherits is not an allowed field
//
// Story: A stranger uploads an analysis with an extra field `constructor`, which every JavaScript object inherits, and
// one with `__proto__`. Both get 400, like any unknown field, and nothing waits for review. A feedback item of kind
// `constructor` gets 400 too, not a crash.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts), called directly with Requests.
import { describe, expect, it } from "vitest";
import { apiCollector, pendingEs } from "../support/api_fakes";

const STRANGER = "44444444-4444-4444-8444-444444444444";

describe("A field name that every object inherits is not an allowed field", () => {
  it("Case 1 · an upload with `constructor` or `__proto__` → 400, nothing pending", async () => {
    const { send, env } = await apiCollector();
    const before = env.DB.rows("SELECT COUNT(*) AS n FROM pending")[0].n;
    for (const extra of ['"constructor": "texto inventado"', '"__proto__": {}']) {
      const analysis = JSON.stringify({ ...pendingEs, video_id: "newvideo" }).replace(/^\{/, `{${extra}, `);
      const res = await send("/analyses/newvideo?lang=es", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: `{"install_id": "${STRANGER}", "analysis": ${analysis}}`,
      });
      expect(res.status, extra).toBe(400);
    }
    expect(env.DB.rows("SELECT COUNT(*) AS n FROM pending")[0].n).toBe(before);
  });

  it("Case 2 · feedback of kind `constructor`, or with a `toString` field → 400", async () => {
    const { send } = await apiCollector();
    for (const body of [{ kind: "constructor", text: "x", install_id: STRANGER },
      { kind: "flag", toString: "x", video_id: "debate01", flag_id: "false-1.0", text: "x", install_id: STRANGER }]) {
      const res = await send("/api/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      expect(res.status, JSON.stringify(body)).toBe(400);
    }
  });
});
