import { HUES, look, TEXT_1, TEXT_2, title, verdict, type Flag, type FlagFile, type Look } from "./flags";
import { browserLang, TEXTS, type Lang, type Words } from "./texts";

const ON_PLAYER = 0.8;
const SHOW_FOR = 8;
// A context chip stays long enough to read at about 15 characters a second, between 8 and 20 seconds, and
// LINGER seconds more after the mouse leaves it.
const READ_CHARS_PER_S = 15;
const READ_MAX = 20;
const LINGER = 3;
export const SHOWN_TYPES = ["fallacy", "inaccuracy", "question", "contradiction", "context"];

/** A flag reaches the player in normal playback only at or above the bar of its type. */
export const onPlayer = (f: Flag) => f.on_player ?? f.confidence >= ON_PLAYER;

/** The viewer's choices from the ⚙ of the panel. They persist in chrome.storage.local when it exists. `lang` null
 * follows the browser. */
export const settings = {
  size: "M" as "S" | "M" | "L", side: "right" as "left" | "right", quiet: false, lang: null as Lang | null,
};
export type Settings = typeof settings;
export const ZOOM = { S: "0.85", M: "1", L: "1.25" };
const QUIET = 0.9;

// One glass surface (.fc-s) for the card, the chip, the feed and the buttons. Colour sits only on the verdict.
// Host Grotesk ships with the extension (fonts/font.css); system-ui shows until it loads.
const STYLE = `
.fc-layer{--t1:${TEXT_1};--t2:${TEXT_2};--t3:rgba(214,219,227,.55);--bone:#E6DCC4;--e:cubic-bezier(.2,.8,.2,1);
  font:450 13px/1.4 "Host Grotesk",system-ui,sans-serif;color:var(--t1);-webkit-font-smoothing:antialiased}
:where(.fc-layer) button{font:inherit;color:inherit;border:0;background:none;padding:0;cursor:pointer}
.fc-layer [hidden]{display:none !important}
.fc-s{box-sizing:border-box;position:relative;background:rgba(11,14,21,.8);backdrop-filter:blur(32px) saturate(.5);
  box-shadow:0 0 0 .5px rgba(255,255,255,.1),inset 0 .5px 0 rgba(255,255,255,.07),0 2px 4px rgba(0,0,0,.18),0 12px 32px -8px rgba(0,0,0,.55)}
.fc-s::before{content:"";position:absolute;left:12%;right:0;top:0;height:1px;pointer-events:none;
  background:linear-gradient(90deg,rgba(255,255,255,0),rgba(255,247,230,.32) 78%,rgba(255,255,255,0))}
.fc-ic{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
.fc-dot{width:16px;height:16px;flex-shrink:0;background:no-repeat center/16px 16px}
.fc-num,.fc-m{font-variant-numeric:tabular-nums}
.fc-m{color:var(--t3)}
.fc-fact{width:360px;margin-top:8px;padding:14px 16px 12px;border-radius:14px;pointer-events:auto;flex:0 1 auto;min-height:0;overflow-y:auto;scrollbar-width:thin;overscroll-behavior:contain}
.fc-hd{display:flex;align-items:center;gap:8px;min-height:22px}
.fc-hd b{font-weight:550}
.fc-conf{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--t2);white-space:nowrap}
.fc-slats{display:flex;gap:2px}
.fc-slats i{width:6px;height:12px;background:rgba(255,255,255,.2);clip-path:polygon(3.5px 0,100% 0,2.5px 100%,0 100%)}
.fc-row .fc-slats i{width:5px;height:10px;clip-path:polygon(2.5px 0,100% 0,1.5px 100%,0 100%)}
.fc-ibs{display:flex;gap:2px;margin:0 -6px 0 6px}
.fc-ib{width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:7px;font-size:15px;color:var(--t3)}
.fc-ib:hover,.fc-ib.on{color:var(--t1);background:rgba(255,255,255,.07)}
.fc-fault{position:relative;height:6px;margin:12px -16px 0;pointer-events:none}
.fc-fault i{position:absolute;height:1px}
.fc-fault i:nth-child(1){left:0;top:5px;width:104px;transform-origin:100% 0;background:linear-gradient(90deg,rgba(255,247,230,0),rgba(255,247,230,.22))}
.fc-fault i:nth-child(2){left:104px;top:5px;width:7.07px;transform-origin:0 0;transform:rotate(-45deg);background:rgba(255,247,230,.42)}
.fc-fault i:nth-child(3){left:109px;right:0;top:0;transform-origin:0 0;background:linear-gradient(90deg,rgba(255,247,230,.42),rgba(255,247,230,.12))}
.fc-enter{animation:fc-enter 240ms var(--e) both}
.fc-enter .fc-fault i:nth-child(odd){animation:fc-draw 320ms var(--e) 240ms both}
@keyframes fc-enter{from{opacity:0;filter:blur(4px);transform:translateY(4px)}}
@keyframes fc-draw{from{transform:scaleX(0)}}
.fc-who{margin-top:12px;font-size:12.5px;color:var(--t3)}
.fc-q{margin-top:4px;font-size:15px;line-height:1.47;color:var(--bone)}
.fc-was{margin-top:4px;line-height:1.47;color:var(--t2)}
.fc-was a,.fc-ft a{color:var(--t1)}
.fc-bd{margin-top:10px;line-height:1.6;color:var(--t2)}
.fc-ft{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px;font-size:12.5px;color:var(--t2)}
.fc-ft summary{display:inline-flex;align-items:center;gap:6px;cursor:pointer;list-style:none}
.fc-ft summary::-webkit-details-marker{display:none}
.fc-ft summary .fc-ic{width:13px;height:13px;color:var(--t3)}
.fc-ft details[open]{order:1;flex-basis:100%}
.fc-ft details div{margin-top:6px;line-height:1.5}
.fc-ref a{color:var(--t1);text-decoration:underline;text-decoration-color:rgba(255,255,255,.3);text-underline-offset:2px}
.fc-ref .fc-ic{display:inline-block;width:11px;height:11px;margin-left:2px;vertical-align:-1px;color:var(--t3)}
.fc-marks{display:flex;flex-basis:100%;order:2;align-items:center;gap:8px;margin-top:2px;padding-top:12px;
  border-top:.5px solid rgba(255,255,255,.08);white-space:nowrap}
.fc-ask{margin-right:auto;font-size:13px;font-weight:550;color:var(--t1)}
.fc-btn{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 10px;border-radius:8px;font-size:12.5px;
  color:var(--t2);box-shadow:0 0 0 .5px rgba(255,255,255,.12)}
.fc-btn:hover,.fc-btn.on{color:var(--t1);background:rgba(255,255,255,.08);
  box-shadow:0 0 0 .5px rgba(255,255,255,.16),inset 0 .5px 0 rgba(255,255,255,.08)}
.fc-vote{display:inline-flex;align-items:center;gap:7px;height:34px;padding:0 14px;border-radius:10px;font-size:13.5px;
  font-weight:550;color:var(--t1);background:rgba(255,255,255,.07);transition:background .15s,box-shadow .15s}
.fc-vote:hover{background:rgba(255,255,255,.12)}
.fc-yes:hover{box-shadow:0 0 0 1px rgba(127,214,194,.45),inset 0 .5px 0 rgba(255,255,255,.1)}
.fc-no:hover{box-shadow:0 0 0 1px rgba(244,154,156,.45),inset 0 .5px 0 rgba(255,255,255,.1)}
.fc-marks input{flex:1;min-width:0;height:26px;padding:0 8px;border:0;border-radius:8px;outline:none;font:inherit;color:var(--t1);
  background:rgba(255,255,255,.06);box-shadow:0 0 0 .5px rgba(255,255,255,.16)}
.fc-link{text-decoration:underline}
.fc-nit{padding:10px 14px 10px;border:.5px solid;font-size:12px}
.fc-nit .fc-q{font-size:13px}
.fc-nit .fc-fault{margin:10px -14px 0}
.fc-chip{display:flex;align-items:center;gap:9px;width:max-content;max-width:520px;margin-top:8px;padding:8px 14px 8px 12px;font-size:13px;border-radius:10px;overflow:hidden;pointer-events:auto;cursor:pointer}
.fc-chip:hover .fc-life{animation-play-state:paused}
.fc-chip .fc-k{white-space:nowrap}
.fc-life{position:absolute;left:14px;right:14px;bottom:0;height:1px;transform-origin:0 0;animation:fc-life linear both;
  background:linear-gradient(90deg,rgba(255,247,230,0),rgba(255,247,230,.4))}
@keyframes fc-life{to{transform:scaleX(0)}}
.fc-tog{display:inline-flex;align-items:center;gap:8px;height:30px;padding:0 11px;border-radius:10px;font-size:12.5px;color:var(--t2);pointer-events:auto}
.fc-tog:hover{color:var(--t1)}
.fc-tog .fc-n{color:var(--t3)}
.fc-panel{position:absolute;right:12px;top:12px;bottom:112px;width:372px;display:flex;flex-direction:column;border-radius:14px;overflow:hidden;pointer-events:auto}
.fc-fh{padding:14px 16px 0}
.fc-t{display:flex;align-items:center;gap:8px;height:24px;font-size:14px;font-weight:550}
.fc-cnt{display:inline-flex;align-items:center;height:18px;padding:0 6px;border-radius:5px;background:rgba(255,255,255,.08);font-size:11.5px;font-weight:450}
.fc-t .fc-btn{margin-left:auto;height:24px;font-weight:450;font-size:12px}
.fc-t .fc-ib{font-weight:450}
.fc-t .fc-ib:last-child{margin-right:-6px}
.fc-flt{display:flex;flex-wrap:wrap;gap:2px;margin:12px 0 0 -4px}
.fc-flt button{display:inline-flex;align-items:center;gap:5px;height:26px;padding:0 9px;border-radius:999px;font-size:12px;color:var(--t2)}
.fc-flt button.on{color:var(--t1);background:rgba(255,255,255,.08);box-shadow:0 0 0 .5px rgba(255,255,255,.12),inset 0 .5px 0 rgba(255,255,255,.08)}
.fc-n{color:var(--t2);font-size:12px}
.fc-flt .fc-dot{width:14px;height:14px;background-size:14px 14px}
.fc-panel .fc-fault{margin:12px 0 0;flex-shrink:0}
.fc-list{position:relative;flex:1;overflow-y:auto;padding:4px 8px 8px;scrollbar-width:none;
  mask-image:linear-gradient(to bottom,transparent,#000 56px,#000 calc(100% - 24px),transparent)}
.fc-row{padding:9px 10px;border-radius:10px;cursor:pointer}
.fc-row:hover{background:rgba(255,255,255,.04)}
.fc-rh{display:flex;align-items:center;gap:7px;min-height:18px;font-size:12px}
.fc-rh b{font-weight:550}
.fc-rq{margin-top:4px;padding-left:13px;line-height:1.45;color:var(--t2)}
/* A context entity takes one line: it does not compete with the claims. */
.fc-one{display:flex;align-items:center;gap:7px;padding:6px 10px;font-size:12px}
.fc-one .fc-e{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12.5px}
.fc-nowtag{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--t3)}
.fc-live{width:6px;height:6px;border-radius:50%;background:#ECE9E1;animation:fc-pulse 2.4s ease-in-out infinite}
@keyframes fc-pulse{50%{opacity:.35}}
.fc-x{margin-top:8px;padding-left:13px;font-size:12.5px;line-height:1.55;color:var(--t2)}
.fc-rft{display:flex;align-items:center;gap:6px;margin-top:8px;padding-left:13px;font-size:12px;color:var(--t2)}
.fc-rft a{display:inline-flex;align-items:center;gap:6px;color:inherit;text-decoration:none}
.fc-rft .fc-ic{width:12px;height:12px;color:var(--t3)}
.fc-rft .fc-conf{color:var(--t3)}
.fc-jump{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);display:inline-flex;align-items:center;gap:7px;
  height:28px;padding:0 12px;border-radius:999px;font-size:12px;white-space:nowrap}
.fc-jump .fc-ic{width:13px;height:13px}
.fc-why{margin-top:4px;padding-left:13px;font-size:12px;color:var(--t3)}
.fc-one{flex-wrap:wrap}
.fc-one .fc-why{flex-basis:100%;margin-top:0;padding-left:23px}
.fc-past{opacity:.72}
.fc-dropped{margin-top:6px}
.fc-dropped summary{padding:8px 10px;font-size:12px;color:var(--t3);cursor:pointer}
.fc-now{background:rgba(255,255,255,.055);box-shadow:inset 0 .5px 0 rgba(255,255,255,.08),0 0 0 .5px rgba(255,255,255,.08)}
.fc-now .fc-rq{color:var(--bone)}
.fc-settings{margin-top:10px;padding:8px 10px;border-radius:10px;background:rgba(255,255,255,.04);font-size:12px;color:var(--t2)}
.fc-settings>div,.fc-settings label{display:flex;align-items:center;gap:4px;margin-bottom:6px}
.fc-settings>div>span{width:60px}
.fc-settings .fc-btn{height:22px;padding:0 8px}
.fc-strip{position:absolute;left:12px;right:12px;bottom:52px;height:18px}
.fc-analysed,.fc-pending{position:absolute;top:7.5px;height:3px;border-radius:2px;background:rgba(255,255,255,.16)}
.fc-pending{background:rgba(255,255,255,.07)}
.fc-done .fc-analysed{background:none}
.fc-tip{position:absolute;bottom:22px;transform:translateX(-50%);display:inline-flex;align-items:center;gap:8px;height:28px;
  padding:0 10px;border-radius:10px;font-size:12.5px;white-space:nowrap}
.fc-tip .fc-m{color:var(--t3)}
.fc-mark{position:absolute;top:50%;transform:translate(-50%,-50%);border-radius:50%;background:no-repeat center/16px 16px;
  box-shadow:0 0 0 1.5px rgba(10,14,21,.7);cursor:pointer;pointer-events:auto}
/* Like YouTube's own bar, the strip and the Avisos button show only while the player shows its controls. */
.fc-strip,.fc-panel-tab{transition:opacity .25s}
.ytp-autohide .fc-strip,.ytp-autohide .fc-panel-tab{opacity:0;pointer-events:none}
@media (prefers-reduced-motion:reduce){.fc-layer *{animation:none !important;transition:none !important}}
`;

// Stroke icons from the design boards, on a 16 px grid.
const ICONS = {
  pin: "M6 2.5h4M7 2.5v4L4.5 9h7L9 6.5v-4M8 9v4.5",
  x: "M4.5 4.5l7 7M11.5 4.5l-7 7",
  arrow: "M5 11l6-6M6 5h5v5",
  down: "M8 3v9.5M4 8.5l4 4 4-4",
};

export function icon(name: keyof typeof ICONS): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("class", "fc-ic");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[name]);
  svg.append(path);
  return svg;
}

/** The interface language: the one picked in ⚙, else the browser's. */
export const lang = (): Lang => settings.lang ?? browserLang();
export const words = (): Words => TEXTS[lang()];

export function setSettings(change: Partial<Settings>, layer: HTMLElement) {
  Object.assign(settings, change);
  // No extension storage, or an extension reloaded under this page: the settings stay in memory.
  try { chrome.storage.local.set({ settings }).catch(() => {}); } catch { /* as above */ }
  layer.dispatchEvent(new Event("fc-settings"));
}

/** How long a flag stays on the player: a card SHOW_FOR seconds, a context chip its reading time. */
const seconds = (f: Flag) => f.type === "context"
  ? Math.min(READ_MAX, Math.max(SHOW_FOR, (f.quote.length + f.reason.length) / READ_CHARS_PER_S))
  : SHOW_FOR;

/** The normal display rule: a flag shows on the player in its own seconds, without a pin. */
export const shows = (f: Flag) =>
  SHOWN_TYPES.includes(f.type) && onPlayer(f) && verdict(f) !== "drop" && (!settings.quiet || f.confidence >= QUIET);

export type OnMark = (flag: Flag, verdict: "correct" | "unfair", reason: string) => void;

export function button(text: string, onClick: () => void, className = "fc-btn"): HTMLButtonElement {
  const b = document.createElement("button");
  b.className = className;
  b.textContent = text;
  b.addEventListener("click", onClick);
  return b;
}

export function div(className: string, text?: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

export function span(className: string, text?: string): HTMLSpanElement {
  const el = document.createElement("span");
  el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

/** The verdict disc. */
export function dot(l: Look): HTMLElement {
  const el = span("fc-dot");
  el.style.backgroundImage = l.dot;
  return el;
}

/** Five slats lit in the verdict hue, then the percent. */
export function confidence(flag: Flag, l: Look): HTMLElement {
  const percent = `${Math.round(flag.confidence * 100)}%`;
  const el = span("fc-conf fc-num");
  el.title = `${words().confidence} ${percent}`;
  const slats = span("fc-slats");
  const lit = Math.round(flag.confidence * 5);
  for (let i = 0; i < 5; i++) {
    const slat = document.createElement("i");
    if (i < lit) slat.style.background = l.color;
    slats.append(slat);
  }
  el.append(slats, percent);
  return el;
}

/** The light line of the panel: a flat ray that steps once at 45°. */
export const fault = () => {
  const el = div("fc-fault");
  el.append(document.createElement("i"), document.createElement("i"), document.createElement("i"));
  return el;
};

function marks(flag: Flag, onMark: OnMark, video: HTMLVideoElement): HTMLElement {
  const w = words();
  const row = div("fc-marks");
  const done = (text: string) => row.replaceChildren(span("", text));
  // The video waits while the person writes the reason, and plays on after only if it was playing.
  const unfair = () => {
    const playing = !video.paused;
    if (playing) video.pause();
    const resume = () => { if (playing) video.play(); };
    const input = document.createElement("input");
    input.placeholder = w.why;
    const save = () => { onMark(flag, "unfair", input.value); done(w.markedUnfair); resume(); };
    const cancel = () => { ask(); resume(); };
    // YouTube turns keys into player shortcuts (k pauses, f goes full screen); keep them in the field.
    for (const type of ["keydown", "keypress", "keyup"]) {
      input.addEventListener(type, (e) => {
        e.stopPropagation();
        if (type !== "keydown") return;
        if ((e as KeyboardEvent).key === "Enter") save();
        if ((e as KeyboardEvent).key === "Escape") cancel();
      });
    }
    row.replaceChildren(input, button(w.save, save), button(w.cancel, cancel));
    input.focus();
  };
  // "¿Es justo este aviso?" with two large glass buttons: ✓ in cyan, ✗ in rose.
  const vote = (glyph: string, color: string, text: string, className: string, onClick: () => void) => {
    const b = button("", onClick, `fc-vote fc-s ${className}`);
    const sign = span("", glyph);
    sign.style.color = color;
    b.append(sign, ` ${text}`);
    return b;
  };
  const ask = () => row.replaceChildren(span("fc-ask", w.ask),
    vote("✓", HUES.ok.text, w.agree, "fc-yes", () => { onMark(flag, "correct", ""); done(w.markedCorrect); }),
    vote("✗", HUES.er.text, w.disagree, "fc-no", unfair));
  // A card the person marked before shows that mark; "cambiar" asks again.
  if (flag.mark) {
    row.replaceChildren(`${w.youMarked}: ${flag.mark === "correct" ? `✓ ${w.agree}` : `✗ ${w.disagree}`}`,
      button(w.change, ask, "fc-link"));
  } else {
    ask();
  }
  return row;
}

/** 75 → "1:15"; 3725 → "1:02:05". */
export function minute(t: number): string {
  const s = Math.floor(t);
  const two = (n: number) => String(n).padStart(2, "0");
  const h = Math.floor(s / 3600);
  return h ? `${h}:${two(Math.floor(s / 60) % 60)}:${two(s % 60)}` : `${Math.floor(s / 60)}:${two(s % 60)}`;
}

/** "2023-04" → "abril de 2023" or "April 2023"; a bare year stays as it is. */
function month(made: string, w: Words): string {
  const [year, m] = made.split("-");
  return m ? w.monthOf(w.months[Number(m) - 1], year) : year;
}

/** Long details that the person opens on demand, under "N fuentes ↗". */
function details(flag: Flag): HTMLElement | null {
  const w = words();
  // Each line carries the links of the outlets it names; a source no line names gets a line of its own.
  const lines: HTMLElement[] = [];
  const used = new Set<string>();
  const outlet = (publisher: string) => publisher.split(" (")[0].trim().toLowerCase();
  const link = (s: Flag["sources"][number]) => Object.assign(document.createElement("a"), {
    href: s.url, target: "_blank", rel: "noopener", textContent: s.publisher, title: s.date,
  });
  const line = (text: string) => {
    const ref = div("fc-ref", text);
    for (const s of flag.sources) {
      if (!text.toLowerCase().includes(outlet(s.publisher))) continue;
      ref.append(" ", link(s), icon("arrow"));
      used.add(s.url);
    }
    lines.push(ref);
  };
  if (flag.promise) {
    const p = flag.promise;
    line(w.promised(month(p.made, w), p.figure, p.deadline, w.status[p.status]));
  }
  for (const m of flag.measures ?? []) line(`${m.name}: ${m.value} (${m.source})`);
  if (flag.controversy) line(`${w.controversy}: ${flag.controversy}`);
  if (flag.note) line(`${w.updated}: ${flag.note}`);
  for (const s of flag.sources) {
    if (used.has(s.url)) continue;
    const ref = div("fc-ref");
    ref.append(link(s), ` · ${s.date}`, icon("arrow"));
    lines.push(ref);
  }
  if (!lines.length) return null;
  const box = document.createElement("details");
  const summary = document.createElement("summary");
  const n = flag.sources.length;
  summary.append(n ? w.sources(n) : w.details, icon("arrow"));
  box.append(summary, ...lines);
  return box;
}

function card(flag: Flag, video: HTMLVideoElement, pinned: boolean, pin: () => void, close: () => void, onMark?: OnMark): HTMLElement {
  const w = words();
  const l = look(flag);
  const el = div("fc-card fc-s fc-fact");
  const head = div("fc-hd");
  const name = document.createElement("b");
  name.textContent = title(flag, lang());
  name.style.color = l.word;
  // The pin keeps the card on the player; on a pinned card it closes the card, as the ✕ does.
  const pinButton = button("", pin, `fc-ib fc-pin${pinned ? " on" : ""}`);
  pinButton.append(icon("pin"));
  pinButton.dataset.pinned = String(pinned);
  pinButton.title = pinned ? w.close : w.pin;
  const closeButton = button("", close, "fc-ib fc-close");
  closeButton.append(icon("x"));
  closeButton.title = w.close;
  const icons = span("fc-ibs");
  icons.append(pinButton, closeButton);
  head.append(name, span("fc-m", minute(flag.t)), confidence(flag, l), icons);
  el.append(head, fault());
  const nitpick = verdict(flag) === "nitpick";
  // A nitpick is a minor correction: a smaller card with a neutral ring.
  if (nitpick) {
    el.classList.add("fc-nit");
    el.style.borderColor = "rgba(226,231,238,.22)";
  }
  const speaker = flag.judge?.speaker ?? flag.speaker;
  if (speaker) el.append(div("fc-who", speaker));
  // A question card quotes the question; the flag itself sits on the end of the answer.
  const quote = div("fc-q", `«${flag.type === "question" && flag.related ? flag.related.quote : flag.quote}»`);
  // A contradiction card quotes the earlier statement with its minute, then the new one. An earlier
  // public statement (no minute) shows its date and its source as a link.
  if (flag.type === "contradiction" && flag.related) {
    const { t, quote: said, date, source } = flag.related;
    const earlier = div("fc-was");
    if (t === null && source) {
      const link = Object.assign(document.createElement("a"), { href: source.url, target: "_blank", textContent: source.publisher });
      earlier.append(`${w.before} (${date}, `, link, `): «${said}»`);
    } else {
      earlier.textContent = `${w.before} (${minute(t!)}): «${said}»`;
    }
    quote.textContent = `${w.now}: ${quote.textContent}`;
    el.append(earlier);
  }
  el.append(quote, div("fc-bd", nitpick ? flag.judge!.reason : flag.reason));
  const foot = div("fc-ft");
  const more = details(flag);
  if (more) foot.append(more);
  if (onMark) foot.append(marks(flag, onMark, video));
  if (foot.childElementCount) el.append(foot);
  return el;
}

/** A context flag is not a claim about the speaker: a chip with nothing to mark. Its line drains over its seconds. */
function chip(flag: Flag, left: number | null): HTMLElement {
  const el = div("fc-card fc-pill fc-s fc-chip");
  const l = look(flag);
  const kind = span("fc-k", words().labels[flag.label] ?? flag.label);
  kind.style.color = l.word;
  el.append(dot(l), kind, span("", `${flag.quote} — ${flag.reason}`));
  if (left !== null) {
    const life = span("fc-life");
    life.style.animationDuration = `${left}s`;
    el.append(life);
  }
  return el;
}

/**
 * Draws the flags of `getFlags()` on the player while `video` plays. `show` pins a flag, also one under the bar.
 * A pinned card stays until its pin or ✕ closes it; a pinned chip closes on a click.
 */
export function mountOverlay(
  player: HTMLElement,
  video: HTMLVideoElement,
  getFlags: () => FlagFile | null,
  onMark?: OnMark,
): { layer: HTMLElement; show: (flag: Flag) => void; unmount: () => void } {
  const layer = document.createElement("div");
  layer.className = "fc-layer";
  layer.style.cssText = "position:absolute;inset:0;z-index:60;pointer-events:none";
  const style = document.createElement("style");
  style.textContent = STYLE;
  const cards = document.createElement("div");
  cards.style.cssText = "position:absolute;top:12px;bottom:72px;display:flex;flex-direction:column";
  const pills = document.createElement("div");
  pills.style.cssText = "position:absolute;left:12px;bottom:72px";
  layer.append(style, cards, pills);
  player.appendChild(layer);
  // The layer covers the picture, not the player: in full screen on a 16:10 screen the picture has bars above and below.
  const fit = () => {
    const p = player.getBoundingClientRect(), v = video.getBoundingClientRect();
    const ratio = video.videoWidth / video.videoHeight;
    if (!ratio || !v.width) return;
    const w = Math.min(v.width, v.height * ratio), h = w / ratio;
    Object.assign(layer.style, {
      inset: "auto",
      left: `${v.left - p.left + (v.width - w) / 2}px`,
      top: `${v.top - p.top + (v.height - h) / 2}px`,
      width: `${w}px`,
      height: `${h}px`,
    });
  };
  const resized = new ResizeObserver(fit);
  resized.observe(player);
  video.addEventListener("loadedmetadata", fit);
  fit();
  const shown = { cards: "", pills: "" };
  let before = new Set<string>();
  const pinned = new Set<string>();
  const closed = new Set<string>();
  // What is under the mouse stays. The containers outlive a redraw, so their leave always comes.
  const held = new Set<string>();
  const lingerUntil = new Map<string, number>();
  const hold = (box: HTMLElement, linger: number) => {
    box.addEventListener("pointerenter", () => { for (const el of box.children) held.add((el as HTMLElement).dataset.id!); });
    box.addEventListener("pointerleave", () => {
      for (const id of held) lingerUntil.set(id, video.currentTime + linger);
      held.clear();
      draw();
    });
  };
  hold(cards, 0);
  hold(pills, LINGER);

  // A click on the pin or the ✕ is the person's choice, so it also ends the mouse's hold on that card.
  const toggle = (flag: Flag) => {
    if (pinned.delete(flag.id)) {
      closed.add(flag.id);
      held.delete(flag.id);
    } else {
      pinned.add(flag.id);
    }
    draw();
  };
  const close = (flag: Flag) => {
    pinned.delete(flag.id);
    held.delete(flag.id);
    closed.add(flag.id);
    draw();
  };

  const draw = () => {
    cards.style.zoom = pills.style.zoom = ZOOM[settings.size];
    const side = layer.classList.contains("fc-panel-open") ? "left" : settings.side;
    cards.style.left = side === "left" ? "12px" : "";
    cards.style.right = side === "right" ? "12px" : "";
    const now = video.currentTime;
    const flags = getFlags()?.flags ?? [];
    const due = (f: Flag) => shows(f) && f.t <= now && now < f.t + seconds(f);
    // A closed card comes back only on its next pass.
    for (const id of closed) if (!flags.some((f) => f.id === id && due(f))) closed.delete(id);
    const visible = flags
      .filter((f) => pinned.has(f.id) || held.has(f.id) || now < (lingerUntil.get(f.id) ?? 0) || (due(f) && !closed.has(f.id)))
      .sort((a, b) => a.t - b.t);
    const key = (fs: Flag[]) => lang() + fs.map((f) => `${f.id}${pinned.has(f.id) ? "*" : ""}`).join("|");
    const facts = visible.filter((f) => f.type !== "context");
    const chips = visible.filter((f) => f.type === "context");
    // Only a flag that was not on the player before plays the entry.
    const enter = (f: Flag, el: HTMLElement) => {
      if (!before.has(f.id)) el.classList.add("fc-enter");
      el.dataset.id = f.id;
      return el;
    };
    // Cards under the mouse are not redrawn: the person may be typing a reason in one.
    const cardsHeld = facts.some((f) => held.has(f.id));
    if (!cardsHeld && key(facts) !== shown.cards) {
      shown.cards = key(facts);
      cards.replaceChildren(...facts.map((f) =>
        enter(f, card(f, video, pinned.has(f.id), () => toggle(f), () => close(f), onMark))));
    }
    if (key(chips) !== shown.pills) {
      shown.pills = key(chips);
      pills.replaceChildren(...chips.map((f) => {
        const el = enter(f, chip(f, pinned.has(f.id) ? null : Math.max(f.t + seconds(f) - now, LINGER)));
        el.title = pinned.has(f.id) ? words().close : words().pinChip;
        el.addEventListener("click", () => toggle(f));
        return el;
      }));
    }
    before = new Set(visible.map((f) => f.id));
  };
  const render = () => draw();

  try {
    chrome.storage.local.get("settings").then((stored) => {
      Object.assign(settings, stored.settings);
      layer.dispatchEvent(new Event("fc-settings"));
    }, () => { /* the extension was reloaded: keep the defaults */ });
  } catch { /* no extension storage: keep the defaults */ }
  layer.addEventListener("fc-settings", draw);
  video.addEventListener("timeupdate", render);
  video.addEventListener("seeked", render);
  draw();
  return {
    layer,
    show: (flag) => {
      pinned.add(flag.id);
      closed.delete(flag.id);
      draw();
    },
    unmount: () => {
      video.removeEventListener("timeupdate", render);
      video.removeEventListener("seeked", render);
      video.removeEventListener("loadedmetadata", fit);
      resized.disconnect();
      layer.remove();
    },
  };
}
