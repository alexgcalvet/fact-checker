// The video list (spec S4), as the owner approved it on the canvas page s4-elegir: the heading and one toolbar, the
// newest video on the line, then the rows by week or in the picked order, never numbered. Each row has its ledger: the avisos, how disputed the
// video is for its length (avisos per 10 minutes) and a mix bar drawn like the marks. Filters and search (S8, the same
// canvas page, board "S4 · Arriba y cuadrícula v2") narrow it, each option counted with the other filters kept. S9 adds
// the grid view and what this browser watched: a state word and a bar under each thumbnail, the thumbnails dimmed at rest.
import { Fragment, useEffect, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import { active, any, count, fold, matches, NONE, people, read, viewOf, write, type Facet, type Filters } from "./filters";
import { AVISOS, kindOf, nitpick, type Flag, type Kind } from "./marks";
import { Footer } from "./Footer";
import { lane, stop, tip } from "./Tip";
import { TEXTS, type Lang, type Texts } from "./texts";
import { Sheet } from "./Sheet";
import { clock, MarkIcon, READING_PHONE, useMedia } from "./Viewer";
import { keepView, lastView, progress, share, stateOf, type View } from "./watched";

/** A video of `GET /api/videos`. */
export interface Listed {
  video_id: string;
  title: string;
  display_title?: string | null; // the collector's title for the reader
  channel: string;
  duration: number;
  published_at: string | null;
  type: string;
  guests: string[];
  flags: number;
  langs: Lang[];
  counts: Record<Kind, number>;
}

const SORTS = ["recientes", "densidad", "antiguos", "avisos", "falso-enganoso", "falso", "largos"] as const;
type Sort = (typeof SORTS)[number];
const BY_DATE: Sort[] = ["recientes", "antiguos"];
const DAY = 86_400_000;
const LANE_BINS = 64; // about 12 px each on the lead's lane: marks in one bin merge
const ONE_COLUMN = "(max-width: 1023px)";
const NO_HOVER = "(hover: none)";
// Within a lane bin the most serious verdict shows.
const SERIOUS: Kind[] = ["falso", "enganoso", "evasiva", "retorica", "puntualizacion"];

export const avisos = (v: Listed) => AVISOS.reduce((n, k) => n + v.counts[k], 0);
/** Avisos per 10 minutes of video, to one decimal; null without a length. */
export const density = (v: Listed) => (v.duration > 0 ? Math.round((avisos(v) / (v.duration / 600)) * 10) / 10 : null);
/** Absolute levels, so a video keeps its colour as the list grows (owner, canvas). */
const level = (d: number) => (d >= 6 ? "alto" : d >= 4 ? "medio" : "bajo");
const LIT = { bajo: 1, medio: 2, alto: 3 };

const date = (v: Listed) => v.published_at ?? "";
export const newest = (a: Listed, b: Listed) => date(b).localeCompare(date(a)) || a.video_id.localeCompare(b.video_id);
const desc = (f: (v: Listed) => number) => (a: Listed, b: Listed) => f(b) - f(a) || newest(a, b);
/** Each order; ties go to the newest. */
const ORDER: Record<Sort, (a: Listed, b: Listed) => number> = {
  recientes: newest,
  densidad: desc((v) => density(v) ?? -1),
  antiguos: (a, b) => date(a).localeCompare(date(b)) || a.video_id.localeCompare(b.video_id),
  avisos: desc(avisos),
  "falso-enganoso": desc((v) => v.counts.falso + v.counts.enganoso),
  falso: (a, b) => b.counts.falso - a.counts.falso || b.counts.enganoso - a.counts.enganoso || newest(a, b),
  largos: desc((v) => v.duration),
};

const sortOf = (search: string): Sort => {
  const asked = new URLSearchParams(search).get("orden") as Sort;
  return SORTS.includes(asked) ? asked : "recientes";
};

const utc = (iso: string) => new Date(`${iso}T00:00:00Z`);
export const day = (lang: Lang, iso: string, year = true) =>
  new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", ...(year ? { year: "numeric" } : {}), timeZone: "UTC" }).format(utc(iso));
const monday = (d: Date) => new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - ((d.getUTCDay() + 6) % 7)));

/** The head of a video's week: this week, last week, a week of the last month, else its month. */
function weekOf(lang: Lang, t: Texts, iso: string | null, lead: boolean): string {
  if (!iso) return t.list.noDate;
  const start = monday(utc(iso));
  const weeks = Math.round((monday(new Date()).getTime() - start.getTime()) / (7 * DAY));
  const range = () => new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", timeZone: "UTC" })
    .formatRange(start, new Date(start.getTime() + 6 * DAY));
  if (weeks <= 0) return lead ? t.list.alsoThisWeek : t.list.thisWeek;
  if (weeks === 1) return t.list.lastWeek(range());
  if (weeks <= 4) return t.list.weekOf(range());
  const sameYear = start.getUTCFullYear() === new Date().getUTCFullYear();
  const month = new Intl.DateTimeFormat(lang, { month: "long", ...(sameYear ? {} : { year: "numeric" }), timeZone: "UTC" }).format(utc(iso));
  return month[0].toUpperCase() + month.slice(1);
}

export const thumb = (id: string, size: "mq" | "hq") => `https://i.ytimg.com/vi/${encodeURIComponent(id)}/${size}default.jpg`;
/** "Ana Pérez (candidata)" → "Ana Pérez", as the viewer names a guest; joined as "Ana y Luis". */
const guestsOf = (lang: Lang, t: Texts, v: Listed) => v.guests.length > 0 &&
  t.list.with(new Intl.ListFormat(lang, { type: "conjunction" }).format(v.guests.map((g) => g.replace(/\s*\(.*\)\s*$/, ""))));
export const href = (lang: Lang, id: string) => `/${lang}/v/${encodeURIComponent(id)}`;

/** A thumbnail's picture in the graded layer (dimmed at rest); the duration and the watched bar sit outside it. */
const Art = ({ id, size }: { id: string; size: "mq" | "hq" }) => <span className="art"><img src={thumb(id, size)} alt="" loading="lazy" /></span>;

/** The bar under a thumbnail: how far this browser watched the video. */
function Watched({ id }: { id: string }) {
  const s = share(progress(id));
  return s !== null && <span aria-hidden="true" className="watched"><span style={{ width: `${Math.round(s * 1000) / 10}%` }} /></span>;
}

/** "Nuevo", "Empezado" or "Visto", or nothing. */
function StateWord({ v, t }: { v: Listed; t: Texts }) {
  const s = stateOf(v.video_id, v.published_at);
  return s && <span className={`seen s-${s}`}>{t.list.states[s]}</span>;
}

/** "ES · EN" or "ES": the languages a video is analysed in. */
function Langs({ v, t }: { v: Listed; t: Texts }) {
  const both = v.langs.includes("en");
  return <span aria-label={both ? t.list.langs.both : t.list.langs.es} className="codes">{both ? "ES · EN" : "ES"}</span>;
}

/** The avisos per 10 minutes: a 3-tick meter in the level's colour, the number, and the level's word for a reader. */
// The lead's meter takes keyboard focus for its tooltip; a row's sits inside the row's link, which takes it.
export function Density({ d, t, lang, long = false, active = false, focus = long }: { d: number; t: Texts; lang: Lang; long?: boolean; active?: boolean; focus?: boolean }) {
  const lvl = level(d);
  const n = new Intl.NumberFormat(lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(d);
  return (
    <span {...tip(t.list.densityTitle(n, t.list.levels[lvl]), focus)} className={`density l-${lvl}${active ? " active" : ""}`}>
      <span aria-hidden="true" className="meter">{[1, 2, 3].map((i) => <span key={i} className={i <= LIT[lvl] ? "lit" : ""} />)}</span>
      <span className="num">{long ? `${n} ${t.list.perTen}` : `${n}/10′`}</span>
      <span className="sr">{t.list.levels[lvl]}</span>
    </span>
  );
}

/** The mix bar: as long as the video is disputed against the most disputed one, its segments drawn like the marks. */
// A grid card keeps an empty bar for a video with no avisos, so its line stays.
function Mix({ v, t, max, keep = false }: { v: Listed; t: Texts; max: number; keep?: boolean }) {
  const d = density(v);
  const kinds = AVISOS.filter((k) => v.counts[k]);
  if (d === null || !kinds.length) return keep ? <span aria-hidden="true" className="mix" /> : null;
  return (
    <span role="img" aria-label={kinds.map((k) => `${v.counts[k]} ${t.word[k]}`).join(", ")} className="mix"
      style={{ width: `max(8px, ${(d / max) * 100}%)` }}>
      {kinds.map((k) => <span key={k} className={`seg m-${k}`} style={{ flexGrow: v.counts[k] }} />)}
    </span>
  );
}

/** The marks with their counts, as in the viewer: the legend of the mix bar on a phone and on the lead. */
export function Marks({ v, t, words = false }: { v: Listed; t: Texts; words?: boolean }) {
  return (
    <span className={words ? "verdicts" : "mini-marks"}>
      {AVISOS.filter((k) => v.counts[k]).map((k) => (
        <span key={k} {...(words ? {} : tip(t.word[k], true))}>
          {words ? <MarkIcon mark={k} /> : <span aria-hidden="true" className={`dot m-${k}`} />}
          {words && <><span style={{ color: `var(--st-${k === "puntualizacion" ? "contexto" : k}-text)` }} className="word">{t.word[k]}</span>{" "}</>}
          <span className="num" style={words ? undefined : { color: `var(--st-${k === "puntualizacion" ? "contexto" : k}-text)` }}>{v.counts[k]}</span>
        </span>
      ))}
    </span>
  );
}

/** The language a video's flags are asked in: the reader's, else the one it has. */
export const served = (v: Listed, lang: Lang) => (v.langs.includes(lang) ? lang : v.langs[0]);

/** Where the lead's avisos fall: the flags route of the newest video. */
function Lane({ v, t, lang }: { v: Listed; t: Texts; lang: Lang }) {
  const [flags, setFlags] = useState<Flag[] | null>(null);
  const asked = served(v, lang);
  useEffect(() => {
    fetch(`/api/videos/${encodeURIComponent(v.video_id)}/flags?lang=${asked}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((answer) => answer && setFlags(answer.flags))
      .catch(() => undefined); // the lane is extra: the lead stands without it
  }, [v.video_id, asked]);
  return flags && <LaneLine v={v} t={t} lang={lang} flags={flags} />;
}

/** A video's lane: one mark per bin, the most serious one; Enter or a click on a mark opens the viewer there. */
export function LaneLine({ v, t, lang, flags }: { v: Listed; t: Texts; lang: Lang; flags: Flag[] }) {
  if (!v.duration) return null;
  const bins = new Map<number, { kind: Kind; n: number; t: number }>();
  for (const f of flags) {
    const kind = kindOf(f);
    if (kind === "contexto" || f.judge?.verdict === "drop") continue;
    const bin = Math.min(LANE_BINS - 1, Math.floor((f.t / v.duration) * LANE_BINS));
    const was = bins.get(bin);
    const keep = was && SERIOUS.indexOf(was.kind) < SERIOUS.indexOf(kind);
    bins.set(bin, { kind: keep ? was.kind : kind, t: keep ? was.t : f.t, n: (was?.n ?? 0) + 1 });
  }
  return (
    <div className="lead-lane">
      <div {...lane(t.markLane)} className="lane-line">
        {[...bins].sort(([a], [b]) => a - b).map(([bin, { kind, n, t: at }], i) => (
          <span key={bin} {...tip(n > 1 ? t.list.avisos(n) : t.word[kind])} {...stop(i === 0)} data-href={`${href(lang, v.video_id)}?t=${Math.floor(at)}`}
            className={`lane-mark m-${kind}`}
            style={{ left: `${((bin + 0.5) / LANE_BINS) * 100}%` }} />
        ))}
      </div>
    </div>
  );
}

/** The newest video, standing on the line. */
function Lead({ v, t, lang, max, phone }: { v: Listed; t: Texts; lang: Lang; max: number; phone: boolean }) {
  const d = density(v);
  const picture = (
    <a href={href(lang, v.video_id)} aria-label={v.title} className="lead-thumb">
      <Art id={v.video_id} size="hq" />
      {v.duration > 0 && <span className="badge num">{clock(v.duration)}</span>}
      <Watched id={v.video_id} />
    </a>
  );
  // On a laptop the totals move to the verdict row's tooltip; the density stays.
  const perTen = d !== null && <Density d={d} t={t} lang={lang} long />;
  return (
    <article className="lead">
      {!phone && picture}
      <div className="lead-text">
        <span className="lead-label">{t.list.latest}</span>
        <h3><a href={href(lang, v.video_id)}>{v.title}</a></h3>
        <span className="dim">{[v.channel, v.published_at && day(lang, v.published_at)].filter(Boolean).join(" · ")}</span>
        <div className="lead-avisos">
          {phone
            ? <><span className="tally">{t.list.avisos(avisos(v))}{perTen && <> · {perTen}</>}</span><Marks v={v} t={t} /></>
            : <><span {...tip(t.list.totals(avisos(v), v.counts.contexto), true)}><Marks v={v} t={t} words /></span>
                {perTen && <span className="tally">{perTen}</span>}</>}
          <Mix v={v} t={t} max={max} />
        </div>
        {!phone && <Lane v={v} t={t} lang={lang} />}
        {!phone && (
          <div className="lead-actions">
            <a href={href(lang, v.video_id)} className="bone-button">{t.list.watch}</a>
          </div>
        )}
      </div>
      {phone && picture}
    </article>
  );
}

/** A row of the list: on a laptop its columns and ledger, on a phone the thumbnail and three lines. */
function Row({ v, t, lang, max, sort, phone }: { v: Listed; t: Texts; lang: Lang; max: number; sort: Sort; phone: boolean }) {
  const d = density(v);
  const state = <StateWord v={v} t={t} />;
  if (phone) {
    // Three lines of fixed height (board "S4 · Arriba y cuadrícula v2"): the title on two, "canal · d mes", then the
    // state, the density and EN.
    const facts = [stateOf(v.video_id, v.published_at) && state, d !== null && <Density d={d} t={t} lang={lang} active={sort === "densidad"} />,
      v.langs.includes("en") && <En t={t} />].filter(Boolean);
    return (
      <a href={href(lang, v.video_id)} className="row-phone">
        <span className="thumb"><Art id={v.video_id} size="mq" />
          {v.duration > 0 && <span className="badge num">{clock(v.duration)}</span>}<Watched id={v.video_id} /></span>
        <span className="row-text">
          <span title={v.title} className="row-title">{v.title}</span>
          <span className="dim ellipsis">{[v.channel, v.published_at && day(lang, v.published_at, false)].filter(Boolean).join(" · ")}</span>{" "}
          <span className="row-facts ellipsis">{facts.map((x, i) => <Fragment key={i}>{i > 0 && " · "}{x}</Fragment>)}</span>
        </span>
      </a>
    );
  }
  const guests = guestsOf(lang, t, v);
  return (
    <a href={href(lang, v.video_id)} className="row-laptop">
      <span className="thumb"><Art id={v.video_id} size="mq" /><Watched id={v.video_id} /></span>
      <span className="row-text">
        <span className="row-title-line"><span title={v.title} className="row-title">{v.title}</span></span>
        {guests && <span className="dim ellipsis">{guests}</span>}
      </span>
      <span className="row-text tight"><span className="ellipsis">{v.channel}</span><span className="dim small-13">{t.list.types[v.type]}</span></span>
      <span className="date-col"><span>{v.published_at && day(lang, v.published_at)}</span> {state} </span>
      <span className="num right dim">{v.duration > 0 && clock(v.duration)}</span>
      <span><Langs v={v} t={t} /></span>
      <span className="ledger">
        <span data-kind="avisos" className="total"><span className="num">{avisos(v)}</span>
          {d !== null && <Density d={d} t={t} lang={lang} active={sort === "densidad"} />}</span>
        {AVISOS.map((k) => (
          <span key={k} data-kind={k} className={`num${v.counts[k] ? "" : " zero"}`}
            style={v.counts[k] ? { color: `var(--st-${k === "puntualizacion" ? "contexto" : k}-text)` } : undefined}>
            {v.counts[k] || "–"}</span>
        ))}
        <span data-kind="contexto" className="num faint">{v.counts.contexto || "–"}</span>
        <span className="ledger-bar"><Mix v={v} t={t} max={max} /></span>
      </span>
    </a>
  );
}

/** "EN" when a video also exists in English. */
const En = ({ t }: { t: Texts }) => <span title={t.list.langs.both} className="codes">EN</span>;

/** A card of the grid, of one height (board "S4 · Arriba y cuadrícula v2"): the thumbnail with its state tag, the title
 * in a block of two lines, "canal · d mes · EN", then the mix bar and the density. Every card has every slot. */
function Card({ v, t, lang, max }: { v: Listed; t: Texts; lang: Lang; max: number }) {
  const d = density(v);
  const state = stateOf(v.video_id, v.published_at);
  return (
    <a href={href(lang, v.video_id)} className="video-card">
      <span className="thumb"><Art id={v.video_id} size="hq" />
        {state && <><span className={`thumb-tag s-${state}`}>{t.list.states[state]}</span>{" "}</>}
        {v.duration > 0 && <span className="badge num">{clock(v.duration)}</span>}<Watched id={v.video_id} /></span>
      <span title={v.title} className="card-title">{v.title}</span>
      <span className="card-meta">{v.channel}{v.published_at && <> · {day(lang, v.published_at, false)}</>}
        {v.langs.includes("en") && <> · <En t={t} /></>}</span>
      <span className="card-foot"><span className="card-bar"><Mix v={v} t={t} max={max} keep /></span>
        {d !== null && <Density d={d} t={t} lang={lang} />}</span>
    </a>
  );
}

const ListIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M2.5 4h11M2.5 8h11M2.5 12h11" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" /></svg>
);
const GridIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.4}>
    <rect x="2.5" y="2.5" width="4.5" height="4.5" rx="1" /><rect x="9" y="2.5" width="4.5" height="4.5" rx="1" />
    <rect x="2.5" y="9" width="4.5" height="4.5" rx="1" /><rect x="9" y="9" width="4.5" height="4.5" rx="1" /></svg>
);

/** The list's view: two icon buttons, "Lista" and "Cuadrícula", in a pill track. */
function ViewToggle({ t, view, pick }: { t: Texts; view: View; pick: (v: View) => void }) {
  const option = (v: View, label: string, icon: ReactNode) =>
    <button type="button" aria-pressed={view === v} aria-label={label} title={label} onClick={() => pick(v)}>{icon}</button>;
  return (
    <span role="group" aria-label={t.list.view.label} className="view-toggle">
      {option("lista", t.list.view.list, <ListIcon />)}{option("cuadricula", t.list.view.grid, <GridIcon />)}
    </span>
  );
}

/** A group's head: its label and count, and on a laptop the column heads that sort the list. */
function GroupHead({ label, n, t, sort, pick, phone }: { label: string; n: number; t: Texts; sort: Sort; pick: (s: Sort) => void; phone: boolean }) {
  // A sorted list is one group with no label (owner, copy pass): only the column heads.
  const title = <span className="group-label">{label && <><span>{label}</span><span className="num faint">{n}</span></>}</span>;
  if (phone) return label ? <li className="group-phone">{title}</li> : null;
  const head = (text: ReactNode, to: Sort, on: boolean, arrow = "↓", extra = "") => (
    <button type="button" aria-pressed={on} onClick={() => pick(to)} className={`col-head${extra}`}>{text}{on && <span aria-hidden="true">{arrow}</span>}</button>
  );
  return (
    <li className="group">
      {title}
      <span className="col-head">{t.list.heads.channel}</span>
      {head(t.list.heads.date, sort === "recientes" ? "antiguos" : "recientes", BY_DATE.includes(sort), sort === "antiguos" ? "↑" : "↓")}
      {head(t.list.heads.duration, "largos", sort === "largos", "↓", " right")}
      <span className="col-head">{t.list.heads.langs}</span>
      <span className="ledger heads">
        {head(t.list.heads.avisos, "avisos", sort === "avisos" || sort === "densidad", "↓", " center")}
        {AVISOS.map((k) => k === "falso"
          ? <button key={k} type="button" {...tip(`${t.word.falso} · ${t.list.byFalso}`)} aria-pressed={sort === "falso"} onClick={() => pick("falso")}
              className="mark-head"><MarkIcon mark={k} /><span>{t.list.short[k]}{sort === "falso" && "↓"}</span></button>
          : <span key={k} {...tip(t.word[k], true)} className="mark-head"><MarkIcon mark={k} /><span>{t.list.short[k]}</span></span>)}
        <span {...tip(t.word.contexto, true)} className="mark-head"><MarkIcon mark="contexto" /><span>{t.list.heads.notes}</span></span>
      </span>
    </li>
  );
}

/** A menu under a button: it opens on its search field or its picked option, arrows move, Esc or a click away closes. */
function usePopup() {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    (box.current?.querySelector<HTMLElement>("input") ?? box.current?.querySelector<HTMLElement>('[aria-selected="true"]'))?.focus();
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);
  const keys = (e: KeyboardEvent) => {
    if (e.key === "Escape") return setOpen(false);
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const options = [...box.current!.querySelectorAll<HTMLElement>('[role="option"]:not(:disabled)')];
    const at = options.indexOf(document.activeElement as HTMLElement);
    options[(at + (e.key === "ArrowDown" ? 1 : options.length - 1)) % options.length]?.focus();
  };
  return { open, setOpen, box, keys };
}

const Down = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5l3 3 3-3" fill="none" stroke="var(--t3)" strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" /></svg>
);
const Tick = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="var(--t1)" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /></svg>
);

/** "Orden <value>" and its menu of orders. */
function SortMenu({ t, sort, pick }: { t: Texts; sort: Sort; pick: (s: Sort) => void }) {
  const { open, setOpen, box, keys } = usePopup();
  return (
    <span ref={box} className="sort-menu" onKeyDown={keys}>
      <button type="button" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)} className="sort-button">
        <span className="sort-label">{t.list.sortLabel}</span> <span className="sort-value">{t.list.sorts[sort][0]}</span><Down />
      </button>
      {open && (
        <div role="listbox" aria-label={t.list.sortLabel} className="menu">
          {SORTS.map((s) => {
            const [label, hint] = t.list.sorts[s];
            return (
              <button key={s} type="button" role="option" title={hint} aria-selected={s === sort} onClick={() => { pick(s); setOpen(false); }}>
                <span className="tick">{s === sort && <Tick />}</span>
                <span className="option-text"><span className="option-label">{label}</span><span className="option-hint">{hint}</span></span>
              </button>
            );
          })}
        </div>
      )}
    </span>
  );
}

/** A filter option: its name and the number of videos it leaves; at 0 it cannot be picked. A second tap clears it. */
function Chip({ label, n, on, pick }: { label: string; n: number; on: boolean; pick: () => void }) {
  return (
    <button type="button" aria-pressed={on} disabled={!on && n === 0} onClick={pick} className="act chip">
      {label} <span className="num">{n}</span>
    </button>
  );
}

/** What the filters read in the address: the names of the channels and guests, the options of each facet. */
interface Scope { videos: Listed[]; f: Filters; t: Texts; lang: Lang; set: (k: Facet, value: string | null) => void }

const otherLang = (lang: Lang): Lang => (lang === "es" ? "en" : "es");

/** The × of a set filter in the toolbar: it clears that filter. */
const Clear = ({ t, name, clear }: { t: Texts; name: string; clear: () => void }) => (
  <button type="button" aria-label={t.list.filters.remove(name)} onClick={clear} className="tool-clear">
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" /></svg>
  </button>
);

/** "También en inglés": a toggle that shows ✓ and a × when set; it cannot be set when it would leave no video. */
function LangToggle({ videos, f, t, lang, set }: Scope) {
  const other = otherLang(lang);
  const on = f.idioma === other;
  return (
    <span className={`tool${on ? " set" : ""}`}>
      <button type="button" aria-pressed={on} disabled={!on && count(videos, f, "idioma", other) === 0}
        onClick={() => set("idioma", on ? null : other)} className="tool-button">
        {on && <Tick />}{t.list.filters.otherLang}
      </button>
      {on && <Clear t={t} name={t.list.filters.otherLang} clear={() => set("idioma", null)} />}
    </span>
  );
}

/** The name a facet's value shows: the other language, a channel's or a guest's name. */
function nameOf({ videos, t }: Pick<Scope, "videos" | "t">, k: Facet, value: string): string {
  if (k === "idioma") return t.list.filters.otherLang;
  return people(videos, k).find((p) => p.slug === value)?.name ?? value;
}

/** The channel or the guest menu: its pick on the button, every option with its count; the guests' has a search field. */
function FacetMenu({ videos, f, t, set, facet }: Scope & { facet: "canal" | "invitado" }) {
  const { open, setOpen, box, keys } = usePopup();
  const [find, setFind] = useState("");
  const all = facet === "canal" ? t.list.filters.allChannels : t.list.filters.allGuests;
  const label = facet === "canal" ? t.list.filters.channel : t.list.filters.guest;
  const picked = f[facet];
  const options = people(videos, facet).filter((p) => fold(p.name).includes(fold(find.trim())));
  const pick = (value: string | null) => { set(facet, value); setOpen(false); setFind(""); };
  const option = (value: string | null, name: string) => {
    const n = count(videos, f, facet, value);
    return (
      <button key={value ?? ""} type="button" role="option" aria-selected={picked === value} disabled={picked !== value && n === 0}
        onClick={() => pick(value)}>
        <span className="tick">{picked === value && <Tick />}</span>
        <span className="option-line"><span className="option-label">{name}</span> <span className="num">{n}</span></span>
      </button>
    );
  };
  return (
    <span ref={box} className={`facet-menu tool${picked ? " set" : ""}`} onKeyDown={keys}>
      <button type="button" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)} className="tool-button">
        {picked ? nameOf({ videos, t }, facet, picked) : label}<Down />
      </button>
      {picked && <Clear t={t} name={nameOf({ videos, t }, facet, picked)} clear={() => set(facet, null)} />}
      {open && (
        <div className="menu facet">
          {facet === "invitado" && (
            <input type="search" value={find} placeholder={t.list.filters.findGuest} aria-label={t.list.filters.findGuest}
              onChange={(e) => setFind(e.target.value)} className="menu-find" />
          )}
          <div role="listbox" aria-label={label}>
            {!find.trim() && option(null, all)}
            {options.map((p) => option(p.slug, p.name))}
          </div>
        </div>
      )}
    </span>
  );
}

const Glass = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
    <circle cx="7" cy="7" r="4.5" fill="none" stroke="var(--t3)" strokeWidth={1.4} /><path d="M10.5 10.5l3 3" stroke="var(--t3)" strokeWidth={1.4} strokeLinecap="round" /></svg>
);

/** The search: a flat field, 320 wide with its `/` key cap on a laptop, full width on a phone; never glass. */
function Search({ t, q, type, field, phone }: { t: Texts; q: string; type: (q: string) => void; field: RefObject<HTMLInputElement | null>; phone: boolean }) {
  return (
    <label className={`search-field${phone ? " wide" : ""}`}>
      <Glass />
      <input ref={field} type="search" value={q} placeholder={t.list.filters.search} aria-label={t.list.filters.search}
        onChange={(e) => type(e.target.value)} />
      {!phone && <kbd aria-hidden="true">/</kbd>}
    </label>
  );
}

/** No video matches: the title names the filters, then the ways out that leave at least one video. */
function NoResults({ videos, f, t, set, go }: Scope & { go: (f: Filters) => void }) {
  const what = [f.q.trim() && `«${f.q.trim()}»`, ...active(f).map((k) => nameOf({ videos, t }, k, f[k]!))].filter(Boolean).join(" · ");
  return (
    <section className="no-results">
      <h2>{t.list.filters.none(what)}</h2>
      <div className="ways-out">
        {f.q.trim() && <button type="button" onClick={() => go({ ...f, q: "" })} className="act hi">{t.list.filters.dropSearch(f.q.trim())}</button>}
        {active(f).map((k) => {
          const n = count(videos, f, k, null);
          return n > 0 && (
            <button key={k} type="button" onClick={() => set(k, null)} className="act hi">{t.list.filters.drop(nameOf({ videos, t }, k, f[k]!), n)}</button>
          );
        })}
        <button type="button" onClick={() => go(NONE)} className="act hi">{t.list.filters.all(videos.length)}</button>
      </div>
    </section>
  );
}

/** The phone's sheet "Filtros": the channels, a guest search and the language, each counted with the others kept; every
 * pick applies at once, its bone button counts what is left and closes it, "Restablecer" clears them. */
function FilterSheet({ videos, f, t, lang, set, n, reset, close, below }:
  Scope & { n: number; reset: () => void; close: () => void; below: RefObject<HTMLElement | null> }) {
  const [find, setFind] = useState("");
  const other = otherLang(lang);
  const chips = (k: "canal" | "invitado", list: { slug: string; name: string }[]) => list.map((p) => (
    <Chip key={p.slug} label={p.name} n={count(videos, f, k, p.slug)} on={f[k] === p.slug} pick={() => set(k, f[k] === p.slug ? null : p.slug)} />
  ));
  const guests = people(videos, "invitado").filter((p) => fold(p.name).includes(fold(find.trim())));
  return (
    <Sheet label={t.list.filters.filters} head={<span className="sheet-title">{t.list.filters.filters}</span>} close={close} closeLabel={t.close} below={below}>
      <div className="sheet-part"><h3>{t.list.filters.channel}</h3><div className="sheet-chips">{chips("canal", people(videos, "canal"))}</div></div>
      <div className="sheet-part"><h3>{t.list.filters.guest}</h3>
        <input type="search" value={find} placeholder={t.list.filters.findGuest} aria-label={t.list.filters.findGuest}
          onChange={(e) => setFind(e.target.value)} className="menu-find" />
        <div className="sheet-chips">{chips("invitado", guests)}</div></div>
      <div className="sheet-part"><h3>{t.list.filters.lang}</h3><div className="sheet-chips">
        <Chip label={t.list.filters.otherLang} n={count(videos, f, "idioma", other)} on={f.idioma === other}
          pick={() => set("idioma", f.idioma === other ? null : other)} /></div></div>
      <div className="sheet-foot">
        <button type="button" onClick={reset} className="act">{t.list.filters.reset}</button>
        <button type="button" onClick={close} className="bone-button">{t.list.filters.show(n)}</button>
      </div>
    </Sheet>
  );
}

/** The list of every approved video. */
export function List({ lang, videos }: { lang: Lang; videos: Listed[] }) {
  const t = TEXTS[lang];
  const phone = useMedia(READING_PHONE);
  // The laptop row's columns need 1024 px: in the one-column width (f7 §19.10 §6) the rows take their phone form.
  const narrow = useMedia(ONE_COLUMN);
  // The sort and the filters live in the address: a reload or a shared link shows the same list.
  const [search, setSearch] = useState(() => {
    // An old link's `?orden=graves` keeps its order under the new key (copy pass).
    const q = new URLSearchParams(location.search);
    if (q.get("orden") === "graves") q.set("orden", "falso-enganoso");
    // There is no filter by kind of aviso any more (owner, 2026-11-22): an old `tipo` leaves the address.
    q.delete("tipo");
    // With no view in the address, the list opens in the view this browser last picked; the address then holds it.
    if (!q.has("vista") && lastView() === "cuadricula") q.set("vista", "cuadricula");
    if (`?${q}` !== (location.search || "?")) history.replaceState(history.state, "", `${location.pathname}?${q}${location.hash}`);
    return location.search;
  });
  const [sheet, setSheet] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const back = () => setSearch(location.search);
    // The `/` key goes to the search, unless the reader is typing.
    const slash = (e: globalThis.KeyboardEvent) => {
      const at = e.target as HTMLElement;
      if (e.key !== "/" || at.closest?.("input, textarea, [contenteditable]")) return;
      e.preventDefault();
      field.current?.focus();
    };
    addEventListener("popstate", back);
    document.addEventListener("keydown", slash);
    return () => { removeEventListener("popstate", back); document.removeEventListener("keydown", slash); };
  }, []);
  const sort = sortOf(search);
  const f = read(search);
  // The phone keeps its rows (board ListPhone has no grid).
  const view: View = phone ? "lista" : viewOf(search) ?? "lista";
  const go = (next: Filters, s: Sort = sort, push = true, v: View = view) => {
    const url = `${location.pathname}${write(next, s, "recientes", v)}`;
    if (push) history.pushState(null, "", url);
    else history.replaceState(null, "", url);
    setSearch(location.search);
  };
  const pick = (s: Sort) => { if (s !== sort) go(f, s); };
  const set = (k: Facet, value: string | null) => go({ ...f, [k]: value });
  // A search pushes one history entry as it starts; each further key replaces it.
  const type = (q: string) => go({ ...f, q }, sort, !f.q);
  const show = (v: View) => {
    keepView(v);
    if (v !== view) go(f, sort, true, v);
  };
  // Without a pointer, the thumbnail nearest the screen's middle wakes when a scroll ends; at load, all sleep.
  const hoverless = useMedia(NO_HOVER);
  useEffect(() => {
    if (!hoverless) return;
    let timer: ReturnType<typeof setTimeout>;
    const wake = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const middle = innerHeight / 2;
        const thumbs = [...document.querySelectorAll<HTMLElement>(".list .thumb, .list .lead-thumb")];
        const near = (el: HTMLElement) => { const r = el.getBoundingClientRect(); return Math.abs(r.top + r.height / 2 - middle); };
        const nearest = thumbs.reduce<HTMLElement | null>((a, el) => (!a || near(el) < near(a) ? el : a), null);
        for (const el of thumbs) el.classList.toggle("awake", el === nearest);
      }, 150);
    };
    addEventListener("scroll", wake, { passive: true });
    return () => { clearTimeout(timer); removeEventListener("scroll", wake); };
  }, [hoverless]);

  if (!videos.length) {
    return (<>
      <main className="list">
        <section className="empty-list">
          <h2>{t.list.empty}</h2>
          <a href={`/${lang}/${t.list.howPath}`}>{t.list.how}</a>
        </section>
        <div aria-hidden="true" className="the-line" />
      </main>
      <Footer lang={lang} />
    </>);
  }

  const filtered = any(f);
  const shown = videos.filter((v) => matches(v, f));
  const sorted = shown.sort(ORDER[sort]);
  const max = Math.max(...videos.map((v) => density(v) ?? 0)) || 1;
  const grid = view === "cuadricula";
  const lead = sort === "recientes" && !filtered && !grid ? sorted[0] : null;
  const rest = lead ? sorted.slice(1) : sorted;
  const byDate = BY_DATE.includes(sort);
  // Consecutive videos of one week share a group; any other order is one group with no label.
  const groups: { label: string; videos: Listed[] }[] = [];
  for (const v of rest) {
    const label = byDate ? weekOf(lang, t, v.published_at, !!lead) : "";
    if (groups.at(-1)?.label === label) groups.at(-1)!.videos.push(v);
    else groups.push({ label, videos: [v] });
  }
  const scope = { videos, f, t, lang, set };
  const status = filtered && (
    <p className="filter-status">{t.list.filters.of(shown.length, videos.length)} <span aria-hidden="true">·</span>{" "}
      <button type="button" onClick={() => go(NONE)} className="link-inline">{t.list.filters.clear}</button></p>
  );
  const on = active(f);

  return (<>
    <main className="list">
      <h1 className="list-title">{t.list.title} <span className="num">{videos.length}</span></h1>
      {phone ? (<>
        <div role="search" aria-label={t.list.filters.toolbar} className="toolbar">
          <Search t={t} q={f.q} type={type} field={field} phone />
          <div className="toolbar-row">
            <SortMenu t={t} sort={sort} pick={pick} />
            <button type="button" aria-haspopup="dialog" onClick={() => setSheet(true)} className={`tool tool-button filters-button${on.length ? " set" : ""}`}>
              {t.list.filters.filters}{on.length > 0 && <span className="count-badge num">{on.length}</span>}</button>
          </div>
        </div>
        {status}
        {sheet && <FilterSheet {...scope} n={shown.length} reset={() => go({ ...NONE, q: f.q })} close={() => setSheet(false)} below={field} />}
      </>) : (<>
        <div role="search" aria-label={t.list.filters.toolbar} className="toolbar">
          <div className="toolbar-side">
            <Search t={t} q={f.q} type={type} field={field} phone={false} />
            <FacetMenu {...scope} facet="canal" />
            <FacetMenu {...scope} facet="invitado" />
            <LangToggle {...scope} />
          </div>
          <div className="toolbar-side"><SortMenu t={t} sort={sort} pick={pick} /><ViewToggle t={t} view={view} pick={show} /></div>
        </div>
        {status}
      </>)}
      {lead && <Lead v={lead} t={t} lang={lang} max={max} phone={phone} />}
      {!grid && <div aria-hidden="true" className="the-line" />}
      {shown.length && grid ? (
        <ol aria-label={t.list.listOf(t.list.sorts[sort][2])} className="cards">
          {sorted.map((v) => <li key={v.video_id}><Card v={v} t={t} lang={lang} max={max} /></li>)}
        </ol>
      ) : shown.length ? (
        <ol aria-label={t.list.listOf(t.list.sorts[sort][2])} className="rows-list">
          {groups.map((g) => (
            <Fragment key={g.label || "sorted"}>
              <GroupHead label={g.label} n={g.videos.length} t={t} sort={sort} pick={pick} phone={narrow} />
              {g.videos.map((v) => (
                <li key={v.video_id}>
                  <Row v={v} t={t} lang={lang} max={max} sort={sort} phone={narrow} />
                </li>
              ))}
            </Fragment>
          ))}
        </ol>
      ) : <NoResults {...scope} go={go} />}
    </main>
    <Footer lang={lang} />
  </>);
}

/** The list while it loads: the sentence says so and grey blocks hold the lead's and the rows' places. */
export function Loading({ lang }: { lang: Lang }) {
  const t = TEXTS[lang];
  return (<>
    <main aria-busy="true" className="list">
      <h1 className="list-title">{t.list.title}</h1>
      <p className="sr">{t.list.loading}</p>
      <div className="lead">
        <span className="block lead-thumb" />
        {/* The reduced lead: kicker, title, "canal · fecha", verdict row, lane and button. */}
        <span className="lead-text"><span className="block" style={{ width: 120 }} /><span className="block tall" style={{ width: "80%" }} />
          <span className="block" style={{ width: "40%" }} /><span className="block" style={{ width: "70%", marginTop: 16 }} />
          <span className="block lane-block" /><span className="block pill-block" /></span>
      </div>
      <div aria-hidden="true" className="the-line" />
      <ol className="rows-list">
        {[220, 180, 240].map((w) => <li key={w} className="row-laptop loading-row"><span className="block thumb" />
          <span className="row-text"><span className="block tall" style={{ width: w, maxWidth: "100%" }} /><span className="block" style={{ width: "45%" }} /></span></li>)}
      </ol>
    </main>
    <Footer lang={lang} />
  </>);
}
