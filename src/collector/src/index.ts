// The feedback collector: a Cloudflare Worker that keeps the testers' marks and shared analyses in D1.
// POST /marks stores one tester's marks; GET /marks?since=<iso> returns the rows received after that time, only to
// the owner (Authorization: Bearer <ADMIN_TOKEN>).
// PUT /analyses/<video_id>?lang= keeps a whole analysis: pending until the owner approves it, served at once when the
// owner uploads it. GET serves only approved analyses, to anyone. The owner lists the pending ones (GET /analyses),
// approves or rejects one (POST /analyses/<video_id>/approve|reject?lang=) and deletes a served one (DELETE).

// The part of the D1 binding that the collector uses (developers.cloudflare.com/d1/worker-api/).
interface D1Statement {
  bind(...values: unknown[]): D1Statement;
  first(): Promise<Record<string, unknown> | null>;
  all(): Promise<{ results: Record<string, unknown>[] }>;
}
interface Env {
  DB: { prepare(sql: string): D1Statement; batch(statements: D1Statement[]): Promise<unknown> };
  ADMIN_TOKEN: string;
}

const MAX_BYTES = 256 * 1024;
const MAX_MARKS = 500;
const DAILY_REQUESTS = 20; // the hard stop per tester
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const TYPES = ["fallacy", "bias", "contradiction", "inaccuracy", "question", "context"];
const VIDEO = /^[A-Za-z0-9_-]{6,20}$/;

const text = (max: number, min = 0) => (v: unknown) => typeof v === "string" && v.length >= min && v.length <= max;
const orNull = (check: (v: unknown) => boolean) => (v: unknown) => v === null || check(v);
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
// The parts model of a stored analysis ranks it: a later upload replaces it only from a higher rank. Any other model
// ranks under these.
const RANK = ["haiku", "sonnet", "opus"];
const ANALYSIS: Record<string, (v: unknown) => boolean> = {
  video_id: (v) => typeof v === "string" && VIDEO.test(v),
  lang: (v) => v === "es" || v === "en",
  spoken: (v) => v === "es" || v === "en",
  status: (v) => v === "done",
  published_at: orNull(text(40)),
  title: orNull(text(500)),
  channel: orNull(text(200)),
  duration: orNull(number(0, 1e6)),
  speakers: (v) => !!v && typeof v === "object" && !Array.isArray(v),
  readers: (v: any) => !!v && typeof v === "object" && !!v.parts && orNull(text(100, 1))(v.parts.model),
  cost_usd: orNull(number(0, 1e6)),
  analysed_until: number(0, 1e6),
  helper_version: text(40, 1),
  flags: Array.isArray,
};
const REQUIRED = ["video_id", "lang", "status", "readers", "helper_version", "flags"];
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

const keys = (o: object, wanted: string[]) => Object.keys(o).length === wanted.length && wanted.every((k) => k in o);

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

  const columns = ["install_id", ...FIELDS, "helper_version", "received_at"];
  const insert = env.DB.prepare(
    `INSERT INTO marks (${columns.join(", ")}) VALUES (${columns.map(() => "?").join(", ")}) ` +
      `ON CONFLICT (install_id, video_id, flag_id) DO UPDATE SET ` +
      columns.filter((c) => !["install_id", "video_id", "flag_id"].includes(c)).map((c) => `${c} = excluded.${c}`).join(", "),
  );
  const count = env.DB.prepare(
    "INSERT INTO requests (install_id, day, n) VALUES (?, ?, 1) ON CONFLICT (install_id, day) DO UPDATE SET n = n + 1",
  ).bind(body.install_id, day);
  await env.DB.batch([count, ...body.marks.map((m: any) =>
    insert.bind(body.install_id, ...FIELDS.map((f) => m[f]), body.helper_version, now))]);
  return reply(200, { stored: body.marks.length });
}

const admin = (request: Request, env: Env) =>
  !!env.ADMIN_TOKEN && request.headers.get("Authorization") === `Bearer ${env.ADMIN_TOKEN}`;

// The first bad part of an uploaded analysis, or null.
function invalidAnalysis(body: any, video: string, lang: string): string | null {
  if (!body || typeof body !== "object" || !keys(body, ["install_id", "analysis"])) return "fields";
  if (typeof body.install_id !== "string" || !UUID.test(body.install_id)) return "install_id";
  const a = body.analysis;
  if (!a || typeof a !== "object" || Object.keys(a).some((k) => !(k in ANALYSIS)) || REQUIRED.some((k) => !(k in a))) {
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

  const now = new Date().toISOString();
  const day = now.slice(0, 10);
  const used = await env.DB.prepare("SELECT n FROM uploads WHERE install_id = ? AND day = ?").bind(body.install_id, day).first();
  if (used && Number(used.n) >= DAILY_UPLOADS) return reply(429, { error: `over ${DAILY_UPLOADS} uploads today` });
  const count = env.DB.prepare(
    "INSERT INTO uploads (install_id, day, n) VALUES (?, ?, 1) ON CONFLICT (install_id, day) DO UPDATE SET n = n + 1",
  ).bind(body.install_id, day);

  const model = body.analysis.readers.parts.model ?? null;
  const stored = await env.DB.prepare("SELECT rank FROM analyses WHERE video_id = ? AND lang = ?").bind(video, lang).first();
  if (stored && rank(model) <= Number(stored.rank)) {
    await env.DB.batch([count]);
    return reply(409, { error: "a whole analysis by an equal or better model is kept" });
  }
  // Only the owner's own upload is served at once: anyone can make an install id, so a stranger's flags wait.
  if (!admin(request, env)) {
    await env.DB.batch([count, env.DB.prepare(
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
  await env.DB.batch([count, save]);
  return reply(stored ? 200 : 201, { stored: true });
}

// The owner's review of a pending upload: approve serves the best model's, newest first; both clear the pending ones.
async function review(request: Request, env: Env, video: string, lang: string, action: string): Promise<Response> {
  if (request.method !== "POST") return reply(405, { error: "method not allowed" });
  if (!admin(request, env)) return reply(401, { error: "unauthorized" });
  const row = await env.DB.prepare(
    "SELECT install_id, analysis, model, rank FROM pending WHERE video_id = ? AND lang = ? " +
      "ORDER BY rank DESC, received_at DESC LIMIT 1",
  ).bind(video, lang).first();
  if (!row) return reply(404, { error: "nothing pending" });
  const clear = env.DB.prepare("DELETE FROM pending WHERE video_id = ? AND lang = ?").bind(video, lang);
  if (action === "reject") {
    await env.DB.batch([clear]);
    return reply(200, { rejected: true });
  }
  const serve = env.DB.prepare(
    "INSERT INTO analyses (video_id, lang, analysis, model, rank, install_id, received_at) VALUES (?, ?, ?, ?, ?, ?, ?) " +
      "ON CONFLICT (video_id, lang) DO UPDATE SET analysis = excluded.analysis, model = excluded.model, " +
      "rank = excluded.rank, install_id = excluded.install_id, received_at = excluded.received_at",
  ).bind(video, lang, row.analysis, row.model, row.rank, row.install_id, new Date().toISOString());
  await env.DB.batch([serve, clear]);
  return reply(200, { approved: true });
}

async function listPending(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") return reply(405, { error: "method not allowed" });
  if (!admin(request, env)) return reply(401, { error: "unauthorized" });
  const { results } = await env.DB.prepare(
    "SELECT video_id, lang, model, json_array_length(analysis, '$.flags') AS flags, install_id, received_at " +
      "FROM pending ORDER BY received_at",
  ).all();
  return reply(200, { rows: results });
}

async function analyses(request: Request, env: Env, url: URL, video: string, action?: string): Promise<Response> {
  const lang = url.searchParams.get("lang") ?? "";
  if (!VIDEO.test(video) || !["es", "en"].includes(lang)) return reply(400, { error: "bad video or lang" });
  if (action) return review(request, env, video, lang, action);
  if (request.method === "PUT") return share(request, env, video, lang);
  if (request.method === "GET") {
    const row = await env.DB.prepare("SELECT analysis FROM analyses WHERE video_id = ? AND lang = ?").bind(video, lang).first();
    return row
      ? new Response(String(row.analysis), { headers: { "Content-Type": "application/json" } })
      : reply(404, { error: "not shared" });
  }
  if (request.method === "DELETE") {
    if (!admin(request, env)) return reply(401, { error: "unauthorized" });
    await env.DB.batch([env.DB.prepare("DELETE FROM analyses WHERE video_id = ? AND lang = ?").bind(video, lang)]);
    return reply(200, { deleted: true });
  }
  return reply(405, { error: "method not allowed" });
}

async function read(url: URL, request: Request, env: Env): Promise<Response> {
  if (!admin(request, env)) return reply(401, { error: "unauthorized" });
  const since = url.searchParams.get("since") ?? "";
  const { results } = await env.DB.prepare(
    `SELECT install_id, helper_version, received_at, ${FIELDS.join(", ")} FROM marks WHERE received_at > ? ` +
      "ORDER BY received_at, install_id, video_id, flag_id",
  ).bind(since).all();
  return reply(200, { rows: results });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/analyses") return listPending(request, env);
    const shared = url.pathname.match(/^\/analyses\/([^/]+?)(?:\/(approve|reject))?$/);
    if (shared) return analyses(request, env, url, shared[1], shared[2]);
    if (url.pathname !== "/marks") return reply(404, { error: "not found" });
    if (request.method === "POST") return store(request, env);
    if (request.method === "GET") return read(url, request, env);
    return reply(405, { error: "method not allowed" });
  },
};
