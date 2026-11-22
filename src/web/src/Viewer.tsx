// The viewer of one approved video, as the owner approved it in Claude Design (spec S1, T001): the YouTube embed with
// our own control bar, whose progress bar is the lane of the flags, the title with the AI line, and the panel of flags
// beside it (a side sheet over the video in full screen). The flag being said shows over the video as a card, or a
// folded pill for a context note, unless the viewer turns it off. YouTube's own controls are off, so its full screen
// never hides ours. On a phone (brand spec §19.7) nothing but the bar covers the video: the flag being said shows in
// the "Ahora" strip under it, and a flag opens in a bottom sheet.
import { Fragment, useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore, type MouseEvent, type ReactNode } from "react";
import { litAt } from "../../shared/panel";
import { Actions, useFeedback, type Say } from "./Feedback";
import { half } from "./faces";
import { Footer, SiteBar, type Section } from "./Footer";
import { BigMark, HomeMark } from "./DeFacto";
import { Tips, tip as hint } from "./Tip";
import { Sheet } from "./Sheet";
import { KINDS, kindOf, low, markFor, markOf, MARKS, nitpick, wordColor, type Flag, type Kind, type Mark } from "./marks";
import { TEXTS, type Lang, type Texts } from "./texts";
import { progress, save } from "./watched";

/** The parts of `YT.Player` that the viewer uses (docs/archive/002-…/research/youtube-embed.md). */
export interface Player {
  getCurrentTime(): number;
  getDuration(): number;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  playVideo(): void;
  pauseVideo(): void;
  mute(): void;
  unMute(): void;
  getVolume(): number;
  setVolume(volume: number): void;
  destroy(): void;
}
export type PlayerClass = new (element: HTMLElement, options: object) => Player;

/** The video fields of `GET /api/videos/<id>`. */
export interface Meta {
  video_id: string;
  lang: Lang;
  title: string;
  display_title?: string | null; // the collector's title for the reader
  channel: string;
  duration: number;
  published_at: string | null;
  type: string;
  guests: string[];
  /** The owner swapped the halves of the debate's thumbnail (S11). */
  swap?: boolean;
  prompts?: string | null;
  /** Set when the asked language has no analysis and `lang` is the one served. */
  requested?: Lang;
  /** Each guest's summary (S4), null for an upload before it. */
  summary?: Record<string, Summary> | null;
  /** Each person's role and speech (S5), null for an upload without voice turns. */
  people?: Record<string, { role: string; spoken_s: number; turns: number; longest_s: number }> | null;
  /** The voice turns of the video by person (S5), null likewise. */
  turns?: { start: number; end: number; person: string }[] | null;
}

/** The numbers of a guest's profile card, as `GET /api/videos/<id>` serves them. */
export interface Summary {
  checked: number;
  verdicts: { false: number; misleading: number; nitpick: number; correct: number };
  severity: { serious: number; moderate: number; minor: number };
  devices: { label: string; count: number }[];
  dodged: number;
  partial: number;
  asked: number;
  gravest: string[];
}

const NOT_EMBEDDABLE = [101, 150];
const PLAYING = 1;
const ENDED = 0;
const SAVE_S = 5; // the progress is saved each time the video moves this far
const POLL_MS = 250;
const IDLE_MS = 3000; // while the video plays, the bar hides after this long with no pointer, touch or focus
const SIZES = { M: "A", L: "A+", XL: "A++" };
const ZOOM = { M: 1, L: 1.15, XL: 1.3 };
const LANE_GAP_PX = 12; // marks closer than this share one cluster
const SNAP_PX = 12; // a click this close to a flag goes to it
export const PHONE = "(max-width: 760px)";
// f7 §19.10 §6: a reading page takes its phone layout under 768 px; the viewer keeps its own 760.
export const READING_PHONE = "(max-width: 767px)";
/** A phone held sideways: the video fills the screen (the PhoneFull board); a short laptop window keeps its page. */
const SIDEWAYS = "(pointer: coarse) and (orientation: landscape) and (max-height: 500px)";
// Once closed, the language note stays closed for the session (S4).
const LANG_NOTE = "calvet-lang-note";
const dismissedNote = () => {
  try {
    return sessionStorage.getItem(LANG_NOTE) === "closed";
  } catch {
    return false;
  }
};
const dismissNote = () => {
  try {
    sessionStorage.setItem(LANG_NOTE, "closed");
  } catch { /* storage blocked: the note closes for this page only */ }
};
// The page keeps the last video it showed, so a page that does not exist can lead back to it.
const LAST_VIDEO = "calvet-last-video";

export const clock = (s: number) => {
  s = Math.floor(s);
  const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = s % 60;
  return `${h ? `${h}:${String(m).padStart(2, "0")}` : m}:${String(x).padStart(2, "0")}`;
};
const pct = (t: number, duration: number) => `${(t / duration) * 100}%`;
/** "Ana Pérez (candidata)" → "Ana Pérez": the panel names a speaker without the role. */
export const short = (name: string) => name.replace(/\s*\(.*\)\s*$/, "");
export const role = (name: string) => name.match(/\(([^)]*)\)\s*$/)?.[1];
/** "Ana Pérez (candidata)" → "ana-perez": the last part of a guest's profile address, computed here (spec S5). */
export const slug = (name: string) => short(name).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase()
  .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
export const profilePath = (lang: Lang, video: string, guest: string) => `/${lang}/v/${encodeURIComponent(video)}/${slug(guest)}`;
/** The comparison of a debate's guests (S10): its word in each language; the router takes either. */
export const COMPARE: Record<Lang, string> = { es: "comparar", en: "compare" };
export const comparePath = (lang: Lang, video: string) => `/${lang}/v/${encodeURIComponent(video)}/${COMPARE[lang]}`;

export const useMedia = (media: string) => useSyncExternalStore((change) => {
  const query = matchMedia(media);
  query.addEventListener("change", change);
  return () => query.removeEventListener("change", change);
}, () => matchMedia(media).matches);

export const Chevron = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" /></svg>
);

/** The "i" of the AI line and of "What is a flag?". */
const Info = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.75" fill="none" stroke="currentColor" strokeWidth={1.3} />
    <path d="M8 7.2v4" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" /><circle cx="8" cy="5" r="0.9" fill="currentColor" /></svg>
);

/** A verdict mark as the brand draws it, from 14 px. A Puntualización draws the context mark as an outline (owner, S4);
 * `data-mark` stays the mark. A low-confidence flag draws its mark in the dimmed text colour. */
export function MarkIcon({ mark: kind, size = 16, dim = false }: { mark: Kind; size?: number; dim?: boolean }) {
  const mark = markFor(kind);
  const clip = useId();
  const glyph = { stroke: "var(--st-glyph)", strokeWidth: 1.6, strokeLinecap: "round" } as const;
  const ink = dim ? "var(--t4)" : `var(--st-${mark})`;
  const shapes: Record<Mark, ReactNode> = {
    falso: <><circle cx="8" cy="8" r="7" fill={ink} /><path d="M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8" {...glyph} /></>,
    enganoso: <><circle cx="8" cy="8" r="6.75" fill="none" stroke={ink} strokeWidth={1.5} />
      <path d="M8 4.6v4.2" stroke={ink} strokeWidth={1.6} strokeLinecap="round" /><circle cx="8" cy="11.2" r="0.95" fill={ink} /></>,
    retorica: <><path d="M8 1.6L14.4 8 8 14.4 1.6 8z" fill="none" stroke={ink} strokeWidth={1.5} strokeLinejoin="round" />
      <path d="M5.4 8.6c.9-1.2 1.75-1.2 2.6 0s1.75 1.2 2.6 0" fill="none" stroke={ink} strokeWidth={1.3} strokeLinecap="round" /></>,
    evasiva: <>
      <defs><clipPath id={clip}><rect x="0" y="0" width="8" height="16" /></clipPath></defs>
      <path d="M8 1.75a6.25 6.25 0 0 1 0 12.5" fill="none" stroke={ink} strokeWidth={1.5} />
      <path d="M6 5.9a2 2 0 1 1 3 1.73c-.6.3-1 .8-1 1.4v.6" fill="none" stroke={ink} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="8" cy="11.6" r=".95" fill={ink} /><path d="M8 1a7 7 0 0 0 0 14z" fill={ink} />
      <g clipPath={`url(#${clip})`}>
        <path d="M6 5.9a2 2 0 1 1 3 1.73c-.6.3-1 .8-1 1.4v.6" fill="none" stroke="var(--st-glyph)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="8" cy="11.6" r=".95" fill="var(--st-glyph)" />
      </g></>,
    contexto: <><rect x="1.5" y="1.5" width="13" height="13" rx="3" fill={ink} /><path d="M8 7.2v4.3" {...glyph} />
      <circle cx="8" cy="4.9" r="0.95" fill="var(--st-glyph)" /></>,
  };
  const outline = <><rect x="2.25" y="2.25" width="11.5" height="11.5" rx="2.5" fill="none" stroke={ink} strokeWidth={1.5} />
    <path d="M8 7.2v4.3" stroke={ink} strokeWidth={1.6} strokeLinecap="round" /><circle cx="8" cy="4.9" r="0.95" fill={ink} /></>;
  return <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" data-mark={mark} data-kind={kind}>
    {kind === "puntualizacion" ? outline : shapes[mark]}</svg>;
}

/** The header of every page: the DeFacto wordmark, which leads home, and one pill bar with the sections and the language
 * (f7 §19.10); `nav` lights the current section. */
export function Page({ lang, nav, children }: { lang: Lang; nav?: Section; children: ReactNode }) {
  return (
    <div className="page">
      <header className="top">
        <HomeMark lang={lang} home={nav === "home"} />
        {/* Every page, the viewer included, leads back home and to the sections (owner, 2026-11-22). */}
        <SiteBar lang={lang} at={nav ?? "other"} />
      </header>
      {children}
      <Tips />
    </div>
  );
}

/** A state of the page in place of the viewer: loading, no analysis, a page that does not exist. A dead end (`lang`
 * given) is a reading page, so it gets the footer; the loading state does not, since the viewer may follow it. */
export function State({ children, lang }: { children: ReactNode; lang?: Lang }) {
  return <><main className="state">{children}</main>{lang && <Footer lang={lang} />}</>;
}

/** The section line under a page's hero: a plain line; the V is CALVET's mark, never DeFacto's (owner, 2026-11-22). */
export const Keel = () => <div aria-hidden="true" className="keel"><svg height="1"><path d="M0 .5 H4000" className="keel-line" /></svg></div>;

/** A page that does not exist, or whose data failed to load: the large DeFacto mark, which turns on load and under the
 * mouse, one line and one link home (design panel, 2026-11-22; logo-spec.md §3). */
export function Lost({ lang, line }: { lang: Lang; line: string }) {
  return <>
    <main className="state lost"><BigMark caps={[64, 48]} hover /><p>{line}</p><a href={`/${lang}/`}>{TEXTS[lang].footer.home}</a></main>
    <Footer lang={lang} />
  </>;
}

/** The way back from a dead end: the previous page, and the last video this browser watched. */
export function Back({ lang }: { lang: Lang }) {
  const t = TEXTS[lang];
  let last: string | null = null;
  try {
    last = localStorage.getItem(LAST_VIDEO);
  } catch { /* storage blocked: the previous page still works */ }
  return (
    <div className="ways">
      {history.length > 1 && <button type="button" className="link" onClick={() => history.back()}>{t.back}</button>}
      {last && last !== location.pathname && <a href={last.replace(/^\/(es|en)/, `/${lang}`)}>{t.lastVideo}</a>}
    </div>
  );
}

/** Why a flag was raised; a nitpick adds the judge's note on why the slip is small. */
export function Reason({ f, t, card = false }: { f: Flag; t: Texts; card?: boolean }) {
  const Line = card ? "span" : "p";
  const cls = card ? "small" : undefined;
  return <>
    <Line className={cls}>{f.reason}</Line>
    {nitpick(f) && <Line className={cls}>{t.word.puntualizacion}: {f.judge!.reason}</Line>}
  </>;
}

const sub = (f: Flag, t: Texts) => t.label[f.label] ?? f.label;
// A Retórica flag names its device in its head (owner, S5): "Retórica · falso dilema".
const device = (f: Flag, t: Texts) => (kindOf(f) === "retorica" ? t.label[f.label]?.toLowerCase() : undefined);
const confidence = (f: Flag, t: Texts) => `${Math.round(f.confidence * 100)} %${low(f) ? ` · ${t.low}` : ""}`;
// A disputed claim names every source that disagrees; any other flag, its first.
export const sources = (f: Flag) => (f.label === "disputed" ? f.sources : f.sources.slice(0, 1));
// A card stays long enough to read it, as the extension's cards: 15 characters a second, 8 to 20 seconds.
const hold = (f: Flag) => Math.min(20, Math.max(8, (f.quote.length + f.reason.length + (nitpick(f) ? f.judge!.reason.length : 0)) / 15));

/** A mark within 12 px of a cluster's first mark joins it. The cluster shows its lead, its gravest flag (the earliest
 * of equals): its mark sits at the lead's second, and a hover or a click names and opens the lead. Before the lane is
 * laid out, none join. */
export function clusters(flags: Flag[], duration: number, width: number) {
  const near = width ? (LANE_GAP_PX / width) * duration : 0;
  const out: { flags: Flag[]; lead: Flag; mark: Mark }[] = [];
  for (const f of flags) {
    const last = out.at(-1);
    if (last && f.t - last.flags[0].t < near) {
      last.flags.push(f);
      if (MARKS.indexOf(markOf(f)) < MARKS.indexOf(last.mark)) Object.assign(last, { lead: f, mark: markOf(f) });
    } else out.push({ flags: [f], lead: f, mark: markOf(f) });
  }
  return out;
}

/** The head of a flag on one line: its mark, its word, its confidence (or its time) and who says it. */
function Head({ f, t, time = false, href }: { f: Flag; t: Texts; time?: boolean; href?: string }) {
  const fallacy = device(f, t);
  return (
    <span className="head">
      <MarkIcon mark={kindOf(f)} dim={low(f)} />
      <span style={{ color: wordColor(f) }} className="word">{t.word[kindOf(f)]}</span>
      {fallacy && <span className="fallacy">· {fallacy}</span>}
      {time ? <span className="num dim">{clock(f.t)}</span> : <span className="num faint conf">{confidence(f, t)}</span>}
      {href ? <a href={href} className="who">{short(f.speaker)}</a> : <span className="who">{short(f.speaker)}</span>}
    </span>
  );
}

/** A row's text: a tap goes to the flag. Its quote shows three lines; "see more" opens the row to show all of it. */
function Said({ f, t, lang, open, go, more }: { f: Flag; t: Texts; lang: Lang; open: boolean; go: () => void; more: () => void }) {
  const quote = useRef<HTMLSpanElement>(null);
  const [cut, setCut] = useState(false);
  useLayoutEffect(() => setCut(quote.current!.scrollHeight > quote.current!.clientHeight), [open]);
  return (
    <>
      <button type="button" aria-expanded={open} onClick={go} className="text">
        <Head f={f} t={t} />
        <span ref={quote} lang={lang} className={`quote${open ? "" : " clamp"}`}>«{f.quote}»</span>
        {!device(f, t) && <span className="why">{sub(f, t)}</span>}
      </button>
      {cut && !open && <button type="button" className="link see-more" onClick={more}>{t.seeMore}</button>}
    </>
  );
}

/** A flag's row, in the panel and on a guest's profile: its time, its head and quote, and once open its reason, its
 * sources and the say. On a phone a closed row keeps the viewer's mark. */
export function Row({ f, t, lang, say, time, open, go, more, phone, lit = false, past = false }: {
  f: Flag; t: Texts; lang: Lang; say: Say; time: ReactNode; open: boolean; go: () => void; more: () => void; phone: boolean;
  lit?: boolean; past?: boolean;
}) {
  return (
    <article aria-current={lit ? "time" : "false"} className={`row${past ? " past" : ""}${low(f) ? " low" : ""}`}>
      {time}
      <div className="body">
        <Said f={f} t={t} lang={lang} open={open} go={go} more={more} />
        {phone && say.mine[f.id] && !open && <Actions f={f} t={t} say={say} />}
        {open && (
          <div className="more">
            <Reason f={f} t={t} />
            <div className="links num">
              {lit && <span className="beat">{t.now}</span>}
              {sources(f).map((s) => <a key={s.url} href={s.url} target="_blank" rel="noopener">{s.publisher} ↗</a>)}
            </div>
            <Actions f={f} t={t} say={say} />
          </div>
        )}
      </div>
    </article>
  );
}

export function Viewer({ lang, meta, flags, Player }: { lang: Lang; meta: Meta; flags: Flag[]; Player: PlayerClass }) {
  const t = TEXTS[lang];
  const [now, setNow] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(100);
  const [captions, setCaptions] = useState(false);
  const [full, setFull] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [panel, setPanel] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const [speaker, setSpeaker] = useState<string | null>(null);
  const [speakers, setSpeakers] = useState(false);
  const [only, setOnly] = useState<Kind | null>(null);
  const [following, setFollowing] = useState(true);
  const [legend, setLegend] = useState(false);
  const [settings, setSettings] = useState(false);
  const [onVideo, setOnVideo] = useState(true);
  const [size, setSize] = useState<keyof typeof SIZES>("M");
  const [side, setSide] = useState<"left" | "right">("right");
  const [quiet, setQuiet] = useState(false);
  const [note, setNote] = useState(false);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [tip, setTip] = useState<number | null>(null);
  const [idle, setIdle] = useState(false);
  const [overBar, setOverBar] = useState(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const phone = useMedia(PHONE); // a phone in portrait: the layout of brand spec §19.7
  const sideways = useMedia(SIDEWAYS);
  const over = full || sideways; // the stage fills the screen: the card over the video, the panel as a side sheet
  const [notice, setNotice] = useState<string | null>(null);
  const [info, setInfo] = useState(false);
  const [langNote, setLangNote] = useState(() => !!meta.requested && !dismissedNote());
  // On a phone the header drops the language, so the byline row offers it when the video exists in both (design, 2026-11-22).
  const [both, setBoth] = useState(false);
  useEffect(() => {
    if (!phone) return;
    fetch("/api/videos").then((r) => r.ok ? r.json() : null)
      .then((d: { videos?: { video_id: string; langs: string[] }[] } | null) =>
        setBoth((d?.videos?.find((v) => v.video_id === meta.video_id)?.langs.length ?? 0) > 1))
      .catch(() => {});
  }, [phone, meta.video_id]);
  const view = useRef<HTMLElement>(null);
  const stack = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLDivElement>(null);
  const boxPaused = useRef(false);
  const [width, setWidth] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const lane = useRef<HTMLDivElement>(null);
  const watch = useRef<HTMLElement>(null);
  const about = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const player = useRef<Player>(null);
  const say = useFeedback(meta.video_id, meta.prompts, t);
  // Where a new player starts: the API turns captions on only when a player loads (cc_load_policy), so the
  // captions button replaces the player at the same second.
  // A time link (`?t=<second>`, spec S5) opens the video at that second.
  const resume = useRef({ at: Number(new URLSearchParams(location.search).get("t")) || 0, play: false, muted: false, volume: 100 });

  // The embed takes an element of its own: YouTube replaces it with its iframe, out of React's sight.
  useEffect(() => {
    const slot = document.createElement("div");
    host.current!.append(slot);
    let poll: ReturnType<typeof setInterval> | undefined;
    const { at, play, muted, volume } = resume.current;
    const p = new Player(slot, {
      videoId: meta.video_id,
      playerVars: {
        controls: 0, fs: 0, playsinline: 1, origin: location.origin, rel: 0, iv_load_policy: 3,
        start: Math.floor(at), autoplay: play ? 1 : 0, ...(captions ? { cc_load_policy: 1 } : {}),
      },
      events: {
        onReady: () => {
          if (muted) p.mute();
          p.setVolume(volume);
          setVolume(p.getVolume());
          poll = setInterval(() => setNow(p.getCurrentTime()), POLL_MS);
        },
        onStateChange: (e: { data: number }) => {
          setPlaying(e.data === PLAYING);
          if (e.data === ENDED) save(meta.video_id, p.getCurrentTime(), p.getDuration() || meta.duration, true);
        },
        onError: (e: { data: number }) => { if (NOT_EMBEDDABLE.includes(e.data)) setBlocked(true); },
      },
    });
    player.current = p;
    return () => {
      clearInterval(poll);
      p.destroy();
    };
  }, [captions]);

  // The time reached, kept in this browser for the list's state word and bar (S9). Opening a video marks it opened.
  const saved = useRef<number | null>(null);
  useEffect(() => {
    if (saved.current === null) {
      saved.current = 0;
      if (!progress(meta.video_id)) save(meta.video_id, 0, meta.duration);
    }
    if (Math.abs(now - saved.current) < SAVE_S) return;
    saved.current = now;
    save(meta.video_id, now, player.current?.getDuration() || meta.duration);
  }, [now]);

  useEffect(() => {
    try {
      localStorage.setItem(LAST_VIDEO, location.pathname);
    } catch { /* storage blocked: the dead-end page only loses its link to this video */ }
    // Esc leaves the browser's full screen, or the page's when the browser refused it: the layout follows.
    const left = () => { if (!document.fullscreenElement) setFull(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setFull(false); };
    document.addEventListener("fullscreenchange", left);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("fullscreenchange", left);
      document.removeEventListener("keydown", esc);
    };
  }, []);

  useLayoutEffect(() => {
    const el = lane.current!;
    const measure = () => setWidth(el.clientWidth);
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    measure();
    return () => observer.disconnect();
  }, []);

  // The page never scrolls: the video takes the height that the text under it leaves.
  useEffect(() => {
    const [box, text, video] = [watch.current!, about.current!, stage.current!];
    const fit = () => {
      const below = text.getBoundingClientRect().bottom - video.getBoundingClientRect().bottom;
      box.style.setProperty("--room", `${box.clientHeight - below - (video.getBoundingClientRect().top - box.getBoundingClientRect().top)}px`);
    };
    const observer = new ResizeObserver(fit);
    observer.observe(box);
    observer.observe(text);
    return () => observer.disconnect();
  }, []);

  const lit = litAt(flags, now);
  // The panel follows the playhead until the viewer scrolls it.
  useEffect(() => {
    const row = list.current?.querySelector<HTMLElement>('[aria-current="time"]');
    if (!following || !row) return;
    // On a phone the page scrolls: the row goes just under the sticky video and panel head.
    if (phone && !over) scrollTo({ top: scrollY + row.getBoundingClientRect().top - stack.current!.offsetHeight - head.current!.offsetHeight });
    else list.current!.scrollTop = row.offsetTop - list.current!.clientHeight / 3;
  }, [lit, following, panel, sheet, phone, over]);

  // On a phone the panel head sticks under the video and its strip, as tall as --stack; a manual scroll of the page
  // stops following the video, but not one inside a sheet or the filter chips.
  useLayoutEffect(() => {
    if (!phone) return;
    const el = stack.current!;
    const measure = () => view.current!.style.setProperty("--stack", `${el.offsetHeight}px`);
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    measure();
    const manual = (e: Event) => { if (!(e.target as Element).closest('[role="dialog"], .filter')) setFollowing(false); };
    addEventListener("touchmove", manual, { passive: true });
    addEventListener("wheel", manual, { passive: true });
    return () => {
      observer.disconnect();
      removeEventListener("touchmove", manual);
      removeEventListener("wheel", manual);
    };
  }, [phone]);

  const seekTo = (seconds: number) => {
    player.current!.seekTo(seconds, true);
    setNow(seconds);
    setFollowing(true);
  };
  // A click on the bar goes to the lead of the mark nearest the pointer, if one sits within 12 px; elsewhere it seeks
  // to that point.
  const seekAt = (e: MouseEvent<HTMLDivElement>) => {
    const box = lane.current!.getBoundingClientRect();
    const at = ((e.clientX - box.left) / box.width) * meta.duration;
    const near = lanes.reduce<Flag | null>((best, c) => (!best || Math.abs(c.lead.t - at) < Math.abs(best.t - at) ? c.lead : best), null);
    if (near && (Math.abs(near.t - at) / meta.duration) * box.width <= SNAP_PX) go(near);
    else seekTo(at);
  };
  // A tap on a flag goes to its second and opens its reason: in its row, or in the sheet on a phone.
  // Each jump to a flag's moment counts one anonymous seek (no consent asked: no id leaves the browser).
  const go = (f: Flag) => {
    seekTo(f.t);
    fetch("/api/visits", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: meta.video_id, lang, kind: "seek" }) }).catch(() => {});
    if (phone && !over) setNotice(f.id);
    else setOpen(f.id);
  };
  // Writing in the sheet pauses the video; it plays again once the box closes, sent or not, or the sheet closes.
  const pauseForBox = () => {
    if (!playing) return;
    player.current!.pauseVideo();
    boxPaused.current = true;
  };
  const resumeAfterBox = () => {
    if (boxPaused.current) player.current!.playVideo();
    boxPaused.current = false;
  };
  const closeNotice = () => {
    setNotice(null);
    resumeAfterBox();
  };
  const toggleCaptions = () => {
    resume.current = { at: player.current!.getCurrentTime(), play: playing, muted, volume };
    setCaptions(!captions);
  };
  const changeVolume = (value: number) => {
    player.current!.setVolume(value);
    setVolume(value);
    if (muted && value > 0) {
      player.current!.unMute();
      setMuted(false);
    }
  };
  // Our own full screen holds the video, the bar, the cards and the panel as a side sheet; on a browser without it
  // (iPhone), the page fills the screen.
  // Like a normal player: any pointer, touch or focus on the player shows the bar, then it rests again.
  const wake = () => {
    setIdle(false);
    clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setIdle(true), IDLE_MS);
  };
  useEffect(() => {
    wake();
    return () => clearTimeout(idleTimer.current);
  }, [playing]);
  const togglePlay = () => (playing ? player.current!.pauseVideo() : player.current!.playVideo());

  const fullScreen = () => {
    // A phone turns the video sideways once the browser is full screen; an iPhone refuses both, and the page still
    // fills the window.
    const turn = screen.orientation as ScreenOrientation & { lock?: (to: string) => Promise<void> } | undefined;
    if (full) {
      turn?.unlock?.();
      if (document.fullscreenElement) document.exitFullscreen();
      setFull(false);
    } else {
      stage.current!.requestFullscreen?.().then(() => turn?.lock?.("landscape")).catch(() => {});
      setFull(true);
    }
    setSheet(false);
  };

  const isNote = (f: Flag) => kindOf(f) === "contexto"; // a nitpick is a flag: a card, its reason and sources
  // A nitpick counts as a flag, with its reason and sources; only the plain context notes stay apart. The bar shows
  // neither.
  const signals = flags.filter((f) => kindOf(f) !== "contexto");
  const onLane = signals.filter((f) => !nitpick(f));
  const bySpeaker = flags.filter((f) => !speaker || f.speaker === speaker);
  const shown = bySpeaker.filter((f) => !only || kindOf(f) === only);
  const count = (kind: Kind, of = bySpeaker) => of.filter((f) => kindOf(f) === kind).length;
  const duration = meta.duration;
  const lanes = clusters(onLane, duration, width);
  // The flag being said, while it is read: the card over the video, or the strip under it on a phone.
  const current = onVideo && lit && now < lit.t + hold(lit) && (isNote(lit) || !quiet || ["falso", "enganoso"].includes(markOf(lit))) ? lit : null;
  // Over a filled screen the card hides while the side sheet is open.
  const cards = (!phone || over) && !(over && sheet);
  const card = cards && current && !isNote(current) && current.id !== dismissed ? current : null;
  const pill = cards && onVideo && lit && isNote(lit) ? lit : null;
  const opened = phone && !over ? flags.find((f) => f.id === notice) : undefined;
  // The bar rests only while the video plays and nothing of it is in use.
  const resting = idle && playing && !overBar && !settings && !(over && sheet);
  const away = side === "left" ? "right" : "left"; // the pill sits across from the card
  const date = meta.published_at && new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${meta.published_at}T00:00:00Z`));
  const byline = [meta.channel, date].filter(Boolean).join(" · ");
  // One card per guest (owner review 2026-11-22). The face is cut from the YouTube thumbnail: in a debate of two, the
  // guest's half (faces.ts); otherwise its centre.
  const face = (g: string) => { const h = half(meta.guests, g, meta.swap); return h ? ` ${h}` : ""; };
  const guests = meta.guests.length > 0 && (
    <div className="guests">
      <ul className="guest-cards">
        {meta.guests.map((g) => (
          <li key={g}>
            <a href={profilePath(lang, meta.video_id, g)} aria-label={t.seeProfile(short(g))} className="guest-card">
              <span className={`face${face(g)}`}>
                <img src={`https://i.ytimg.com/vi/${encodeURIComponent(meta.video_id)}/hqdefault.jpg`} alt="" aria-hidden="true" />
              </span>
              <span className="guest-text">
                <span className="guest-name">{short(g)}</span>{role(g) && <span className="guest-role">{role(g)}</span>}
              </span>
              <span className="guest-go">{t.profileCard} →</span>
            </a>
          </li>
        ))}
      </ul>
      {meta.guests.length > 1 && <a href={comparePath(lang, meta.video_id)} className="compare-pill">{t.compare.link}</a>}
    </div>
  );
  const summary = (
    <p className="glass summary">
      {KINDS.filter((k) => count(k, flags)).map((k) => (
        <span key={k}><MarkIcon mark={k} /><span style={{ color: `var(--st-${markFor(k)}-text)` }} className="word">{t.word[k]}</span>
          <span className="num">{count(k, flags)}</span></span>
      ))}
    </p>
  );
  const ai = <p className="ai"><Info />{t.ai}</p>;
  // A guest's name on a flag leads to their profile (S5); a host has none.
  const profile = (f: Flag) => (meta.guests.includes(f.speaker) ? profilePath(lang, meta.video_id, f.speaker) : undefined);
  // A flag's quote, its reason and its sources: on the card, or in the sheet on a phone.
  const detail = (f: Flag, card = false) => <>
    <span lang={meta.lang} className="quote">«{f.quote}»</span>
    <Reason f={f} t={t} card={card} />
    {sources(f).map((s) => <a key={s.url} href={s.url} target="_blank" rel="noopener" className="source">{s.publisher} ↗</a>)}
  </>;
  const seg = <K extends string>(value: K, current: K, pick: (k: K) => void, text: string) => (
    <button key={value} type="button" aria-pressed={value === current} onClick={() => pick(value)}>{text}</button>
  );
  const chip = (key: Kind | null, text: string, n: number) => (
    <button key={key ?? "all"} type="button" aria-pressed={only === key} onClick={() => setOnly(key)}>
      {key && <span aria-hidden="true" className={`dot m-${key}`} />}
      {text} <span className="num">{n}</span>
    </button>
  );
  const who = (g: string | null) => (g ? short(g) : t.everyone(meta.guests.length));
  const said = (g: string | null) => signals.filter((f) => !g || f.speaker === g).length;

  const speakerMenu = meta.guests.length > 1 && (
    <button type="button" aria-label={t.who} aria-haspopup="true" aria-expanded={speakers} onClick={() => setSpeakers(!speakers)}
      className="link speaker">
      {who(speaker)} <span className="num">{said(speaker)}</span><Chevron />
    </button>
  );
  const legendBody = <>
    <p className="small dim">{t.whatIntro}</p>
    {KINDS.map((k) => (
      <div key={k} className="legend-row"><span style={{ color: `var(--st-${markFor(k)}-text)` }} className="word small">{t.word[k]}</span>
        <span className="small">{t.legend[k]}</span></div>
    ))}
    <p className="small dim"><span className="num">70 %</span> {t.confidence}</p>
  </>;

  // The panel: its counts, one filter bar and the list. Beside the video, or as a side sheet over it in full screen.
  // On a phone, the count, "follow the video" and who says it share one row over the filter bar.
  const panelBody = (
    <>
      <div ref={head} className="panel-head">
        <div className="counts">
          <h2>{t.count(signals.length)}</h2>
          <button type="button" aria-label={phone ? t.what : undefined} aria-expanded={legend} onClick={() => setLegend(!legend)} className="link what">
            <Info />{!phone && t.what}
          </button>
          {phone
            ? <>
                <label className="follow"><span>{t.follow}</span>
                  <input type="checkbox" role="switch" checked={following} onChange={() => setFollowing(!following)} /></label>
                {speakerMenu}
              </>
            : <button type="button" aria-label={over ? t.close : t.hidePanel} onClick={() => (over ? setSheet(false) : setPanel(false))}
                className="icon hide">×</button>}
        </div>
        {/* The filter bar of the marks, then who says it on its own line: nothing covers the scrolling chips. */}
        <div role="group" aria-label={t.filter} className="glass chips filter">
          <div className="marks">
            {chip(null, t.all, bySpeaker.length)}
            {KINDS.filter((k) => count(k)).map((k) => chip(k, t.word[k], count(k)))}
          </div>
        </div>
        {!phone && speakerMenu}
        {speakers && (
          <div role="group" aria-label={t.who} className="popover">
            {[null, ...meta.guests].map((g) => (
              <button key={g ?? "all"} type="button" aria-pressed={speaker === g} onClick={() => { setSpeaker(g); setSpeakers(false); }}>
                {who(g)} <span className="num">{said(g)}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {shown.length ? (
        <ol ref={list} className={`rows${duration >= 3600 ? " long" : ""}`} onWheel={() => setFollowing(false)} onTouchMove={() => setFollowing(false)}>
          {shown.map((f) => (
            <li key={f.id}>
              <Row f={f} t={t} lang={meta.lang} say={say} phone={phone} open={open === f.id} lit={f === lit} past={!!lit && f.t < lit.t}
                go={() => go(f)} more={() => setOpen(f.id)}
                time={<button type="button" aria-label={t.go(clock(f.t))} className="time num" onClick={() => go(f)}>{clock(f.t)}</button>} />
            </li>
          ))}
        </ol>
      ) : (
        <div className="empty">
          <p>{t.empty(only && t.word[only], speaker && short(speaker))}</p>
          <button type="button" className="link" onClick={() => { setOnly(null); setSpeaker(null); }}>{t.seeAll}</button>
        </div>
      )}

      {!following && !phone && (
        <button type="button" className="glass back" onClick={() => setFollowing(true)}>{t.backToNow}</button>
      )}
      {legend && (phone
        ? <Sheet label={t.what} head={<span className="sheet-title">{t.what}</span>} close={() => setLegend(false)} closeLabel={t.close} below={stack}>
            {legendBody}</Sheet>
        : <div role="dialog" aria-label={t.what} className="sheet legend">
            <div className="sheet-row"><span className="sheet-title">{t.what}</span>
              <button type="button" aria-label={t.close} onClick={() => setLegend(false)} className="icon">×</button></div>
            {legendBody}
          </div>)}
    </>
  );

  return (<>
    {langNote && (
      <div role="note" className="lang-note">
        <Info />
        <span {...hint(t.onlySpanishWhy)} className="lang-note-text">{t.onlySpanish}
          {phone && <> <a href={`/es/v/${encodeURIComponent(meta.video_id)}`} hrefLang="es" lang="es">{t.openSpanish}</a></>}</span>
        {!phone && <a href={`/es/v/${encodeURIComponent(meta.video_id)}`} hrefLang="es" lang="es" className="lang-note-link">{t.openSpanish}</a>}
        <button type="button" aria-label={t.close} className="icon" onClick={() => { dismissNote(); setLangNote(false); }}>×</button>
      </div>
    )}
    <main ref={view} className={`viewer${panel ? "" : " hidden"}`}>
      <section ref={watch} aria-label={meta.title} className="watch">
        {/* The video and, on a phone, the "Ahora" strip under it: they stick to the top together. */}
        <div ref={stack} className="stack">
          <div ref={stage} className={`stage${over ? " full" : ""}${over && sheet ? " with-sheet" : ""}${resting ? " resting" : ""}`}
            onPointerMove={wake} onPointerDown={wake} onFocusCapture={wake}>
            <div ref={host} className="embed" hidden={blocked} />
            {/* Over the iframe, so a pointer on the video reaches us: a click plays or pauses; a tap on a resting bar only wakes it. */}
            {!blocked && <div className="catcher" aria-hidden="true" onClick={() => { if (!resting) togglePlay(); }} />}
            {blocked && (
              <div className="blocked">
                <span className="error"><MarkIcon mark="enganoso" /> {t.blocked}</span>
                <p>{t.blockedWhy}</p>
                <a href={`https://www.youtube.com/watch?v=${encodeURIComponent(meta.video_id)}`}>{t.youtube}</a>
              </div>
            )}

            {pill && (note
              ? <div className={`notice note ${away}`}>
                  <span className="head"><MarkIcon mark="contexto" /><span style={{ color: wordColor(pill) }} className="word">{t.word[kindOf(pill)]}</span>
                    <span className="dim quote-line">· «{pill.quote}»</span>
                    <button type="button" aria-label={t.fold} onClick={() => setNote(false)} className="icon fold">×</button></span>
                  <span className="small">{pill.reason}</span>
                </div>
              : <button type="button" aria-expanded="false" onClick={() => setNote(true)} className={`notice pill ${away}`}>
                  <MarkIcon mark="contexto" size={14} /> <span className="quote-line">{t.word[kindOf(pill)]} · «{pill.quote}»</span>
                </button>)}
            {card && (
              <article aria-label={t.nowFlag} aria-live="polite" className={`notice card ${side}`} style={{ zoom: ZOOM[size] }}>
                <span className="card-head"><Head f={card} t={t} href={profile(card)} />
                  <button type="button" aria-label={t.hideCard} onClick={() => setDismissed(card.id)} className="icon fold">×</button></span>
                {detail(card, true)}
                {/* Writing on the card pauses the video, so the card stays while the viewer writes. */}
                <Actions key={card.id} f={card} t={t} say={say} onOpen={() => player.current!.pauseVideo()} />
              </article>
            )}

            {say.question}
            {settings && (
              <div role="dialog" aria-label={t.settings} className="sheet settings">
                <span className="sheet-title">{t.settings}</span>
                <label className="setting"><span>{t.onVideo}</span>
                  <input type="checkbox" checked={onVideo} onChange={() => setOnVideo(!onVideo)} />
                </label>
                <span className="small">{phone ? t.onVideoWhyPhone : t.onVideoWhy}</span>
                {/* A phone draws no card, so it has no card size or side. */}
                {!phone && <>
                  <div className="setting"><span>{t.size}</span>
                    <div role="group" aria-label={t.sizeLabel} className="glass chips">
                      {(Object.keys(SIZES) as (keyof typeof SIZES)[]).map((k) => seg(k, size, setSize, SIZES[k]))}
                    </div>
                  </div>
                  <div className="setting"><span>{t.side}</span>
                    <div role="group" aria-label={t.sideLabel} className="glass chips">
                      {seg("left", side, setSide, t.left)}{seg("right", side, setSide, t.right)}
                    </div>
                  </div>
                </>}
                <label className="setting"><span>{t.quiet}</span>
                  <input type="checkbox" checked={quiet} onChange={() => setQuiet(!quiet)} />
                </label>
                <span className="small">{t.quietWhy}</span>
              </div>
            )}

            {over && sheet && <aside aria-label={t.flags} className="panel side-sheet">{panelBody}</aside>}

            <div aria-hidden="true" className="thin">
              <div className="played" style={{ width: pct(now, duration) }} />
              {lanes.map((c) => (
                <span key={c.lead.id} className={`lane-mark m-${c.mark}${low(c.lead) ? " low" : ""}`} style={{ left: pct(c.lead.t, duration) }} />
              ))}
            </div>
            <div className="bar" onPointerEnter={() => setOverBar(true)} onPointerLeave={() => setOverBar(false)}>
              <div ref={lane} role="group" aria-label={t.lane} className="lane" onClick={seekAt}>
                <div className="track" />
                <div className="played" style={{ width: pct(now, duration) }} />
                {lanes.map((c, i) => (
                  <button key={c.lead.id} type="button" style={{ left: pct(c.lead.t, duration) }}
                    aria-label={`${clock(c.lead.t)} · ${c.flags.length > 1 ? t.count(c.flags.length) : t.word[c.mark]}`}
                    onClick={(e) => { e.stopPropagation(); go(c.lead); }}
                    onMouseEnter={() => setTip(i)} onMouseLeave={() => setTip(null)}>
                    <span aria-hidden="true" data-mark={c.mark} className={`lane-mark m-${c.mark}${c.flags.length > 1 ? " many" : ""}${low(c.lead) ? " low" : ""}`} />
                    {c.flags.length > 1 && <span aria-hidden="true" className="plus num">+{c.flags.length - 1}</span>}
                  </button>
                ))}
                <span aria-hidden="true" className="playhead" style={{ left: pct(now, duration) }} />
                {tip !== null && lanes[tip] && (() => {
                  const f = lanes[tip].lead;
                  return (
                    <div role="tooltip" className="tip" style={{ left: pct(f.t, duration) }}>
                      <span className="head"><span className="num dim">{clock(f.t)}</span>
                        <span style={{ color: wordColor(f) }} className="word">{t.word[markOf(f)]}</span><span className="who">{short(f.speaker)}</span></span>
                      <span lang={meta.lang} className="quote small">«{f.quote}»</span>
                    </div>
                  );
                })()}
              </div>
              <div className="controls">
                <button type="button" aria-label={playing ? t.pause : t.play} className="icon"
                  onClick={togglePlay}>
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                    {playing
                      ? <path d="M5 3v10M11 3v10" stroke="var(--t1)" strokeWidth={2} strokeLinecap="round" />
                      : <path d="M4.5 2.8v10.4L13 8z" fill="var(--t1)" />}
                  </svg>
                </button>
                <button type="button" aria-label={muted ? t.unmute : t.mute} className="icon" onClick={() => {
                  if (muted) player.current!.unMute();
                  else player.current!.mute();
                  setMuted(!muted);
                }}>
                  <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" fill="none" stroke="var(--t1)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 7h2.5L9 4v10l-3.5-3H3z" />
                    {muted ? <path d="M12 7l4 4M16 7l-4 4" /> : <path d="M12 6.5a3.5 3.5 0 0 1 0 5M14 4.5a6.5 6.5 0 0 1 0 9" />}
                  </svg>
                </button>
                <input type="range" min={0} max={100} value={muted ? 0 : volume} aria-label={t.volume} className="volume"
                  onChange={(e) => changeVolume(Number(e.target.value))} />
                <span className="num dim time-now">{clock(now)} / {clock(duration)}</span>
                <span className="spacer" />
                <button type="button" aria-label={t.captions} aria-pressed={captions} onClick={toggleCaptions} className="icon cc">CC</button>
                <button type="button" aria-label={t.settings} aria-expanded={settings} onClick={() => setSettings(!settings)} className="icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" fill="none" stroke="var(--t1)" strokeWidth={1.5} strokeLinecap="round">
                    <path d="M3 5h7M13 5h2M3 13h2M8 13h7" /><circle cx="11.5" cy="5" r="1.6" /><circle cx="6.5" cy="13" r="1.6" />
                  </svg>
                </button>
                {(!panel || over) && (
                  <button type="button" aria-label={t.openPanel} aria-expanded={over ? sheet : false} className="open-panel"
                    onClick={() => (over ? setSheet(!sheet) : setPanel(true))}>
                    {t.flags} <span className="num count">{signals.length}</span>
                  </button>
                )}
                <button type="button" aria-label={full ? t.exitFull : t.full} className="icon" onClick={fullScreen}>
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="var(--t1)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                    <path d={full ? "M6 2v4H2M10 2v4h4M6 14v-4H2M10 14v-4h4" : "M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4"} />
                  </svg>
                </button>
              </div>
            </div>
          </div>
          {/* A tap on the strip opens its flag in the sheet; a context note shows here too, as a note. */}
          {phone && !over && onVideo && (
            <div aria-label={t.nowFlag} aria-live="polite" className="now">
              {current
                ? <button type="button" aria-haspopup="dialog" onClick={() => setNotice(current.id)}>
                    <Head f={current} t={t} time />
                    <span lang={meta.lang} className="quote">«{current.quote}»</span>
                  </button>
                : <p>{t.between}</p>}
            </div>
          )}
        </div>

        {/* On a phone, one line of title and who and when; "Más" opens the rest in a sheet. */}
        <div ref={about} className="about">
          <h1>{meta.title}</h1>
          {phone
            ? <div className="byline-row"><p className="byline">{byline}</p>
                {both && <nav aria-label={t.nav} className="langs byline-langs">
                  {(["es", "en"] as Lang[]).map((l, i) => <Fragment key={l}>
                    {i > 0 && <span aria-hidden="true" className="sep-dot">·</span>}
                    {l === meta.lang
                      ? <span aria-current="true" lang={l}>{l.toUpperCase()}</span>
                      : <a href={`/${l}/v/${encodeURIComponent(meta.video_id)}${now >= 1 ? `?t=${Math.floor(now)}` : ""}`} hrefLang={l} lang={l}>{l.toUpperCase()}</a>}
                  </Fragment>)}
                </nav>}
                <button type="button" aria-haspopup="dialog" aria-expanded={info} onClick={() => setInfo(true)} className="link more-info">
                  {t.more}<Chevron /></button></div>
            : null}
          {/* The guests' cards show on every screen: the way to a profile must not hide (owner, 2026-11-22). */}
          {phone && guests}
          {!phone && <><p className="byline">{byline}</p>{guests}{summary}{ai}</>}
        </div>
      </section>

      {!over && <aside aria-label={t.flags} className="panel">{panelBody}</aside>}

      {opened && (
        <Sheet label={t.nowFlag} head={<Head f={opened} t={t} href={profile(opened)} />} close={closeNotice} closeLabel={t.close} below={stack}>
          {detail(opened)}
          <Actions key={opened.id} f={opened} t={t} say={say} onOpen={pauseForBox} onClose={resumeAfterBox} />
        </Sheet>
      )}
      {phone && info && (
        <Sheet label={t.about} head={<h2 className="info-title">{meta.title}</h2>} close={() => setInfo(false)} closeLabel={t.close} below={stack}>
          {summary}{ai}
        </Sheet>
      )}
    </main>
  </>);
}
