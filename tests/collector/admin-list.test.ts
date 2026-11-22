// S1 A2 · The review list shows models per role, cost, type, flags and serious flags
//
// Story: A tester uploads a debate whose parts were read by Opus and verdicts by Sonnet, cost 0.84 $, with 12 flags of
// which 3 are serious; another tester uploads an interview. The owner opens the review page and sees two rows:
// "debate · parts opus, verdict sonnet · 0.84 $ · 12 flags · 3 serious" and the interview with its own numbers. The
// owner's helper gets the same fields from /analyses.
//
// Setup: the collector Worker's fetch handler, called directly with a Request; the D1 fake (tests/support/d1_fake.ts);
// the invented TEAM_DOMAIN and POLICY_AUD, and a stubbed global fetch that serves the fake Access key set
// (tests/support/access_fake.ts). Two strangers PUT their uploads, so both wait in `pending`. The debate has two
// guests and a host in `people`; its 12 flags hold 3 kept flags with severity "serious" and one nitpick that the
// judge also rated "serious" (not counted, as on the extension's card title). The interview has one guest. No
// wrangler, no network.
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import worker from "../../src/collector/src/index";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { fakeD1 } from "../support/d1_fake";
import { fakeLimit } from "../support/limit_fake";

const ORIGIN = "https://collector.example";
const DEBATER = "11111111-1111-4111-8111-111111111111";
const INTERVIEWER = "22222222-2222-4222-8222-222222222222";

type Judge = { verdict: "keep" | "nitpick"; severity?: "minor" | "moderate" | "serious" };
const flag = (i: number, speaker: string, judge: Judge | null) => ({
  id: `false-${i}.0`, t: i * 10, speaker, quote: `cifra inventada ${i}`, type: "inaccuracy", label: "false",
  reason: "Motivo inventado.", confidence: 0.8, related: null, sources: [],
  ...(judge ? { judge: { reason: "Se sostiene.", ...judge } } : {}),
});
const reader = (model: string) => ({ provider: "claude", model });
const upload = (video: string, extra: object) => ({
  video_id: video, lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Vídeo inventado",
  channel: "Canal", duration: 3600, analysed_until: 3600, helper_version: "0.1.0", ...extra,
});

// 12 flags: 3 serious, 1 nitpick rated serious, 4 moderate, 2 minor, 2 not judged.
const debateFlags = [
  ...[1, 2, 3].map((i) => flag(i, "Ana", { verdict: "keep", severity: "serious" })),
  flag(4, "Luis", { verdict: "nitpick", severity: "serious" }),
  ...[5, 6, 7, 8].map((i) => flag(i, "Luis", { verdict: "keep", severity: "moderate" })),
  ...[9, 10].map((i) => flag(i, "Ana", { verdict: "keep", severity: "minor" })),
  ...[11, 12].map((i) => flag(i, "Luis", null)),
];
const debate = upload("debate01", {
  speakers: { SPEAKER_00: "Ana", SPEAKER_01: "Luis", SPEAKER_02: "Marta" },
  people: { Ana: { role: "guest" }, Luis: { role: "guest" }, Marta: { role: "host" } },
  readers: { parts: reader("opus"), verdict: reader("sonnet"), judge: reader("sonnet"), search: reader("sonnet") },
  cost_usd: 0.84, flags: debateFlags,
});
// 5 flags: 1 serious, 2 moderate, 1 nitpick, 1 not judged.
const interview = upload("intervw1", {
  speakers: { SPEAKER_00: "Pablo", SPEAKER_01: "Marta" },
  people: { Pablo: { role: "guest" }, Marta: { role: "host" } },
  readers: { parts: reader("sonnet"), verdict: reader("sonnet"), judge: reader("haiku"), search: reader("haiku") },
  cost_usd: 0.31,
  flags: [flag(1, "Pablo", { verdict: "keep", severity: "serious" }),
          flag(2, "Pablo", { verdict: "keep", severity: "moderate" }),
          flag(3, "Pablo", { verdict: "keep", severity: "moderate" }),
          flag(4, "Pablo", { verdict: "nitpick", severity: "minor" }), flag(5, "Pablo", null)],
});

const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

async function collector(uploads: [string, object][]) {
  const env = { DB: fakeD1(), WRITES: fakeLimit(), ADMIN_TOKEN: "admin-secret", TEAM_DOMAIN, POLICY_AUD } as any;
  for (const [installId, analysis] of uploads) {
    const a = analysis as { video_id: string };
    const res = await worker.fetch(new Request(`${ORIGIN}/analyses/${a.video_id}?lang=es`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ install_id: installId, analysis }),
    }), env);
    expect(res.status).toBe(202);
  }
  const rows = async (path: string, headers: Record<string, string>) => {
    const res = await worker.fetch(new Request(`${ORIGIN}${path}`, { headers }), env);
    expect(res.status).toBe(200);
    return ((await res.json()) as any).rows as Record<string, any>[];
  };
  return {
    page: async () => rows("/admin/pending", { [HEADER]: await token() }),
    helper: () => rows("/analyses", { Authorization: "Bearer admin-secret" }),
  };
}

const byVideo = (rows: Record<string, any>[], video: string) => rows.find((r) => r.video_id === video);

describe("S1 A2 · The review list shows models per role, cost, type, flags and serious flags", () => {
  // Case 1 · a debate and an interview pending → two rows with type, models per role, cost, flags and serious
  it("Case 1 · the page's list → the debate row and the interview row with their own numbers", async () => {
    const { page } = await collector([[DEBATER, debate], [INTERVIEWER, interview]]);
    const rows = await page();
    expect(rows).toHaveLength(2);
    expect(byVideo(rows, "debate01")).toMatchObject({
      lang: "es", type: "debate", cost_usd: 0.84, flags: 12, serious: 3, install_id: DEBATER,
      readers: { parts: { model: "opus" }, verdict: { model: "sonnet" } },
    });
    expect(byVideo(rows, "intervw1")).toMatchObject({
      lang: "es", type: "interview", cost_usd: 0.31, flags: 5, serious: 1, install_id: INTERVIEWER,
      readers: { parts: { model: "sonnet" }, verdict: { model: "sonnet" }, judge: { model: "haiku" } },
    });
  });

  // Case 2 · the owner's helper lists /analyses with the admin token → the same rows and fields
  it("Case 2 · GET /analyses with the admin token → the same rows as the page", async () => {
    const { page, helper } = await collector([[DEBATER, debate], [INTERVIEWER, interview]]);
    const fromHelper = await helper();
    const fromPage = await page();
    for (const video of ["debate01", "intervw1"]) {
      const row = byVideo(fromHelper, video)!;
      for (const field of ["readers", "cost_usd", "type", "flags", "serious", "model", "install_id", "received_at"]) {
        expect(row[field], `${video}.${field}`).toEqual(byVideo(fromPage, video)![field]);
      }
    }
  });

  // Case 3 · no `people` → the speakers count: two speakers make a debate, one an interview; no cost → null
  it("Case 3 · no people: two speakers → debate, one speaker → interview; no cost_usd → null", async () => {
    const two = upload("twospkrs", {
      speakers: { SPEAKER_00: "Ana", SPEAKER_01: "Luis" }, readers: { parts: reader("opus") },
      flags: [flag(1, "Ana", null), flag(2, "Luis", null)],
    });
    const one = upload("onespkr1", {
      speakers: { SPEAKER_00: "Ana" }, readers: { parts: reader("opus") }, flags: [flag(1, "Ana", null)],
    });
    const rows = await (await collector([[DEBATER, two], [INTERVIEWER, one]])).page();
    expect(byVideo(rows, "twospkrs")).toMatchObject({ type: "debate", flags: 2, serious: 0, cost_usd: null });
    expect(byVideo(rows, "onespkr1")).toMatchObject({ type: "interview", flags: 1, serious: 0, cost_usd: null });
  });
});
