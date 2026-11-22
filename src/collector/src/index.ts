// The feedback collector: a Cloudflare Worker that keeps the testers' marks and shared analyses in D1.
// POST /marks stores one tester's marks, or a web viewer's from the web app (helper version `web`); GET
// /marks?since=<iso> returns the rows received after that time, only to the owner (Authorization: Bearer <ADMIN_TOKEN>).
// PUT /analyses/<video_id>?lang= keeps a whole analysis: pending until the owner approves it, served at once when the
// owner uploads it, in place of any stored one. GET serves only approved analyses, to anyone. The owner lists the pending ones (GET /analyses),
// approves or rejects one (POST /analyses/<video_id>/approve|reject?lang=) and deletes a served one (DELETE). The
// owner hides one flag or shows it again (POST /analyses/<video_id>/flags/<flag_id>/hide|show?lang=): a hidden flag is
// never served and counts nowhere.
// The owner swaps the halves of a debate's thumbnail (POST /admin/videos/<video_id>/faces/swap|keep): the API's `swap`
// tells the web which half is each guest's face.
// /admin is the owner's review page (pending uploads, approved videos, the latest marks and feedback), and /admin/* its calls: behind
// Cloudflare Access, so they need the Access JWT, never ADMIN_TOKEN.
// /api/* is the public read API of the approved analyses, open to any origin. The default entrypoint hands it to the
// PublicApi entrypoint, the only one that Cloudflare caches (wrangler.toml), so no other route is ever cached.
// /try/<video_id>, the old test page, redirects to the viewer in the browser's language.
// / sends to /es/ or /en/ by the browser's language; /es/* and /en/* are the web app (web/app/, built from src/web/),
// never indexed; on /<lang>/v/<video_id> its share tags carry the title and thumbnail of that approved video, and the
// visit counts. POST /api/visits counts a jump to a flag's moment; /admin/visits sums both per video, language and day.
// POST /api/feedback keeps one item of feedback on the method from the web app; only the owner reads it, at
// GET /feedback?since=<iso> (ADMIN_TOKEN) and /admin/feedback. It is data: it never goes into a model's prompt.
import { createRemoteJWKSet, jwtVerify } from "jose";
import { countKinds, type Judged } from "../../shared/kinds";
import { cleanTitle } from "../../shared/titles";

// The part of the D1 binding that the collector uses (developers.cloudflare.com/d1/worker-api/).
interface D1Statement {
  bind(...values: unknown[]): D1Statement;
  first(): Promise<Record<string, unknown> | null>;
  all(): Promise<{ results: Record<string, unknown>[] }>;
  run(): Promise<unknown>;
}
interface Context {
  waitUntil(promise: Promise<unknown>): void;
  exports: { PublicApi: { fetch(r: Request): Promise<Response> } };
}
interface Env {
  DB: { prepare(sql: string): D1Statement; batch(statements: D1Statement[]): Promise<unknown> };
  ADMIN_TOKEN: string;
  TEAM_DOMAIN: string; // https://<team>.cloudflareaccess.com
  POLICY_AUD: string; // the AUD tag of the Access application
  ASSETS: { fetch(request: Request): Promise<Response> };
  WRITES: { limit(options: { key: string }): Promise<{ success: boolean }> }; // per address (wrangler.toml)
}

const MAX_BYTES = 256 * 1024;
const MAX_MARKS = 500;
const DAILY_REQUESTS = 20; // the hard stop per tester
// An install id or a web id costs nothing to make, so all marks share one stop per UTC day, counted in `requests` under
// the id `all`, which no install id matches.
const ALL = "all";
const DAILY_ALL_MARKS = 5000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const TYPES = ["fallacy", "bias", "contradiction", "inaccuracy", "question", "context"];
const VIDEO = /^[A-Za-z0-9_-]{6,20}$/;

const text = (max: number, min = 0) => (v: unknown) => typeof v === "string" && v.length >= min && v.length <= max;
const orNull = (check: (v: unknown) => boolean) => (v: unknown) => v === null || check(v);
const object = (v: unknown) => !!v && typeof v === "object" && !Array.isArray(v);
const number = (lo: number, hi: number) => (v: unknown) => typeof v === "number" && Number.isFinite(v) && v >= lo && v <= hi;

// Each field of a sent mark and its check. A mark with any other field is refused.
const MARK: Record<string, (v: unknown) => boolean> = {
  video_id: (v) => typeof v === "string" && VIDEO.test(v),
  flag_id: text(100, 1),
  t: number(0, 1e6),
  type: (v) => TYPES.includes(v as string),
  label: (v) => typeof v === "string" && /^[a-z_]{1,40}$/.test(v),
  quote: text(1000, 1),
  confidence: number(0, 1),
  verdict: (v) => v === "correct" || v === "unfair",
  reason: text(500),
  provider: orNull(text(40, 1)),
  model: orNull(text(100, 1)),
};
const FIELDS = Object.keys(MARK);

const MAX_ANALYSIS_BYTES = 1024 * 1024; // D1 allows 2,000,000 bytes per row
const MAX_FLAGS = 1000;
const DAILY_UPLOADS = 10; // the hard stop per tester
const MAX_PENDING = 200; // strangers' uploads that wait for review
// The parts model of a stored analysis ranks it: a later upload replaces it only from a higher rank. Any other model
// ranks under these.
const RANK = ["haiku", "sonnet", "opus"];
// S4: what each flag of a guest adds to the profile card, as the helper's summary.tally writes it; the video call sums
// the flags. `gravest` lists the candidates in order.
const oneOf = (...values: string[]) => orNull((v) => values.includes(v as string));
const TALLY_FLAG = (f: any) => object(f) && keys(f, ["verdict", "severity", "device", "question"]) &&
  oneOf("false", "misleading", "nitpick")(f.verdict) && oneOf("serious", "moderate", "minor")(f.severity) &&
  orNull((v) => typeof v === "string" && /^[a-z_]{1,40}$/.test(v))(f.device) && oneOf("dodged", "partial")(f.question);
const TALLY = (t: any) => object(t) && keys(t, ["checked", "asked", "flags", "gravest"]) &&
  number(0, 1e6)(t.checked) && number(0, 1e6)(t.asked) && object(t.flags) &&
  Object.keys(t.flags).length <= MAX_FLAGS && Object.values(t.flags).every(TALLY_FLAG) &&
  Array.isArray(t.gravest) && t.gravest.length <= MAX_FLAGS && t.gravest.every(text(100, 1));
// S5: the voice turns of the whole video by person, as the helper's speakers.merged writes them.
const MAX_TURNS = 5000;
const TURN = (t: any) => object(t) && keys(t, ["start", "end", "person"]) && number(0, 1e6)(t.start) && number(0, 1e6)(t.end) &&
  text(200, 1)(t.person);
const ANALYSIS: Record<string, (v: unknown) => boolean> = {
  video_id: (v) => typeof v === "string" && VIDEO.test(v),
  lang: (v) => v === "es" || v === "en",
  spoken: (v) => v === "es" || v === "en",
  status: (v) => v === "done",
  published_at: orNull(text(40)),
  title: orNull(text(500)),
  channel: orNull(text(200)),
  duration: orNull(number(0, 1e6)),
  speakers: object,
  people: orNull(object),
  claims: orNull(object),
  questions: orNull(object),
  readers: (v: any) => !!v && typeof v === "object" && !!v.parts && orNull(text(100, 1))(v.parts.model),
  cost_usd: orNull(number(0, 1e6)),
  analysed_until: number(0, 1e6),
  helper_version: text(40, 1),
  flags: Array.isArray,
  turns: (v) => Array.isArray(v) && v.length <= MAX_TURNS && v.every(TURN),
  summary: orNull((v) => object(v) && Object.keys(v as object).length <= 20 &&
    Object.entries(v as object).every(([name, t]) => text(200, 1)(name) && TALLY(t))),
};
const REQUIRED = ["video_id", "lang", "status", "readers", "helper_version", "flags"];
// S7: the prompts file of the helper version, sent with an upload. Its version is the helper version, then "+" and the
// first 12 hex digits of the SHA-256 of JSON.stringify(components): the hash that the helper computes in prompts.py.
const PROMPTS_VERSION = /^[0-9A-Za-z.]{1,27}\+([0-9a-f]{12})$/;
const ID = (v: unknown) => typeof v === "string" && /^[a-z_]{1,40}$/.test(v);
const RULE = (r: any) => object(r) && keys(r, ["id", "text"]) && ID(r.id) && text(5000, 1)(r.text);
const COMPONENT = (c: any) => object(c) && keys(c, ["id", "role", "text", "rules"]) && ID(c.id) && text(40, 1)(c.role) &&
  text(100000, 1)(c.text) && Array.isArray(c.rules) && c.rules.length <= 100 && c.rules.every(RULE);
const hex = async (text: string) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)))]
  .map((b) => b.toString(16).padStart(2, "0")).join("");
const link = (v: any) => !!v && typeof v.url === "string" && /^https?:\/\//i.test(v.url);
const FLAG: Record<string, (v: unknown) => boolean> = {
  id: text(100, 1),
  t: number(0, 1e6),
  type: (v) => TYPES.includes(v as string),
  label: (v) => typeof v === "string" && /^[a-z_]{1,40}$/.test(v),
  quote: text(2000, 1),
  reason: text(2000),
  confidence: number(0, 1),
  sources: (v) => Array.isArray(v) && v.every(link),
  related: (v: any) => v === null || (typeof v === "object" && (!v.source || link(v.source))),
};

const reply = (status: number, body: object) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const keys = (o: object, wanted: string[]) => Object.keys(o).length === wanted.length && wanted.every((k) => Object.hasOwn(o, k));

// The first bad part of a request body, or null.
function invalid(body: any): string | null {
  if (!body || typeof body !== "object" || !keys(body, ["install_id", "helper_version", "marks"])) return "fields";
  if (typeof body.install_id !== "string" || !UUID.test(body.install_id)) return "install_id";
  if (!text(40, 1)(body.helper_version)) return "helper_version";
  if (!Array.isArray(body.marks) || !body.marks.length) return "marks";
  for (const [i, m] of body.marks.entries()) {
    if (!m || typeof m !== "object" || !keys(m, FIELDS)) return `marks[${i}]`;
    const bad = FIELDS.find((f) => !MARK[f](m[f]));
    if (bad) return `marks[${i}].${bad}`;
  }
  return null;
}

async function store(request: Request, env: Env): Promise<Response> {
  const raw = await request.arrayBuffer();
  if (raw.byteLength > MAX_BYTES) return reply(413, { error: `over ${MAX_BYTES} bytes` });
  let body: any;
  try {
    body = JSON.parse(new TextDecoder().decode(raw));
  } catch {
    return reply(400, { error: "bad json" });
  }
  if (Array.isArray(body?.marks) && body.marks.length > MAX_MARKS) return reply(413, { error: `over ${MAX_MARKS} marks` });
  const bad = invalid(body);
  if (bad) return reply(400, { error: `bad ${bad}` });

  const now = new Date().toISOString();
  const day = now.slice(0, 10);
  const used = await env.DB.prepare("SELECT n FROM requests WHERE install_id = ? AND day = ?").bind(body.install_id, day).first();
  if (used && Number(used.n) >= DAILY_REQUESTS) return reply(429, { error: `over ${DAILY_REQUESTS} requests today` });
  const all = await env.DB.prepare("SELECT n FROM requests WHERE install_id = ? AND day = ?").bind(ALL, day).first();
  if (all && Number(all.n) >= DAILY_ALL_MARKS) return reply(429, { error: `over ${DAILY_ALL_MARKS} marks today` });

  const columns = ["install_id", ...FIELDS, "helper_version", "received_at"];
  const insert = env.DB.prepare(
    `INSERT INTO marks (${columns.join(", ")}) VALUES (${columns.map(() => "?").join(", ")}) ` +
      `ON CONFLICT (install_id, video_id, flag_id) DO UPDATE SET ` +
      columns.filter((c) => !["install_id", "video_id", "flag_id"].includes(c)).map((c) => `${c} = excluded.${c}`).join(", "),
  );
  const count = (id: string, n: number) => env.DB.prepare(
    "INSERT INTO requests (install_id, day, n) VALUES (?, ?, ?) ON CONFLICT (install_id, day) DO UPDATE SET n = n + excluded.n",
  ).bind(id, day, n);
  await env.DB.batch([count(body.install_id, 1), count(ALL, body.marks.length), ...body.marks.map((m: any) =>
    insert.bind(body.install_id, ...FIELDS.map((f) => m[f]), body.helper_version, now))]);
  return reply(200, { stored: body.marks.length });
}

const admin = (request: Request, env: Env) =>
  !!env.ADMIN_TOKEN && request.headers.get("Authorization") === `Bearer ${env.ADMIN_TOKEN}`;

// The team's key set, fetched and cached by jose. Its URL comes from TEAM_DOMAIN, never from the token.
let teamKeys: { team: string; keys: ReturnType<typeof createRemoteJWKSet> } | undefined;

// True when the request carries the JWT that Cloudflare Access adds after the owner's login.
async function access(request: Request, env: Env): Promise<boolean> {
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!token || !env.TEAM_DOMAIN || !env.POLICY_AUD) return false;
  if (teamKeys?.team !== env.TEAM_DOMAIN) {
    teamKeys = { team: env.TEAM_DOMAIN, keys: createRemoteJWKSet(new URL("/cdn-cgi/access/certs", env.TEAM_DOMAIN)) };
  }
  try {
    await jwtVerify(token, teamKeys.keys, { issuer: env.TEAM_DOMAIN, audience: env.POLICY_AUD });
    return true;
  } catch {
    return false;
  }
}

// The first bad part of an uploaded analysis, or null.
function invalidAnalysis(body: any, video: string, lang: string): string | null {
  if (!body || typeof body !== "object" || !keys(body, ["install_id", "analysis", ...("prompts" in body ? ["prompts"] : [])])) {
    return "fields";
  }
  if (typeof body.install_id !== "string" || !UUID.test(body.install_id)) return "install_id";
  const a = body.analysis;
  if (!a || typeof a !== "object" || Object.keys(a).some((k) => !Object.hasOwn(ANALYSIS, k)) || REQUIRED.some((k) => !Object.hasOwn(a, k))) {
    return "analysis fields";
  }
  const bad = Object.keys(a).find((k) => !ANALYSIS[k](a[k]));
  if (bad) return `analysis.${bad}`;
  if (a.video_id !== video || a.lang !== lang) return "video or lang";
  for (const [i, f] of a.flags.entries()) {
    if (!f || typeof f !== "object") return `flags[${i}]`;
    const wrong = Object.keys(FLAG).find((k) => !FLAG[k](f[k]));
    if (wrong) return `flags[${i}].${wrong}`;
  }
  // A guest's tally counts only flags of the upload: the owner reads each flag that a profile card counts.
  const ids = new Set(a.flags.map((f: any) => f.id));
  if (a.summary && Object.values(a.summary).some((t: any) => [...Object.keys(t.flags), ...t.gravest].some((id) => !ids.has(id)))) {
    return "summary";
  }
  const p = body.prompts;
  if (p !== undefined && !(object(p) && keys(p, ["version", "components"]) && p.version === a.helper_version &&
    PROMPTS_VERSION.test(p.version) && Array.isArray(p.components) && p.components.length <= 50 &&
    p.components.every(COMPONENT))) return "prompts";
  return null;
}

const rank = (model: string | null) => RANK.findIndex((name) => (model ?? "").toLowerCase().includes(name));

async function share(request: Request, env: Env, video: string, lang: string): Promise<Response> {
  const raw = await request.arrayBuffer();
  if (raw.byteLength > MAX_ANALYSIS_BYTES) return reply(413, { error: `over ${MAX_ANALYSIS_BYTES} bytes` });
  let body: any;
  try {
    body = JSON.parse(new TextDecoder().decode(raw));
  } catch {
    return reply(400, { error: "bad json" });
  }
  if (Array.isArray(body?.analysis?.flags) && body.analysis.flags.length > MAX_FLAGS) {
    return reply(413, { error: `over ${MAX_FLAGS} flags` });
  }
  const bad = invalidAnalysis(body, video, lang);
  if (bad) return reply(400, { error: `bad ${bad}` });
  // Anyone can make an install id, so a prompts file counts only if its text gives its version's hash: the first one
  // kept for a version is then the only text that version can have.
  if (body.prompts) {
    const hash = (await hex(JSON.stringify(body.prompts.components))).slice(0, 12);
    if (body.prompts.version.match(PROMPTS_VERSION)[1] !== hash) return reply(400, { error: "bad prompts hash" });
  }
  const keepPrompts = body.prompts ? [env.DB.prepare(
    "INSERT OR IGNORE INTO prompts (version, prompts, received_at) VALUES (?, ?, ?)",
  ).bind(body.prompts.version, JSON.stringify(body.prompts), new Date().toISOString())] : [];

  const now = new Date().toISOString();
  const day = now.slice(0, 10);
  const used = await env.DB.prepare("SELECT n FROM uploads WHERE install_id = ? AND day = ?").bind(body.install_id, day).first();
  if (used && Number(used.n) >= DAILY_UPLOADS) return reply(429, { error: `over ${DAILY_UPLOADS} uploads today` });
  const count = env.DB.prepare(
    "INSERT INTO uploads (install_id, day, n) VALUES (?, ?, 1) ON CONFLICT (install_id, day) DO UPDATE SET n = n + 1",
  ).bind(body.install_id, day);

  const model = body.analysis.readers.parts.model ?? null;
  const stored = await env.DB.prepare("SELECT rank FROM analyses WHERE video_id = ? AND lang = ?").bind(video, lang).first();
  // The owner is the review: their upload replaces any stored one; anyone else's needs a better model.
  if (stored && !admin(request, env) && rank(model) <= Number(stored.rank)) {
    await env.DB.batch([count]);
    return reply(409, { error: "a whole analysis by an equal or better model is kept" });
  }
  // Only the owner's own upload is served at once: anyone can make an install id, so a stranger's flags wait, at most
  // MAX_PENDING of them; one already waiting can be sent again.
  if (!admin(request, env)) {
    const others = await env.DB.prepare(
      "SELECT COUNT(*) AS n FROM pending WHERE NOT (video_id = ? AND lang = ? AND install_id = ?)",
    ).bind(video, lang, body.install_id).first();
    if (Number(others?.n) >= MAX_PENDING) return reply(429, { error: `${MAX_PENDING} uploads wait for review` });
    await env.DB.batch([count, ...keepPrompts, env.DB.prepare(
      "INSERT INTO pending (video_id, lang, install_id, analysis, model, rank, received_at) VALUES (?, ?, ?, ?, ?, ?, ?) " +
        "ON CONFLICT (video_id, lang, install_id) DO UPDATE SET analysis = excluded.analysis, model = excluded.model, " +
        "rank = excluded.rank, received_at = excluded.received_at",
    ).bind(video, lang, body.install_id, JSON.stringify(body.analysis), model, rank(model), now)]);
    return reply(202, { pending: true });
  }
  const save = env.DB.prepare(
    "INSERT INTO analyses (video_id, lang, analysis, model, rank, install_id, received_at) VALUES (?, ?, ?, ?, ?, ?, ?) " +
      "ON CONFLICT (video_id, lang) DO UPDATE SET analysis = excluded.analysis, model = excluded.model, " +
      "rank = excluded.rank, install_id = excluded.install_id, received_at = excluded.received_at",
  ).bind(video, lang, JSON.stringify(body.analysis), model, rank(model), body.install_id, now);
  await env.DB.batch([count, ...keepPrompts, save]);
  return reply(stored ? 200 : 201, { stored: true });
}

// One pending upload, as the owner's list names it: its uploader and the time it came. A newer upload by the same
// uploader changes the time, so the owner never approves what they did not open.
const pendingRow = (env: Env, video: string, lang: string, url: URL) => env.DB.prepare(
  "SELECT install_id, analysis, model, rank FROM pending WHERE video_id = ? AND lang = ? AND install_id = ? " +
    "AND received_at = ?",
).bind(video, lang, url.searchParams.get("install") ?? "", url.searchParams.get("at") ?? "").first();

// The owner's review of the pending uploads of a video and language: reject deletes them all; approve serves the one
// opened and deletes the others. The caller checks that the request comes from the owner.
async function review(request: Request, env: Env, url: URL, video: string, lang: string, action: string): Promise<Response> {
  if (request.method !== "POST") return reply(405, { error: "method not allowed" });
  const clear = env.DB.prepare("DELETE FROM pending WHERE video_id = ? AND lang = ?").bind(video, lang);
  if (action === "reject") {
    const any = await env.DB.prepare("SELECT 1 FROM pending WHERE video_id = ? AND lang = ?").bind(video, lang).first();
    if (!any) return reply(404, { error: "nothing pending" });
    await env.DB.batch([clear]);
    return reply(200, { rejected: true });
  }
  const row = await pendingRow(env, video, lang, url);
  if (!row) return reply(409, { error: "the upload changed or is gone; open it again" });
  const serve = env.DB.prepare(
    "INSERT INTO analyses (video_id, lang, analysis, model, rank, install_id, received_at) VALUES (?, ?, ?, ?, ?, ?, ?) " +
      "ON CONFLICT (video_id, lang) DO UPDATE SET analysis = excluded.analysis, model = excluded.model, " +
      "rank = excluded.rank, install_id = excluded.install_id, received_at = excluded.received_at",
  ).bind(video, lang, row.analysis, row.model, row.rank, row.install_id, new Date().toISOString());
  await env.DB.batch([serve, clear]);
  return reply(200, { approved: true });
}

// S5: the ids of the flags that the owner hid in one video and language.
async function hiddenIds(env: Env, video: string, lang: string): Promise<Set<string>> {
  const { results } = await env.DB.prepare("SELECT flag_id FROM hidden WHERE video_id = ? AND lang = ?").bind(video, lang).all();
  return new Set(results.map((r) => String(r.flag_id)));
}

// A guest's tally without the hidden flags: their claims stay in `checked`, so they count as correct.
const visibleTally = (t: any, hidden: Set<string>) => ({
  ...t,
  flags: Object.fromEntries(Object.entries(t.flags).filter(([id]) => !hidden.has(id))),
  gravest: t.gravest.filter((id: string) => !hidden.has(id)),
});

// An analysis as another helper gets it: no hidden flag in its flags or in its guests' tallies.
function visible(analysis: any, hidden: Set<string>) {
  if (!hidden.size) return analysis;
  const summary = analysis.summary && Object.fromEntries(
    Object.entries(analysis.summary).map(([name, t]) => [name, visibleTally(t, hidden)]),
  );
  return { ...analysis, flags: analysis.flags.filter((f: any) => !hidden.has(f.id)), ...(summary ? { summary } : {}) };
}

// The owner hides a flag of a video and language, or shows it again. The flag must be in the approved analysis or in
// a pending upload, so a hide before approval holds once it is served. The caller checks that the request comes from
// the owner.
async function hide(request: Request, env: Env, url: URL, video: string, flag: string, action: string): Promise<Response> {
  const lang = url.searchParams.get("lang") ?? "";
  if (!VIDEO.test(video) || !["es", "en"].includes(lang)) return reply(400, { error: "bad video or lang" });
  if (request.method !== "POST") return reply(405, { error: "method not allowed" });
  const held = await env.DB.prepare(
    "SELECT 1 FROM (SELECT analysis FROM analyses WHERE video_id = ?1 AND lang = ?2 " +
      "UNION ALL SELECT analysis FROM pending WHERE video_id = ?1 AND lang = ?2) AS a, json_each(a.analysis, '$.flags') " +
      "WHERE json_extract(value, '$.id') = ?3 LIMIT 1",
  ).bind(video, lang, flag).first();
  if (!held) return reply(404, { error: "no such flag" });
  await env.DB.batch([action === "hide"
    ? env.DB.prepare("INSERT OR IGNORE INTO hidden (video_id, lang, flag_id, hidden_at) VALUES (?, ?, ?, ?)")
      .bind(video, lang, flag, new Date().toISOString())
    : env.DB.prepare("DELETE FROM hidden WHERE video_id = ? AND lang = ? AND flag_id = ?").bind(video, lang, flag)]);
  return reply(200, { hidden: action === "hide" });
}

// The owner swaps the halves of a debate's thumbnail, or keeps the speaker order: one row of `faces` per video, for
// every language. The video must be approved. The caller checks that the request comes from the owner.
async function faces(request: Request, env: Env, video: string, action: string): Promise<Response> {
  if (!VIDEO.test(video)) return reply(400, { error: "bad video" });
  if (request.method !== "POST") return reply(405, { error: "method not allowed" });
  if (!(await env.DB.prepare("SELECT 1 FROM analyses WHERE video_id = ? LIMIT 1").bind(video).first())) {
    return reply(404, { error: "not shared" });
  }
  await env.DB.batch([action === "swap"
    ? env.DB.prepare("INSERT OR IGNORE INTO faces (video_id, swapped_at) VALUES (?, ?)").bind(video, new Date().toISOString())
    : env.DB.prepare("DELETE FROM faces WHERE video_id = ?").bind(video)]);
  return reply(200, { swap: action === "swap" });
}

// The owner turns a video off or on for the public: one row of `inactive` per video, for every language. The video
// must be approved. The caller checks that the request comes from the owner.
async function active(request: Request, env: Env, video: string, action: string): Promise<Response> {
  if (!VIDEO.test(video)) return reply(400, { error: "bad video" });
  if (request.method !== "POST") return reply(405, { error: "method not allowed" });
  if (!(await env.DB.prepare("SELECT 1 FROM analyses WHERE video_id = ? LIMIT 1").bind(video).first())) {
    return reply(404, { error: "not shared" });
  }
  await env.DB.batch([action === "off"
    ? env.DB.prepare("INSERT OR IGNORE INTO inactive (video_id, off_at) VALUES (?, ?)").bind(video, new Date().toISOString())
    : env.DB.prepare("DELETE FROM inactive WHERE video_id = ?").bind(video)]);
  return reply(200, { active: action === "on" });
}

// The review page's approved videos, newest first, with their flags and how many are hidden.
async function listApproved(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  const { results } = await env.DB.prepare(
    "SELECT video_id, lang, json_extract(analysis, '$.title') AS title, " +
      `CASE WHEN ${GUESTS} >= 2 THEN 'debate' ELSE 'interview' END AS type, ` +
      "json_array_length(analysis, '$.flags') AS flags, " +
      "(SELECT COUNT(*) FROM hidden WHERE hidden.video_id = analyses.video_id AND hidden.lang = analyses.lang) AS hidden, " +
      `${GUESTS} AS guests, ${SWAP}, ${OWN_TITLE}, NOT ${OFF} AS active, received_at FROM analyses ORDER BY received_at DESC`,
  ).all();
  return reply(200, { rows: results.map((r) => ({ ...r, swap: Boolean(r.swap), active: Boolean(r.active) })) });
}

// A debate has two or more guests: the speakers with role `guest` in `people`, else every speaker, as the helper's
// summary counts them. A serious flag is one the judge rated serious and did not call a nitpick, as on the card title.
const GUEST_NAMES =
  "CASE WHEN json_type(analysis, '$.people') = 'object' AND EXISTS (SELECT 1 FROM json_each(analysis, '$.people')) " +
  "THEN (SELECT json_group_array(key) FROM json_each(analysis, '$.people') WHERE json_extract(value, '$.role') = 'guest') " +
  "ELSE (SELECT json_group_array(name) FROM (SELECT value AS name FROM json_each(analysis, '$.speakers') " +
  "UNION SELECT json_extract(value, '$.speaker') FROM json_each(analysis, '$.flags')) WHERE name IS NOT NULL) END";
const GUESTS = `json_array_length(${GUEST_NAMES})`;
// The owner swapped the halves of this video's thumbnail (S11).
// The owner's display title of an approved video (POST /admin/videos/<video_id>/title, `{title}`): it wins over the
// clean title; an empty one deletes it, so the clean title shows again.
async function ownTitle(request: Request, env: Env, video: string): Promise<Response> {
  if (!VIDEO.test(video)) return reply(400, { error: "bad video" });
  if (request.method !== "POST") return reply(405, { error: "method not allowed" });
  let title: unknown;
  try {
    title = ((await request.json()) as { title?: unknown }).title;
  } catch {
    return reply(400, { error: "bad json" });
  }
  if (typeof title !== "string" || title.trim().length > 200) return reply(400, { error: "bad title" });
  if (!(await env.DB.prepare("SELECT 1 FROM analyses WHERE video_id = ? LIMIT 1").bind(video).first())) {
    return reply(404, { error: "not shared" });
  }
  await env.DB.batch([title.trim()
    ? env.DB.prepare("INSERT INTO titles (video_id, title, set_at) VALUES (?, ?, ?) ON CONFLICT (video_id) DO UPDATE SET " +
        "title = excluded.title, set_at = excluded.set_at").bind(video, title.trim(), new Date().toISOString())
    : env.DB.prepare("DELETE FROM titles WHERE video_id = ?").bind(video)]);
  return reply(200, { title: title.trim() || null });
}

// The owner's display title of a video, if any (the titles table).
const OWN_TITLE = "(SELECT title FROM titles WHERE titles.video_id = analyses.video_id) AS own_title";
// The owner turned this video off (the inactive table): the public API and the web app serve only the others.
const OFF = "EXISTS (SELECT 1 FROM inactive WHERE inactive.video_id = analyses.video_id)";
const SWAP = "EXISTS (SELECT 1 FROM faces WHERE faces.video_id = analyses.video_id) AS swap";
const SERIOUS =
  "(SELECT COUNT(*) FROM json_each(analysis, '$.flags') WHERE json_extract(value, '$.judge.severity') = 'serious' " +
  "AND coalesce(json_extract(value, '$.judge.verdict'), '') <> 'nitpick')";

async function listPending(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  const { results } = await env.DB.prepare(
    "SELECT video_id, lang, model, json_extract(analysis, '$.readers') AS readers, " +
      "json_extract(analysis, '$.cost_usd') AS cost_usd, " +
      `CASE WHEN ${GUESTS} >= 2 THEN 'debate' ELSE 'interview' END AS type, ` +
      `json_array_length(analysis, '$.flags') AS flags, ${SERIOUS} AS serious, install_id, received_at ` +
      "FROM pending ORDER BY received_at",
  ).all();
  return reply(200, { rows: results.map((r) => ({ ...r, readers: JSON.parse(String(r.readers)) })) });
}

// The review page and its calls, only after the Access check.
async function page(request: Request, env: Env, url: URL): Promise<Response> {
  if (!(await access(request, env))) return reply(401, { error: "unauthorized" });
  // The Access cookie goes with a post from any site, so a post must come from the review page itself.
  const origin = request.headers.get("Origin");
  if (request.method !== "GET" && origin !== null && origin !== url.origin) return reply(403, { error: "forbidden origin" });
  if (url.pathname === "/admin" || url.pathname === "/admin/") {
    return env.ASSETS.fetch(new Request(new URL("/admin/", url), request));
  }
  if (url.pathname === "/admin/pending") return listPending(request, env);
  if (url.pathname === "/admin/marks") return latestMarks(request, env);
  if (url.pathname === "/admin/feedback") return latestFeedback(request, env);
  if (url.pathname === "/admin/visits") return listVisits(request, env);
  if (url.pathname === "/admin/approved") return listApproved(request, env);
  const flag = url.pathname.match(/^\/admin\/analyses\/([^/]+)\/flags\/([^/]+)\/(hide|show)$/);
  if (flag) return hide(request, env, url, flag[1], flag[2], flag[3]);
  const swap = url.pathname.match(/^\/admin\/videos\/([^/]+)\/faces\/(swap|keep)$/);
  if (swap) return faces(request, env, swap[1], swap[2]);
  const power = url.pathname.match(/^\/admin\/videos\/([^/]+)\/active\/(on|off)$/);
  if (power) return active(request, env, power[1], power[2]);
  const named = url.pathname.match(/^\/admin\/videos\/([^/]+)\/title$/);
  if (named) return ownTitle(request, env, named[1]);
  const kept = url.pathname.match(/^\/admin\/(approved|hidden)\/([^/]+)$/);
  if (kept) return keptAnalysis(request, env, url, kept[2], kept[1]);
  const upload = url.pathname.match(/^\/admin\/pending\/([^/]+?)(?:\/(approve|reject))?$/);
  if (!upload) return reply(404, { error: "not found" });
  const [, video, action] = upload;
  const lang = url.searchParams.get("lang") ?? "";
  if (!VIDEO.test(video) || !["es", "en"].includes(lang)) return reply(400, { error: "bad video or lang" });
  if (action) return review(request, env, url, video, lang, action);
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  const row = await pendingRow(env, video, lang, url);
  return row
    ? new Response(String(row.analysis), { headers: { "Content-Type": "application/json" } })
    : reply(404, { error: "nothing pending" });
}

// The review page's view of an approved analysis in full (`approved`), or the hidden flag ids of a video and
// language (`hidden`), for its Hide and Show buttons.
async function keptAnalysis(request: Request, env: Env, url: URL, video: string, what: string): Promise<Response> {
  const lang = url.searchParams.get("lang") ?? "";
  if (!VIDEO.test(video) || !["es", "en"].includes(lang)) return reply(400, { error: "bad video or lang" });
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  if (what === "hidden") return reply(200, { flags: [...await hiddenIds(env, video, lang)] });
  const row = await env.DB.prepare("SELECT analysis FROM analyses WHERE video_id = ? AND lang = ?").bind(video, lang).first();
  return row
    ? new Response(String(row.analysis), { headers: { "Content-Type": "application/json" } })
    : reply(404, { error: "not shared" });
}

async function analyses(request: Request, env: Env, url: URL, video: string, action?: string): Promise<Response> {
  const lang = url.searchParams.get("lang") ?? "";
  if (!VIDEO.test(video) || !["es", "en"].includes(lang)) return reply(400, { error: "bad video or lang" });
  if (action) return admin(request, env) ? review(request, env, url, video, lang, action) : reply(401, { error: "unauthorized" });
  if (request.method === "PUT") return share(request, env, video, lang);
  if (request.method === "GET") {
    const row = await env.DB.prepare("SELECT analysis FROM analyses WHERE video_id = ? AND lang = ?").bind(video, lang).first();
    if (!row) return reply(404, { error: "not shared" });
    return reply(200, visible(JSON.parse(String(row.analysis)), await hiddenIds(env, video, lang)));
  }
  if (request.method === "DELETE") {
    if (!admin(request, env)) return reply(401, { error: "unauthorized" });
    await env.DB.batch([env.DB.prepare("DELETE FROM analyses WHERE video_id = ? AND lang = ?").bind(video, lang)]);
    return reply(200, { deleted: true });
  }
  return reply(405, { error: "method not allowed" });
}

// The public API: approved analyses only, never a pending upload. Cloudflare keeps each answer 60 s.
const apiReply = (status: number, body: object) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=60" },
});
const VIDEO_FIELDS =
  "video_id, json_extract(analysis, '$.title') AS title, json_extract(analysis, '$.channel') AS channel, " +
  "json_extract(analysis, '$.duration') AS duration, json_extract(analysis, '$.published_at') AS published_at, " +
  `CASE WHEN ${GUESTS} >= 2 THEN 'debate' ELSE 'interview' END AS type, ${GUEST_NAMES} AS guests, ${OWN_TITLE}, ` +
  "(SELECT COUNT(*) FROM json_each(analysis, '$.flags') WHERE json_extract(value, '$.id') NOT IN " +
  `(SELECT flag_id FROM hidden WHERE hidden.video_id = analyses.video_id AND hidden.lang = analyses.lang)) AS flags, ${SWAP}`;

/** The proper names of our own data that a clean title may restore: each channel, each person's name, and each word
 * of 4 or more letters of a person's name (a surname alone). */
async function knownNames(env: Env): Promise<string[]> {
  const { results } = await env.DB.prepare(
    "SELECT json_extract(analysis, '$.channel') AS channel, json_extract(analysis, '$.people') AS people FROM analyses",
  ).all();
  const names = new Set<string>();
  for (const r of results) {
    if (r.channel) names.add(String(r.channel));
    for (const person of Object.keys(r.people ? JSON.parse(String(r.people)) : {})) {
      names.add(person);
      for (const word of person.split(/\s+/)) if (word.length >= 4) names.add(word);
    }
  }
  return [...names];
}

/** The title a reader sees: the owner's own, else the clean one (src/shared/titles.ts). */
const displayTitle = (title: unknown, own: unknown, names: string[]) =>
  own !== null && own !== undefined ? String(own) : title === null ? null : cleanTitle(String(title), names);

const withGuests = ({ own_title, ...row }: Record<string, unknown>, names: string[]) => ({
  ...row, display_title: displayTitle(row.title, own_title, names), guests: JSON.parse(String(row.guests)), swap: Boolean(row.swap),
});

// The numbers of a guest's profile card from the tally of each flag (S4): `correct` is what was checked and not
// false, misleading or a nitpick; devices by count, ties to the one with more serious flags.
function guestSummary(t: any) {
  const flags = Object.values(t.flags) as Record<string, string | null>[];
  const count = (key: string, value: string) => flags.filter((f) => f[key] === value).length;
  const verdicts = { false: count("verdict", "false"), misleading: count("verdict", "misleading"), nitpick: count("verdict", "nitpick") };
  const devices = new Map<string, { label: string; count: number; serious: number }>();
  for (const f of flags) {
    if (!f.device) continue;
    const d = devices.get(f.device) ?? devices.set(f.device, { label: f.device, count: 0, serious: 0 }).get(f.device)!;
    d.count += 1;
    d.serious += Number(f.severity === "serious");
  }
  return {
    checked: t.checked,
    verdicts: { ...verdicts, correct: t.checked - verdicts.false - verdicts.misleading - verdicts.nitpick },
    severity: { serious: count("severity", "serious"), moderate: count("severity", "moderate"), minor: count("severity", "minor") },
    devices: [...devices.values()].sort((a, b) => b.count - a.count || b.serious - a.serious)
      .map(({ label, count }) => ({ label, count })),
    dodged: count("question", "dodged"),
    partial: count("question", "partial"),
    asked: t.asked,
    gravest: t.gravest.slice(0, 2),
  };
}

// The prompts file of a version that an approved analysis names, or null: a pending upload never publishes a file.
async function served(env: Env, version: string): Promise<any> {
  const row = await env.DB.prepare(
    "SELECT prompts FROM prompts WHERE version = ? AND EXISTS " +
      "(SELECT 1 FROM analyses WHERE json_extract(analysis, '$.helper_version') = prompts.version)",
  ).bind(version).first();
  return row ? JSON.parse(String(row.prompts)) : null;
}

async function api(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  // A POST is never cached, so feedback can come through this entrypoint.
  if (url.pathname === "/api/feedback" && request.method === "POST") return feedback(request, env);
  if (url.pathname === "/api/visits" && request.method === "POST") return seek(request, env);
  if (request.method !== "GET") return apiReply(405, { error: "method not allowed" });
  if (url.pathname === "/api/videos") {
    // One entry per video: the fields of its newest approved language (SQLite takes bare columns from the MAX row).
    const { results } = await env.DB.prepare(
      `SELECT ${VIDEO_FIELDS}, json_group_array(lang) AS langs, lang AS served, json_extract(analysis, '$.flags') AS judged, ` +
        `MAX(received_at) FROM analyses WHERE NOT ${OFF} GROUP BY video_id ORDER BY published_at DESC, video_id`,
    ).all();
    const { results: hidden } = await env.DB.prepare("SELECT video_id, lang, flag_id FROM hidden").all();
    const isHidden = new Set(hidden.map((h) => `${h.video_id} ${h.lang} ${h.flag_id}`));
    const names = await knownNames(env);
    // The counts by verdict kind (S4) leave out what the web never shows: a hidden flag and a flag the judge dropped.
    const videos = results.map(({ "MAX(received_at)": _, served, judged, ...r }) => ({
      ...withGuests(r, names),
      langs: JSON.parse(String(r.langs)),
      counts: countKinds((JSON.parse(String(judged)) as (Judged & { id: string })[])
        .filter((f) => f.judge?.verdict !== "drop" && !isHidden.has(`${r.video_id} ${served} ${f.id}`))),
    }));
    return apiReply(200, { videos });
  }
  const version = url.pathname.match(/^\/api\/prompts\/([^/]+)$/);
  if (version) {
    const file = await served(env, decodeURIComponent(version[1]));
    return file ? apiReply(200, file) : apiReply(404, { error: "not found" });
  }
  const route = url.pathname.match(/^\/api\/videos\/([^/]+?)(\/flags)?$/);
  if (!route) return apiReply(404, { error: "not found" });
  const [, video, flags] = route;
  const lang = url.searchParams.get("lang") ?? "";
  if (!VIDEO.test(video) || !["es", "en"].includes(lang)) return apiReply(400, { error: "bad video or lang" });
  if (!flags) {
    // The asked language, else the other one, which the answer names as `requested`.
    const row = await env.DB.prepare(
      `SELECT ${VIDEO_FIELDS}, lang, (SELECT version FROM prompts WHERE version = json_extract(analysis, '$.helper_version')) ` +
        "AS prompts, json_extract(analysis, '$.summary') AS summary, json_extract(analysis, '$.people') AS people, " +
        `json_extract(analysis, '$.turns') AS turns FROM analyses WHERE video_id = ? AND NOT ${OFF} ORDER BY lang = ? DESC LIMIT 1`,
    ).bind(video, lang).first();
    if (!row) return apiReply(404, { error: "not found" });
    const tallies = row.summary ? JSON.parse(String(row.summary)) : null;
    const hidden = await hiddenIds(env, video, String(row.lang));
    const summary = tallies &&
      Object.fromEntries(Object.entries(tallies).map(([name, t]) => [name, guestSummary(visibleTally(t, hidden))]));
    // Each person's speech (S5) only from an upload with voice turns: an older one may hold a stale `spoken_s`.
    const turns = row.turns ? JSON.parse(String(row.turns)) : null;
    const people = turns && row.people ? Object.fromEntries(Object.entries(JSON.parse(String(row.people)) as Record<string, any>)
      .map(([name, p]) => [name, { role: p.role, spoken_s: p.spoken_s, turns: p.turns, longest_s: p.longest_s }])) : null;
    return apiReply(200, { ...withGuests(row, await knownNames(env)), summary, people, turns, ...(row.lang === lang ? {} : { requested: lang }) });
  }
  const row = await env.DB.prepare(`SELECT json_extract(analysis, '$.flags') AS flags FROM analyses WHERE video_id = ? AND lang = ? AND NOT ${OFF}`)
    .bind(video, lang).first();
  if (!row) return apiReply(404, { error: "not found" });
  const hidden = await hiddenIds(env, video, lang);
  const all = (JSON.parse(String(row.flags)) as { id: string; t: number }[]).filter((f) => !hidden.has(f.id))
    .sort((a, b) => a.t - b.t);
  // The cursor is the number of flags already given: a live stream appends flags, so a position stays valid.
  const after = url.searchParams.get("after") ?? "0";
  if (!/^\d+$/.test(after) || Number(after) > all.length) return apiReply(400, { error: "bad cursor" });
  return apiReply(200, { flags: all.slice(Number(after)), cursor: String(all.length), live: false });
}

// S8: feedback on the method. A web id costs nothing to make, so all ids share one stop per UTC day as well.
const MAX_FEEDBACK_BYTES = 8 * 1024;
const DAILY_FEEDBACK = 20; // per id
const DAILY_ALL_FEEDBACK = 1000;
// The fields of each kind and their checks; `text`, `install_id` and the required fields must be there.
const FEEDBACK: Record<string, { fields: Record<string, (v: unknown) => boolean>; required: string[] }> = {
  flag: {
    fields: { video_id: (v) => typeof v === "string" && VIDEO.test(v), flag_id: text(100, 1), rule: ID, version: text(40, 1), text: text(1000) },
    required: ["video_id", "flag_id", "text"],
  },
  prompt: {
    fields: {
      video_id: (v) => typeof v === "string" && VIDEO.test(v), version: text(40, 1), component: ID, rule: ID,
      quote: text(1000, 1), text: text(1000, 1),
    },
    required: ["version", "component", "text"],
  },
};
const FEEDBACK_ROW = "id, kind, video_id, flag_id, rule, version, component, quote, text, install_id, received_at";
const FEEDBACK_COLUMNS = ["kind", "video_id", "flag_id", "rule", "version", "component", "quote", "text", "install_id"];

// The first bad part of a feedback item, or null. A `prompt` item must point to text of a served prompts file.
async function invalidFeedback(body: any, env: Env): Promise<string | null> {
  if (!object(body)) return "fields";
  if (!Object.hasOwn(FEEDBACK, body.kind)) return "kind";
  const kind = FEEDBACK[body.kind];
  if (typeof body.install_id !== "string" || !UUID.test(body.install_id)) return "install_id";
  const bad = Object.keys(body).find((k) => k !== "kind" && k !== "install_id" && !(Object.hasOwn(kind.fields, k) && kind.fields[k](body[k])));
  if (bad) return bad;
  const missing = kind.required.find((k) => !Object.hasOwn(body, k));
  if (missing) return missing;
  if (body.kind === "flag") return null;
  const file = await served(env, body.version);
  if (!file) return "version";
  const component = (file.components as any[]).find((c) => c.id === body.component);
  if (!component) return "component";
  const rule = "rule" in body ? (component.rules as any[]).find((r) => r.id === body.rule) : null;
  if ("rule" in body && !rule) return "rule";
  if ("quote" in body && !(rule ?? component).text.includes(body.quote)) return "quote";
  return null;
}

async function feedback(request: Request, env: Env): Promise<Response> {
  const raw = await request.arrayBuffer();
  if (raw.byteLength > MAX_FEEDBACK_BYTES) return apiReply(413, { error: `over ${MAX_FEEDBACK_BYTES} bytes` });
  let body: any;
  try {
    body = JSON.parse(new TextDecoder().decode(raw));
  } catch {
    return apiReply(400, { error: "bad json" });
  }
  const bad = await invalidFeedback(body, env);
  if (bad) return apiReply(400, { error: `bad ${bad}` });
  const now = new Date().toISOString();
  const day = now.slice(0, 10);
  const used = await env.DB.prepare(
    "SELECT (SELECT COUNT(*) FROM feedback WHERE install_id = ? AND received_at >= ?) AS mine, " +
      "(SELECT COUNT(*) FROM feedback WHERE received_at >= ?) AS everyone",
  ).bind(body.install_id, day, day).first();
  if (Number(used?.mine) >= DAILY_FEEDBACK) return apiReply(429, { error: `over ${DAILY_FEEDBACK} items today` });
  if (Number(used?.everyone) >= DAILY_ALL_FEEDBACK) return apiReply(429, { error: `over ${DAILY_ALL_FEEDBACK} items today for all` });
  await env.DB.batch([env.DB.prepare(
    `INSERT INTO feedback (${FEEDBACK_COLUMNS.join(", ")}, received_at) VALUES (${FEEDBACK_COLUMNS.map(() => "?").join(", ")}, ?)`,
  ).bind(...FEEDBACK_COLUMNS.map((c) => body[c] ?? null), now)]);
  return apiReply(200, { stored: 1 });
}

// The cached entrypoint of the public API (wrangler.toml [exports.PublicApi]).
export const PublicApi = { fetch: (request: Request, env: Env) => api(request, env) };

const MARK_ROW = `install_id, helper_version, received_at, ${FIELDS.join(", ")}`;

async function read(url: URL, request: Request, env: Env): Promise<Response> {
  if (!admin(request, env)) return reply(401, { error: "unauthorized" });
  const since = url.searchParams.get("since") ?? "";
  const { results } = await env.DB.prepare(
    `SELECT ${MARK_ROW} FROM marks WHERE received_at > ? ORDER BY received_at, install_id, video_id, flag_id`,
  ).bind(since).all();
  return reply(200, { rows: results });
}

// The review page's list of marks: the latest 200, newest first. `feedback pull` keeps the whole history.
async function latestMarks(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  const { results } = await env.DB.prepare(`SELECT ${MARK_ROW} FROM marks ORDER BY received_at DESC LIMIT 200`).all();
  return reply(200, { rows: results });
}

// The owner's read of feedback: the rows received after `since`, oldest first.
async function readFeedback(url: URL, request: Request, env: Env): Promise<Response> {
  if (!admin(request, env)) return reply(401, { error: "unauthorized" });
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  const { results } = await env.DB.prepare(`SELECT ${FEEDBACK_ROW} FROM feedback WHERE received_at > ? ORDER BY received_at, id`)
    .bind(url.searchParams.get("since") ?? "").all();
  return reply(200, { rows: results });
}

// The review page's list of feedback: the latest 200, newest first.
async function latestFeedback(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  const { results } = await env.DB.prepare(`SELECT ${FEEDBACK_ROW} FROM feedback ORDER BY received_at DESC, id DESC LIMIT 200`).all();
  return reply(200, { rows: results });
}

// A day's counter of one video, language and kind ("visit" or "seek"): no cookie, no id, at most VISITS_MAX a day.
const VISITS_MAX = 10_000;
async function count(env: Env, video: string, lang: string, kind: "visit" | "seek") {
  await env.DB.prepare(
    "INSERT INTO visits (video_id, lang, day, kind, n) VALUES (?, ?, ?, ?, 1) " +
      "ON CONFLICT (video_id, lang, day, kind) DO UPDATE SET n = n + 1 WHERE n < ?",
  ).bind(video, lang, new Date().toISOString().slice(0, 10), kind, VISITS_MAX).run();
}

// POST /api/visits {video_id, lang, kind: "seek"}: a jump to a flag's moment of an approved video.
async function seek(request: Request, env: Env): Promise<Response> {
  const body = await request.json().catch(() => null) as { video_id?: unknown; lang?: unknown; kind?: unknown } | null;
  const video = String(body?.video_id ?? "");
  if (!VIDEO.test(video) || !["es", "en"].includes(String(body?.lang)) || body?.kind !== "seek") {
    return apiReply(400, { error: "bad request" });
  }
  if (!(await env.DB.prepare(`SELECT 1 FROM analyses WHERE video_id = ? AND NOT ${OFF}`).bind(video).first())) {
    return apiReply(404, { error: "not found" });
  }
  await count(env, video, String(body!.lang), "seek");
  return new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": "*" } });
}

// The review page's visits table: visits and seeks per video, language and day, newest day first.
async function listVisits(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  const { results } = await env.DB.prepare(
    "SELECT video_id, lang, day, SUM(CASE kind WHEN 'visit' THEN n ELSE 0 END) AS visits, " +
      "SUM(CASE kind WHEN 'seek' THEN n ELSE 0 END) AS seeks FROM visits " +
      "GROUP BY video_id, lang, day ORDER BY day DESC, video_id, lang LIMIT 500",
  ).all();
  return reply(200, { rows: results });
}

// An old test page link: the viewer in the browser's language, as / picks it.
const browserLang = (request: Request) => (/^es\b/i.test(request.headers.get("Accept-Language") ?? "") ? "es" : "en");
function tryPage(request: Request, url: URL): Response {
  const video = url.pathname.match(/^\/try\/([\w-]+)$/)?.[1];
  if (!video) return reply(404, { error: "not found" });
  return Response.redirect(new URL(`/${browserLang(request)}/v/${video}`, url).toString(), 301);
}

const escape = (text: string) =>
  text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
// The neutral share tags of the app's index.html: its <title> and og:title, side by side.
const SHARE_TAGS = /<title>[^<]*<\/title>\s*<meta property="og:title" content="[^"]*">/;

// The web app's one HTML for every path. A video page replaces the neutral share tags with the stored title, escaped
// (an analysis of the asked language, else the other one), and the video's YouTube thumbnail.
async function webApp(request: Request, env: Env, url: URL, ctx: Context): Promise<Response> {
  if (url.pathname === "/") {
    return Response.redirect(new URL(`/${browserLang(request)}/`, url).toString(), 302);
  }
  let html = await (await env.ASSETS.fetch(new Request(new URL("/app/", url), request))).text();
  const [, lang, page, video] = url.pathname.split("/");
  if (page === "v" && VIDEO.test(video ?? "")) {
    const row = await env.DB.prepare(
      `SELECT json_extract(analysis, '$.title') AS title, ${OWN_TITLE} FROM analyses WHERE video_id = ? AND NOT ${OFF} ORDER BY lang = ? DESC LIMIT 1`,
    ).bind(video, lang).first();
    if (row) {
      ctx.waitUntil(count(env, video, lang, "visit")); // the page does not wait for the count
      // A video with no title keeps the neutral tags.
      const shown = displayTitle(row.title, row.own_title, await knownNames(env));
      if (shown !== null) {
        const title = `${escape(shown)} · DeFacto`; // the tab names the page, then the site
        html = html.replace(SHARE_TAGS, () => `<title>${title}</title>\n<meta property="og:title" content="${title}">\n` +
          `<meta property="og:image" content="https://i.ytimg.com/vi/${video}/hqdefault.jpg">`);
      }
    }
  }
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8", "X-Robots-Tag": "noindex",
      // The YouTube embed needs the page's origin as Referer (error 153 without it).
      "Referrer-Policy": "strict-origin-when-cross-origin",
    },
  });
}

export default {
  async fetch(request: Request, env: Env, ctx: Context) {
    const url = new URL(request.url);
    // Ids are free, so every write outside the owner's page also counts against the sender's address.
    if (!["GET", "HEAD"].includes(request.method) && !url.pathname.startsWith("/admin") &&
      !(await env.WRITES.limit({ key: request.headers.get("CF-Connecting-IP") ?? "" })).success) {
      return reply(429, { error: "too many requests from this address" });
    }
    if (url.pathname.startsWith("/try/")) return tryPage(request, url);
    if (url.pathname === "/" || /^\/(es|en)\//.test(url.pathname)) return webApp(request, env, url, ctx);
    if (url.pathname.startsWith("/api/")) return ctx.exports.PublicApi.fetch(request);
    if (url.pathname === "/admin" || url.pathname.startsWith("/admin/")) return page(request, env, url);
    if (url.pathname === "/analyses") {
      return admin(request, env) ? listPending(request, env) : reply(401, { error: "unauthorized" });
    }
    const flag = url.pathname.match(/^\/analyses\/([^/]+)\/flags\/([^/]+)\/(hide|show)$/);
    if (flag) {
      return admin(request, env) ? hide(request, env, url, flag[1], flag[2], flag[3]) : reply(401, { error: "unauthorized" });
    }
    const shared = url.pathname.match(/^\/analyses\/([^/]+?)(?:\/(approve|reject))?$/);
    if (shared) return analyses(request, env, url, shared[1], shared[2]);
    if (url.pathname === "/feedback") return readFeedback(url, request, env);
    if (url.pathname !== "/marks") return reply(404, { error: "not found" });
    if (request.method === "POST") return store(request, env);
    if (request.method === "GET") return read(url, request, env);
    return reply(405, { error: "method not allowed" });
  },
};
