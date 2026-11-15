"use strict";
(() => {
  // src/sw.ts
  var PORTS = [8765, 8766, 8767, 8768, 8769];
  var port = PORTS[0];
  var known = false;
  var helper = () => `http://127.0.0.1:${port}`;
  var VIDEO_ID = /^[A-Za-z0-9_-]{6,20}$/;
  async function isHelper(p) {
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
        return known = true;
      }
    }
    return known = false;
  }
  async function call(req) {
    if (req.kind === "summary") return chrome.tabs.create({ url: `${helper()}/videos/${req.videoId}/summary` }).then(() => null);
    try {
      const res2 = await send(req);
      if (res2.ok) return await res2.json();
      if (known || await isHelper(port)) {
        known = true;
        return null;
      }
    } catch (e) {
      if (!(e instanceof TypeError || e instanceof SyntaxError)) throw e;
    }
    if (!await find()) throw new TypeError("no fact-checker helper on ports 8765-8769");
    const res = await send(req);
    return res.ok ? res.json() : null;
  }
  function send(req) {
    const HELPER = helper();
    const url = `${HELPER}/videos/${req.videoId}`;
    return req.kind === "share" || req.kind === "provider" ? fetch(`${HELPER}/${req.kind}`) : req.kind === "set-share" ? fetch(`${HELPER}/share`, { method: "POST", body: JSON.stringify({ share: req.share === true }) }) : req.kind === "analyze" ? fetch(
      `${url}?from=${Math.max(0, Math.floor(req.from))}&lang=${req.lang === "en" ? "en" : "es"}`,
      { method: "POST" }
    ) : req.kind === "role" ? fetch(`${url}/people`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: String(req.name), role: req.role === "host" ? "host" : "guest" })
    }) : req.kind === "mark" ? fetch(`${url}/marks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flag_id: String(req.flagId), verdict: req.verdict, reason: String(req.reason).slice(0, 500) })
    }) : fetch(req.kind === "flags" && typeof req.at === "number" ? `${url}?at=${Math.max(0, Math.floor(req.at))}${req.lang ? `&lang=${req.lang === "en" ? "en" : "es"}` : ""}` : url);
  }
  chrome.runtime.onMessage.addListener((req, _sender, sendResponse) => {
    if (!req || !VIDEO_ID.test(req.videoId) || !["analyze", "flags", "mark", "summary", "share", "set-share", "provider", "role"].includes(req.kind)) return;
    call(req).then((data) => sendResponse({ ok: true, data })).catch((e) => sendResponse(e instanceof TypeError ? { ok: false, down: true } : { ok: false, error: String(e) }));
    return true;
  });
})();
