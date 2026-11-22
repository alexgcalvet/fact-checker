import type { FlagFile } from "./flags";
import { button as textButton, div, lang, mountOverlay, words } from "./overlay";
import { PRIVACY } from "./texts";
import { mountPanel } from "./panel";

const POLL_MS = 3000;

type Reply = { ok: boolean; data?: FlagFile | null; down?: boolean };

// Takes down the current video's layer and stops its polls; set by each start.
let unmount: (() => void) | null = null;

// After the extension is reloaded, this old copy of the script stays in open tabs with no extension behind it.
// It then stops polling, removes its layer and stops following the next video; the reloaded tab gets a new copy.
// Chrome may keep `chrome.runtime.id` on such a copy, so the error message tells too.
async function send(message: object): Promise<Reply | null> {
  try {
    return await chrome.runtime.sendMessage(message);
  } catch (error) {
    if (chrome.runtime?.id && !String(error).includes("context invalidated")) throw error;
    unmount?.();
    unmount = null;
    document.removeEventListener("yt-navigate-finish", start);
    return null;
  }
}

async function start() {
  unmount?.();
  unmount = null;
  const videoId = new URLSearchParams(location.search).get("v");
  const player = document.getElementById("movie_player");
  const video = player?.querySelector("video");
  if (location.pathname !== "/watch" || !videoId || !player || !video) return;
  // An answer for this video that comes after the person moved on is dropped: `alive` is false by then.
  let flags: FlagFile | null = null;
  let poll: number | undefined;
  let alive = true;

  // Nothing is shared before the person answers once: the first mark or analysis asks, and the helper keeps the
  // answer as `share_marks`. The mark or the analysis goes after the answer, so the yes covers it.
  let asking: Promise<void> | null = null;
  const ask = async () => {
    const res = (await send({ kind: "share", videoId })) as { ok: boolean; data?: { share: boolean | null } } | null;
    if (!res?.ok || !res.data) {
      asking = null; // the helper is down: ask again next time
      return;
    }
    if (res.data.share !== null) return;
    const w = words().consent;
    const box = div("fc-consent fc-s");
    box.style.cssText = "position:absolute;left:12px;top:12px;max-width:400px;padding:12px;border-radius:10px;" +
      "font-size:12.5px;line-height:1.5;color:var(--t1);pointer-events:auto;display:flex;flex-direction:column;gap:8px";
    const privacy = Object.assign(document.createElement("a"),
      { href: PRIVACY, target: "_blank", rel: "noopener", textContent: w.privacy });
    privacy.style.color = "inherit";
    const share = await new Promise<boolean>((done) => {
      const answers = div("");
      answers.style.cssText = "display:flex;gap:8px;align-items:center";
      answers.append(textButton(w.yes, () => done(true)), textButton(w.no, () => done(false)), privacy);
      box.append(div("", w.ask), answers);
      overlay.layer.append(box);
    });
    box.remove();
    await send({ kind: "set-share", videoId, share });
  };
  const consent = () => (asking ??= ask());
  const overlay = mountOverlay(player, video, () => flags, (flag, verdict, reason) => {
    // The poll stops once the video is done, so keep the new mark on the flag we already have.
    flag.mark = verdict;
    consent().then(() => send({ kind: "mark", videoId, flagId: flag.id, verdict, reason }));
  });
  const shareReply = async (message: object) => {
    const res = (await send(message)) as { ok: boolean; data?: { share: boolean } } | null;
    return res?.ok && res.data ? res.data.share : null;
  };
  const unmountPanel = mountPanel(overlay.layer, video, () => flags, overlay.show,
    () => send({ kind: "summary", videoId }),
    { get: () => shareReply({ kind: "share", videoId }), set: (on) => shareReply({ kind: "set-share", videoId, share: on }) },
    (name, role) => send({ kind: "role", videoId, name, role }),
    () => send({ kind: "keys", videoId, lang: lang() }));
  unmount = () => { alive = false; clearInterval(poll); unmountPanel(); overlay.unmount(); };
  // The service worker answers `down` when nothing listens on the helper's port: not installed, or not running.
  const notice = div("fc-down fc-s");
  notice.style.cssText = "position:absolute;left:12px;top:12px;max-width:380px;padding:10px 12px;border-radius:10px;" +
    "font-size:12.5px;line-height:1.5;color:var(--t1);pointer-events:auto";
  const down = (res: Reply | null) => {
    if (res?.down) {
      notice.replaceChildren(...words().helperDown.map((text) => div("", text)));
      overlay.layer.append(notice);
    } else {
      notice.remove();
    }
    return Boolean(res?.down);
  };
  // Each poll carries the playback second: the helper analyses only up to 10 minutes ahead of it, and pauses when
  // the polls stop. It also carries the interface language: a video never analysed here may have a shared analysis
  // in that language.
  const refresh = async () => {
    const res = await send({ kind: "flags", videoId, at: video.currentTime, lang: lang() });
    if (!alive) return null;
    down(res);
    if (res?.ok && res.data) {
      flags = res.data;
      overlay.layer.dispatchEvent(new Event("fc-flags")); // a paused video fires no timeupdate
    }
    if (flags && flags.status !== "running") clearInterval(poll);
    return res;
  };
  const follow = () => {
    clearInterval(poll);
    poll = setInterval(refresh, POLL_MS);
    refresh();
  };
  const button = document.createElement("button");
  button.className = "fc-start fc-s fc-tog";
  button.textContent = words().analyze;
  overlay.layer.addEventListener("fc-settings", () => { button.textContent = words().analyze; });
  button.style.cssText = "position:absolute;left:12px;top:12px";
  // Flags that another person's analysis paid for show a small note in place of the button.
  const note = div("fc-shared fc-s fc-m", words().shared);
  note.style.cssText = "position:absolute;left:12px;top:12px;padding:6px 10px;border-radius:8px;font-size:12px";
  overlay.layer.addEventListener("fc-settings", () => { note.textContent = words().shared; });
  // Under the button, what an analysis spends with the provider that reads the parts.
  const spend = div("fc-spend fc-m");
  spend.style.cssText = "position:absolute;left:12px;top:48px;max-width:360px;font-size:12px;line-height:1.4";
  let provider = "";
  const spent = () => { spend.textContent = words().spend[provider] ?? words().spend.api; };
  overlay.layer.addEventListener("fc-settings", () => { if (provider) spent(); });
  // A first look, again every few seconds while the helper is down.
  // An analysis spends Claude tool calls, so it starts only when the person asks; a known video costs nothing.
  const look = async () => {
    const res = await refresh();
    if (!alive || down(res)) return;
    clearInterval(poll);
    const known = flags as FlagFile | null;
    // An analysis stopped by an error can be asked again; one that spent its budget cannot.
    const retry = known?.status === "stopped" && Boolean(known.stop_reason?.startsWith("error"));
    if (!known || retry) {
      overlay.layer.append(button);
      const res = (await send({ kind: "provider", videoId })) as { ok: boolean; data?: { provider: string } } | null;
      provider = res?.ok && res.data ? res.data.provider : "";
      if (provider && button.isConnected) {
        spent();
        overlay.layer.append(spend);
      }
    }
    else if (known.source === "shared") overlay.layer.append(note);
    else if (known.status === "running") follow();
  };
  button.addEventListener("click", async () => {
    button.remove();
    spend.remove();
    await consent();
    // The reasons of the flags come in the interface language.
    const res = await send({ kind: "analyze", videoId, from: video.currentTime, lang: lang() });
    if (!alive) return;
    if (down(res)) {
      poll = setInterval(look, POLL_MS);
      return;
    }
    follow();
  });
  poll = setInterval(look, POLL_MS);
  await look();
}

// YouTube is a single-page app: a new video fires this event instead of a page load.
document.addEventListener("yt-navigate-finish", start);
start();
