// The helper serves on the first free port of these; /health tells it from another program on the same port.
const PORTS = [8765, 8766, 8767, 8768, 8769];
let port = PORTS[0];
let known = false;
const helper = () => `http://127.0.0.1:${port}`;
const VIDEO_ID = /^[A-Za-z0-9_-]{6,20}$/;

type HelperRequest =
  | { kind: "analyze"; videoId: string; from: number; lang: "es" | "en" }
  | { kind: "flags"; videoId: string; at?: number; lang?: "es" | "en" }
  | { kind: "summary"; videoId: string }
  | { kind: "keys"; videoId: string; lang: "es" | "en" }
  | { kind: "share"; videoId: string }
  | { kind: "provider"; videoId: string }
  | { kind: "set-share"; videoId: string; share: boolean }
  | { kind: "role"; videoId: string; name: string; role: "host" | "guest" }
  | { kind: "mark"; videoId: string; flagId: string; verdict: "correct" | "unfair"; reason: string };

async function isHelper(p: number) {
  try {
    const res = await fetch(`http://127.0.0.1:${p}/health`);
    return res.ok && (await res.json())?.app === "fact-checker";
  } catch {
    return false;
  }
}

async function find() {
  for (const p of PORTS) {
    if (await isHelper(p)) {
      port = p;
      return (known = true);
    }
  }
  return (known = false);
}

// A call goes to the kept port. A refused connection, or an answer that is not the helper's, looks for the helper
// over the five ports and sends the call again; with no helper, fetch's TypeError says it is down.
async function call(req: HelperRequest) {
  // The helper's page shows the image with its alt text under it.
  if (req.kind === "summary") return chrome.tabs.create({ url: `${helper()}/videos/${req.videoId}/summary` }).then(() => null);
  // The helper's key page takes the keys itself: it opens on the port where the helper answers, never on a guess.
  if (req.kind === "keys") {
    if (!(await isHelper(port)) && !(await find())) throw new TypeError("no fact-checker helper on ports 8765-8769");
    return chrome.tabs.create({ url: `${helper()}/keys?lang=${req.lang === "en" ? "en" : "es"}` }).then(() => null);
  }
  try {
    const res = await send(req);
    if (res.ok) return await res.json();
    if (known || (await isHelper(port))) {
      known = true;
      return null;
    }
  } catch (e) {
    if (!(e instanceof TypeError || e instanceof SyntaxError)) throw e;
  }
  if (!(await find())) throw new TypeError("no fact-checker helper on ports 8765-8769");
  const res = await send(req);
  return res.ok ? res.json() : null;
}

function send(req: HelperRequest) {
  const HELPER = helper();
  const url = `${HELPER}/videos/${req.videoId}`;
  return req.kind === "share" || req.kind === "provider"
      ? fetch(`${HELPER}/${req.kind}`)
      : req.kind === "set-share"
      ? fetch(`${HELPER}/share`, { method: "POST", body: JSON.stringify({ share: req.share === true }) })
      : req.kind === "analyze"
      ? fetch(`${url}?from=${Math.max(0, Math.floor(req.from))}&lang=${req.lang === "en" ? "en" : "es"}`,
        { method: "POST" })
      : req.kind === "role"
      ? fetch(`${url}/people`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: String(req.name), role: req.role === "host" ? "host" : "guest" }),
        })
      : req.kind === "mark"
        ? fetch(`${url}/marks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ flag_id: String(req.flagId), verdict: req.verdict, reason: String(req.reason).slice(0, 500) }),
          })
        : fetch(req.kind === "flags" && typeof req.at === "number"
          ? `${url}?at=${Math.max(0, Math.floor(req.at))}${req.lang ? `&lang=${req.lang === "en" ? "en" : "es"}` : ""}`
          : url);
}

chrome.runtime.onMessage.addListener((req: HelperRequest, _sender, sendResponse) => {
  if (!req || !VIDEO_ID.test(req.videoId) || !["analyze", "flags", "mark", "summary", "keys", "share", "set-share", "provider", "role"].includes(req.kind)) return;
  call(req)
    .then((data) => sendResponse({ ok: true, data }))
    // fetch rejects with a TypeError when nothing listens on the helper's port: the content script says so.
    .catch((e) => sendResponse(e instanceof TypeError ? { ok: false, down: true } : { ok: false, error: String(e) }));
  return true;
});
