// The invented videos of the public API tests (S2), and a collector that holds them. No real name, quote or video id:
// docs/api-examples/ holds the API's answers to these same videos.
//   - debate01: a debate of two guests (Ana, Luis) and a host (Marta), approved in Spanish (12 flags) and in English
//     (12 flags), the English one received later. Its flags: false, misleading and ad hominem, two of them nitpicks.
//   - intervw1: an interview of one guest (Pablo) and a host (Marta), approved in Spanish only (5 flags).
//   - pending1: a tester's upload that waits for review.
// The debate uploads carry the guests' summary of docs/api-examples/summary-upload.json (S4); the interview has none.
// The debate uploads carry each person's speech and the voice turns (S5): Ana speaks 28:40 in 6 turns, Luis 24:50 in 5,
// Marta 5:50 in 5; the interview, uploaded before speaking time existed, has neither.
// The debate names the prompts version of docs/api-examples/prompts.json, and its Spanish upload carries that file (S7);
// the interview names the bare helper version 0.1.0 and has no prompts file.
// The owner's helper uploads with the admin token, so the debate and the interview are served at once; the stranger's
// upload stays pending. The flags are stored out of order of their second, as a helper may write them.
import worker from "../../src/collector/src/index";
import * as collectorModule from "../../src/collector/src/index";
import { fakeD1 } from "./d1_fake";
import { fakeLimit } from "./limit_fake";
import PROMPTS from "../../docs/api-examples/prompts.json";
import SUMMARY from "../../docs/api-examples/summary-upload.json";

export const ORIGIN = "https://collector.example";
const OWNER = "00000000-0000-4000-8000-000000000000";
const STRANGER = "33333333-3333-4333-8333-333333333333";

const reader = (model: string) => ({ provider: "claude", model });
const READERS = { parts: reader("opus"), verdict: reader("sonnet"), judge: reader("sonnet"), search: reader("sonnet") };
// The type, label, judge verdict and severity of the flags, in order; a debate gives the odd ones to Ana, the even
// ones to Luis. Every label has its rule in docs/api-examples/prompts.json.
const KINDS: [string, string, string, string | null][] = [
  ["inaccuracy", "false", "keep", "serious"], ["inaccuracy", "false", "keep", "moderate"],
  ["inaccuracy", "misleading", "keep", "minor"], ["fallacy", "ad_hominem", "keep", "serious"],
  ["inaccuracy", "false", "keep", "moderate"], ["inaccuracy", "false", "nitpick", null],
  ["fallacy", "ad_hominem", "keep", "minor"], ["inaccuracy", "misleading", "keep", "serious"],
  ["inaccuracy", "false", "nitpick", null], ["fallacy", "ad_hominem", "keep", "minor"],
  ["fallacy", "ad_hominem", "keep", "serious"], ["inaccuracy", "misleading", "keep", "minor"],
];
const flag = (i: number, t: number, speaker: string, quote: string) => {
  const [type, label, verdict, severity] = KINDS[i - 1];
  return {
    id: `${label}-${i}.0`, t, speaker, quote, type, label, reason: "Invented reason.", confidence: 0.8, related: null,
    sources: type === "inaccuracy" ? [{ publisher: "Invented Office", url: "https://example.org/data", date: "2026-10-01" }] : [],
    judge: { verdict, ...(severity ? { severity } : {}), reason: "Invented judge reason." },
  };
};
const SECONDS = [630, 75, 1210, 300, 45, 980, 1500, 210, 860, 1720, 420, 1100];
const flags = (n: number, speakers: string[], word: string) =>
  SECONDS.slice(0, n).map((t, i) => flag(i + 1, t, speakers[i % speakers.length], `${word} ${i + 1}`));

const video = (id: string, lang: string, extra: object) => ({
  video_id: id, lang, spoken: "es", status: "done", readers: READERS, cost_usd: 0.84, helper_version: "0.1.0", ...extra,
});
// The voice turns of the debate, as the helper uploads them: [start, end, person].
const TURNS: [number, number, string][] = [
  [0, 60, "Marta"], [60, 400, "Ana"], [410, 700, "Luis"], [700, 760, "Marta"], [760, 1000, "Ana"], [1000, 1300, "Luis"],
  [1310, 1600, "Ana"], [1600, 1700, "Marta"], [1700, 2000, "Luis"], [2000, 2300, "Ana"], [2310, 2610, "Luis"],
  [2620, 2900, "Ana"], [2900, 3000, "Marta"], [3000, 3300, "Luis"], [3300, 3570, "Ana"], [3570, 3600, "Marta"],
];
export const SPEECH = {
  people: {
    Ana: { role: "guest", spoken_s: 1720, turns: 6, longest_s: 340 },
    Luis: { role: "guest", spoken_s: 1490, turns: 5, longest_s: 300 },
    Marta: { role: "host", spoken_s: 350, turns: 5, longest_s: 100 },
  },
  turns: TURNS.map(([start, end, person]) => ({ start, end, person })),
};
const DEBATE = {
  published_at: "2026-11-10", duration: 3600, analysed_until: 3600, channel: "Invented Channel",
  speakers: { SPEAKER_00: "Ana", SPEAKER_01: "Luis", SPEAKER_02: "Marta" }, ...SPEECH,
  claims: { Ana: 10, Luis: 8 }, questions: { Ana: 4, Luis: 3 }, summary: SUMMARY,
};
export const debateEs = video("debate01", "es", { ...DEBATE, helper_version: PROMPTS.version, title: "Debate inventado", flags: flags(12, ["Ana", "Luis"], "cifra inventada") });
export const debateEn = video("debate01", "en", { ...DEBATE, helper_version: PROMPTS.version, title: "Invented debate", flags: flags(12, ["Ana", "Luis"], "invented figure") });
export const interviewEs = video("intervw1", "es", {
  published_at: "2026-11-05", duration: 1800, analysed_until: 1800, channel: "Invented Channel", title: "Entrevista inventada",
  speakers: { SPEAKER_00: "Pablo", SPEAKER_01: "Marta" },
  people: { Pablo: { role: "guest" }, Marta: { role: "host" } },
  flags: flags(5, ["Pablo"], "dato inventado"),
});
export const pendingEs = video("pending1", "es", {
  published_at: "2026-11-12", duration: 900, analysed_until: 900, channel: "Invented Channel", title: "Pendiente",
  speakers: { SPEAKER_00: "Eva" }, flags: flags(2, ["Eva"], "pendiente"),
});

// A fake execution context: ctx.exports.<Name> is the module's named entrypoint of that name, called with this env.
function context(env: object): any {
  const ctx: any = { waitUntil() {}, passThroughOnException() {}, props: {} };
  ctx.exports = new Proxy({}, {
    get: (_, name: string) => {
      const entry = (collectorModule as any)[name];
      const target = typeof entry === "function" ? new entry(ctx, env) : entry;
      return { fetch: (request: Request) => target.fetch(request, env, ctx) };
    },
  });
  return ctx;
}

// A collector with the three videos stored; `get` calls it like a browser on another site, `send` like the web app.
export async function apiCollector() {
  const env = { DB: fakeD1(), WRITES: fakeLimit(), ADMIN_TOKEN: "admin-secret", TEAM_DOMAIN: "", POLICY_AUD: "" } as any;
  const put = async (analysis: any, installId: string, admin: boolean, prompts?: object) => {
    const res = await worker.fetch(new Request(`${ORIGIN}/analyses/${analysis.video_id}?lang=${analysis.lang}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...(admin ? { Authorization: "Bearer admin-secret" } : {}) },
      body: JSON.stringify({ install_id: installId, analysis, ...(prompts ? { prompts } : {}) }),
    }), env, context(env));
    if (!(admin ? [200, 201] : [202]).includes(res.status)) throw new Error(`upload of ${analysis.video_id} ${analysis.lang}: ${res.status}`);
  };
  await put(debateEs, OWNER, true, PROMPTS);
  await put(interviewEs, OWNER, true);
  await put(debateEn, OWNER, true);
  await put(pendingEs, STRANGER, false);
  // The owner uploads an analysis again: it replaces the stored one at once.
  const owner = (analysis: any) => put(analysis, OWNER, true);
  const get = (path: string) =>
    worker.fetch(new Request(`${ORIGIN}${path}`, { headers: { Origin: "https://another-site.example" } }), env, context(env));
  // Any request of a page on the collector's own origin, as its `fetch` sends it.
  const send = (path: string, init?: RequestInit) => worker.fetch(new Request(`${ORIGIN}${path}`, init), env, context(env));
  return { get, send, env, owner };
}

// The answer stored in docs/api-examples/<name>.
export async function example(name: string) {
  const { readFile } = await import("node:fs/promises");
  return JSON.parse(await readFile(new URL(`../../docs/api-examples/${name}`, import.meta.url), "utf8"));
}
