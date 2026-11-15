const HELPER = "http://127.0.0.1:8765";
const VIDEO_ID = /^[A-Za-z0-9_-]{6,20}$/;

type HelperRequest =
  | { kind: "analyze"; videoId: string; from: number; lang: "es" | "en" }
  | { kind: "flags"; videoId: string; at?: number; lang?: "es" | "en" }
  | { kind: "summary"; videoId: string }
  | { kind: "share"; videoId: string }
  | { kind: "provider"; videoId: string }
  | { kind: "set-share"; videoId: string; share: boolean }
  | { kind: "mark"; videoId: string; flagId: string; verdict: "correct" | "unfair"; reason: string };

async function call(req: HelperRequest) {
  const url = `${HELPER}/videos/${req.videoId}`;
  // The helper's page shows the image with its alt text under it.
  if (req.kind === "summary") return chrome.tabs.create({ url: `${url}/summary` }).then(() => null);
  const res =
    req.kind === "share" || req.kind === "provider"
      ? await fetch(`${HELPER}/${req.kind}`)
      : req.kind === "set-share"
      ? await fetch(`${HELPER}/share`, { method: "POST", body: JSON.stringify({ share: req.share === true }) })
      : req.kind === "analyze"
      ? await fetch(`${url}?from=${Math.max(0, Math.floor(req.from))}&lang=${req.lang === "en" ? "en" : "es"}`,
        { method: "POST" })
      : req.kind === "mark"
        ? await fetch(`${url}/marks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ flag_id: String(req.flagId), verdict: req.verdict, reason: String(req.reason).slice(0, 500) }),
          })
        : await fetch(req.kind === "flags" && typeof req.at === "number"
          ? `${url}?at=${Math.max(0, Math.floor(req.at))}${req.lang ? `&lang=${req.lang === "en" ? "en" : "es"}` : ""}`
          : url);
  return res.ok ? res.json() : null;
}

chrome.runtime.onMessage.addListener((req: HelperRequest, _sender, sendResponse) => {
  if (!req || !VIDEO_ID.test(req.videoId) || !["analyze", "flags", "mark", "summary", "share", "set-share", "provider"].includes(req.kind)) return;
  call(req)
    .then((data) => sendResponse({ ok: true, data }))
    // fetch rejects with a TypeError when nothing listens on the helper's port: the content script says so.
    .catch((e) => sendResponse(e instanceof TypeError ? { ok: false, down: true } : { ok: false, error: String(e) }));
  return true;
});
