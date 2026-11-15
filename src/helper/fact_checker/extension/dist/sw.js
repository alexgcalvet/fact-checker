"use strict";
(() => {
  // src/sw.ts
  var HELPER = "http://127.0.0.1:8765";
  var VIDEO_ID = /^[A-Za-z0-9_-]{6,20}$/;
  async function call(req) {
    const url = `${HELPER}/videos/${req.videoId}`;
    if (req.kind === "summary") return chrome.tabs.create({ url: `${url}/summary` }).then(() => null);
    const res = req.kind === "share" || req.kind === "provider" ? await fetch(`${HELPER}/${req.kind}`) : req.kind === "set-share" ? await fetch(`${HELPER}/share`, { method: "POST", body: JSON.stringify({ share: req.share === true }) }) : req.kind === "analyze" ? await fetch(
      `${url}?from=${Math.max(0, Math.floor(req.from))}&lang=${req.lang === "en" ? "en" : "es"}`,
      { method: "POST" }
    ) : req.kind === "mark" ? await fetch(`${url}/marks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flag_id: String(req.flagId), verdict: req.verdict, reason: String(req.reason).slice(0, 500) })
    }) : await fetch(req.kind === "flags" && typeof req.at === "number" ? `${url}?at=${Math.max(0, Math.floor(req.at))}${req.lang ? `&lang=${req.lang === "en" ? "en" : "es"}` : ""}` : url);
    return res.ok ? res.json() : null;
  }
  chrome.runtime.onMessage.addListener((req, _sender, sendResponse) => {
    if (!req || !VIDEO_ID.test(req.videoId) || !["analyze", "flags", "mark", "summary", "share", "set-share", "provider"].includes(req.kind)) return;
    call(req).then((data) => sendResponse({ ok: true, data })).catch((e) => sendResponse(e instanceof TypeError ? { ok: false, down: true } : { ok: false, error: String(e) }));
    return true;
  });
})();
