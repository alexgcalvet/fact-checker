// S1 A3 · The owner opens an upload, reads its flags, and approves or rejects it from the page
//
// Story: The owner opens the debate's row and reads its 12 flags: second, type, label, quote, reason and severity.
// They press Approve: the debate leaves the list, and anyone who asks the collector for it gets the upload they
// opened, never another one. Reject on the interview deletes it and serves nothing.
//
// Setup: the collector Worker's fetch handler, called directly with a Request, through the routes that the review page
// calls (the page itself is checked in A4); the D1 fake (tests/support/d1_fake.ts); the invented TEAM_DOMAIN and
// POLICY_AUD, and a stubbed global fetch that serves the fake Access key set (tests/support/access_fake.ts). Three
// strangers PUT uploads: the Opus debate, an older Sonnet upload of the same debate, and an interview. No wrangler, no
// network.
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import worker from "../../src/collector/src/index";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { fakeD1 } from "../support/d1_fake";
import { fakeLimit } from "../support/limit_fake";

const ORIGIN = "https://collector.example";
const DEBATER = "11111111-1111-4111-8111-111111111111";
const EARLIER = "22222222-2222-4222-8222-222222222222";
const INTERVIEWER = "33333333-3333-4333-8333-333333333333";

const SEVERITIES = ["serious", "moderate", "minor"] as const;
const flag = (i: number) => ({
  id: `false-${i}.0`, t: i * 30, speaker: i % 2 ? "Ana" : "Luis", quote: `cifra inventada ${i}`, type: "inaccuracy",
  label: "false", reason: `Motivo inventado ${i}.`, confidence: 0.8, related: null, sources: [],
  judge: { verdict: "keep", reason: "Se sostiene.", severity: SEVERITIES[i % 3] },
});
const reader = (model: string) => ({ provider: "claude", model });
const upload = (video: string, parts: string, flags: object[]) => ({
  video_id: video, lang: "es", spoken: "es", status: "done", published_at: "2026-11-10", title: "Vídeo inventado",
  channel: "Canal", duration: 3600, analysed_until: 3600, helper_version: "0.1.0",
  speakers: { SPEAKER_00: "Ana", SPEAKER_01: "Luis" },
  people: { Ana: { role: "guest" }, Luis: { role: "guest" } },
  readers: { parts: reader(parts), verdict: reader("sonnet") }, cost_usd: 0.84, flags,
});
const debate = upload("debate01", "opus", Array.from({ length: 12 }, (_, i) => flag(i + 1)));
const older = upload("debate01", "sonnet", [flag(1)]);
const interview = { ...upload("intervw1", "sonnet", [flag(1), flag(2)]), people: { Ana: { role: "guest" } } };

const keys = certsFetch();
beforeAll(() => vi.stubGlobal("fetch", keys.fetch));
afterAll(() => vi.unstubAllGlobals());

async function collector() {
  const env = { DB: fakeD1(), WRITES: fakeLimit(), ADMIN_TOKEN: "admin-secret", TEAM_DOMAIN, POLICY_AUD } as any;
  const call = (path: string, headers: Record<string, string> = {}, method = "GET") =>
    worker.fetch(new Request(`${ORIGIN}${path}`, { method, headers }), env);
  for (const [installId, analysis] of [[EARLIER, older], [DEBATER, debate], [INTERVIEWER, interview]] as const) {
    const res = await worker.fetch(new Request(`${ORIGIN}/analyses/${analysis.video_id}?lang=es`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ install_id: installId, analysis }),
    }), env);
    expect(res.status).toBe(202);
  }
  const owner = async () => ({ [HEADER]: await token() });
  const rows = async () =>
    (((await (await call("/admin/pending", await owner())).json()) as any).rows as Row[]);
  // A row of the list names one upload: its uploader and the time it came.
  const row = async (video: string, install = video === "debate01" ? DEBATER : INTERVIEWER) =>
    (await rows()).find((r) => r.video_id === video && r.install_id === install) ??
      { video_id: video, install_id: install, received_at: "gone" };
  const which = (r: Row) => `lang=es&install=${r.install_id}&at=${encodeURIComponent(r.received_at)}`;
  const open = async (r: Row) => call(`/admin/pending/${r.video_id}?${which(r)}`, await owner());
  const review = async (r: Row, action: "approve" | "reject") =>
    call(`/admin/pending/${r.video_id}/${action}?${which(r)}`, await owner(), "POST");
  const listed = async () => (await rows()).map((r) => r.video_id);
  const served = (video: string) => call(`/analyses/${video}?lang=es`);
  const put = (installId: string, analysis: object) => worker.fetch(new Request(`${ORIGIN}/analyses/debate01?lang=es`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ install_id: installId, analysis }),
  }), env);
  return { open, review, listed, served, row, put };
}

type Row = { video_id: string; install_id: string; received_at: string };

describe("S1 A3 · The owner opens an upload, reads its flags, and approves or rejects it from the page", () => {
  // Case 1 · open the debate → the upload that approve would serve: the Opus one, with its 12 flags in full
  it("Case 1 · open the debate → the Opus upload with 12 flags: second, type, label, quote, reason, severity", async () => {
    const { open, row } = await collector();
    const res = await open(await row("debate01"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body).toEqual(debate);
    expect(body.flags).toHaveLength(12);
    expect(body.flags[0]).toMatchObject({
      t: 30, type: "inaccuracy", label: "false", quote: "cifra inventada 1", reason: "Motivo inventado 1.",
      judge: { severity: "moderate" },
    });
  });

  // Case 2 · approve the debate → it leaves the list, and anyone gets the opened upload from the collector
  it("Case 2 · approve → 200; the debate leaves the list; GET /analyses/debate01 serves what was opened", async () => {
    const { open, review, listed, served, row } = await collector();
    const debateRow = await row("debate01");
    const opened = await (await open(debateRow)).json();
    expect((await served("debate01")).status).toBe(404);
    expect((await review(debateRow, "approve")).status).toBe(200);
    expect(await listed()).toEqual(["intervw1"]);
    const res = await served("debate01");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(opened);
  });

  // Case 3 · reject the interview → deleted: not listed, not served, nothing left to open or approve
  it("Case 3 · reject → 200; the interview is not listed, not served, and opening it gives 404", async () => {
    const { open, review, listed, served, row } = await collector();
    const interviewRow = await row("intervw1");
    expect((await review(interviewRow, "reject")).status).toBe(200);
    const left = await listed();
    expect(left).not.toContain("intervw1");
    expect(left).toContain("debate01");
    expect((await served("intervw1")).status).toBe(404);
    expect((await open(interviewRow)).status).toBe(404);
    expect((await review(interviewRow, "approve")).status).toBe(409);
  });

  // Case 4 · the owner opens the older Sonnet row → that upload, not the Opus one
  it("Case 4 · open the Sonnet row of the debate → the Sonnet upload with its 1 flag", async () => {
    const { open, row } = await collector();
    expect(await (await open(await row("debate01", EARLIER))).json()).toEqual(older);
  });

  // Case 5 · while the owner reads the Sonnet row, a stranger uploads the same debate as "opus" → approve serves the
  // Sonnet upload that was opened; a stranger who replaces the opened upload itself makes approve answer 409
  it("Case 5 · a later upload never goes public in place of the opened one", async () => {
    const { open, review, served, row, put } = await collector();
    const sonnetRow = await row("debate01", EARLIER);
    await open(sonnetRow);
    const forged = { ...debate, flags: [{ ...flag(1), quote: "texto inventado por un extraño" }] };
    expect((await put("44444444-4444-4444-8444-444444444444", forged)).status).toBe(202);
    expect((await review(sonnetRow, "approve")).status).toBe(200);
    expect(await (await served("debate01")).json()).toEqual(older);

    const { review: review2, row: row2, put: put2, served: served2 } = await collector();
    const opusRow = await row2("debate01");
    await new Promise((done) => setTimeout(done, 5));
    expect((await put2(DEBATER, forged)).status).toBe(202);
    expect((await review2(opusRow, "approve")).status).toBe(409);
    expect((await served2("debate01")).status).toBe(404);
  });
});
