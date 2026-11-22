// A guest's card to take away (spec S11): a 1:1 image drawn from the profile's own figures (board S5Export), the 4:5
// InterviewCard ported from the helper's summary.html (owner review, 2026-11-22), or a paper sheet for A4 or Letter with
// every aviso. Every card ends with the disclosure line, and no control removes it. The 1:1 band is plan C of the canvas
// (night with the line); the 4:5 plate is the video's YouTube thumbnail, and plan C when it cannot load.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal, flushSync } from "react-dom";
import { domToBlob } from "modern-screenshot";
import { encode } from "uqr";
import wordmark from "../brand/calvet-quilla-nav.svg";
import inkmark from "../brand/calvet-quilla-night.svg";
import { allSpoken, guestFigures, level, LIT, useNumbers } from "./figures";
import { half, useThumb, type Half } from "./faces";
import { AVISOS, kindOf, markFor, type Flag, type Kind } from "./marks";
import { TEXTS, type Lang } from "./texts";
import { clock, MarkIcon, profilePath, READING_PHONE, role, short, slug, useMedia, type Meta, type Summary } from "./Viewer";

type Format = "11" | "45" | "print";
type Paper = "a4" | "letter";
const SIZE: Record<Format | Paper, [number, number]> = { "11": [1080, 1080], "45": [1080, 1350], print: [794, 1123], a4: [794, 1123], letter: [816, 1056] };
const ALT_MAX = 1000;
const day = (lang: Lang, date: Date) =>
  new Intl.DateTimeFormat(lang === "en" ? "en-GB" : "es", { day: "numeric", month: "short", year: "numeric" }).format(date);

type Props = { lang: Lang; meta: Meta; flags: Flag[]; name: string; card: Summary; gravest: Flag[] };

/** Everything a card says, in the card's language: the same numbers as the profile. */
function useCard({ meta, flags, name, card, gravest }: Props, lang: Lang) {
  const t = TEXTS[lang];
  const n = useNumbers(lang);
  const f = guestFigures(meta, flags, name, card);
  const url = `${location.origin}${profilePath(lang, meta.video_id, name)}`;
  const published = meta.published_at ? day(lang, new Date(`${meta.published_at}T00:00:00Z`)) : null;
  return {
    t, n, f, url, gravest, lang, meta, card, fullName: name, name: short(name), role: role(name) ?? t.profile.guest.toLowerCase(),
    published, ai: t.card.ai(day(lang, new Date())),
    mixed: AVISOS.filter((k) => f.ofKind(k).length),
    timeline: [...f.avisos].sort((a, b) => a.t - b.t),
  };
}
type Card = ReturnType<typeof useCard>;

const Meter = ({ rate }: { rate: number }) => (
  <span aria-hidden="true" className="ficha-meter big">
    {[1, 2, 3].map((i) => <span key={i} className={i <= LIT[level(rate)] ? "lit" : ""} />)}
  </span>
);

const Mix = ({ c }: { c: Card }) => (
  <span aria-hidden="true" data-part="mix" className="mix ficha-mix">
    {c.mixed.map((k) => <span key={k} className={`seg m-${k}`} style={{ flexGrow: c.f.ofKind(k).length }} />)}
  </span>
);
const Legend = ({ c, size }: { c: Card; size: number }) => (
  <span className="ficha-legend">
    {c.mixed.map((k) => (
      <span key={k}><MarkIcon mark={k} size={size} /><span style={{ color: `var(--st-${markFor(k)}-text)` }}>{c.t.word[k]}</span>{" "}
        <span className="num">{c.f.ofKind(k).length}</span></span>
    ))}
  </span>
);

/** The night band of an image card: the wordmark, "Ficha", and the line with its V under the wordmark's V. */
const Band = ({ c, floor }: { c: Card; floor: number }) => (
  <div className="ficha-band" style={{ height: floor + 64 }}>
    <img src={wordmark} alt="Calvet" className="ficha-mark" />
    <span className="ficha-kicker">{c.t.card.kicker}</span>
    <svg aria-hidden="true" width="1080" height="48" style={{ top: floor }} className="ficha-keel">
      <path d="M0 .5 H151.46 M184.95 .5 H1080" className="keel-line" />
      <path d="M151.46 0.5 L163.5 45.5 L173.5 45.5 L184.95 0.5" strokeLinejoin="miter" className="keel-v" />
    </svg>
  </div>
);

// A long name shrinks to fit the card's 936 px on one line (about half an em per letter in Newsreader).
const fit = (name: string, size: number) => ({ fontSize: Math.min(size, Math.floor(936 / (0.5 * name.length))) });
const rateLabel = (c: Card) => (c.f.speech ? c.t.card.rate : c.t.card.rateVideo);
const correctValue = (c: Card) => (c.f.correct === null ? "–" : <>{c.f.correct}<span className="unit"> %</span></>);

function Square({ c }: { c: Card }) {
  const { t, n, f } = c;
  const line = (f.share !== null || f.eludedPct !== null) && (
    <p className="ficha-line">
      {f.share !== null && <>{t.card.speaks} <span className="num">{n.one(f.share)} %</span> {t.card.ofTime}</>}
      {f.share !== null && f.eludedPct !== null && ` ${t.card.and} `}
      {f.eludedPct !== null && <>{f.share === null ? t.card.dodges : t.card.dodgesAfter} <span className="num">{t.card.of(f.eluded, c.card.asked)}</span> {t.card.questions}</>}.
    </p>
  );
  return (<>
    <Band c={c} floor={400} />
    <div className="ficha-body" style={{ top: 464 }}>
      <div style={fit(c.name, 88)} className="ficha-name">{c.name}</div>
      <div className="ficha-sub">{[c.role, c.meta.channel, c.published].filter(Boolean).join(" · ")}</div>
      <div className="ficha-big">
        <div><span className="ficha-value">{n.one(f.rate)}{f.speech && <Meter rate={f.rate} />}</span>
          <span className="ficha-label">{rateLabel(c)}{f.speech && ` · ${t.profile.levels[level(f.rate)]}`}</span></div>
        <div><span className="ficha-value">{correctValue(c)}</span>
          <span className="ficha-label">{t.card.correct} · {t.card.of(c.card.verdicts.correct, c.card.checked)}</span></div>
      </div>
      {line}
    </div>
  </>);
}

// The InterviewCard (helper summary.py `page()`): the plate is the video's thumbnail (faces.ts).
const VERDICTS = ["false", "misleading", "nitpick", "correct"] as const; // the verdict bar, false first
const VERDICT_INK = { false: "falso", misleading: "enganoso", nitpick: "contexto", correct: "correcto" } as const;
const LEVELS = ["serious", "moderate", "minor"] as const;
const DEVICE_SLOTS = 6;
const plural = (n: number, forms: string[]) => forms[n === 1 ? 0 : 1];
/** Whitespace folded, then cut at a word with "…" past `size` characters. */
const cut = (text: string, size: number) => {
  const s = text.split(/\s+/).join(" ").trim();
  return s.length <= size ? s : `${s.slice(0, size).replace(/\s+\S*$/, "").replace(/[,.;:]+$/, "")}…`;
};
/** "41 min" or "1 h 52 min". */
const length = (seconds: number) => {
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min` : `${m} min`;
};
/** The programme, not the whole YouTube title: "Show No. 12 - Name | topics" → "Show No. 12". */
const programme = (title: string) => title.split(/ [-|–—] /)[0] || title;
const source = (f: Flag) => (f.sources?.[0] ? f.sources[0].publisher.split(/\s+[(–—-]\s*/)[0] : "");

/** Everything the InterviewCard says, shared by the card and its alt text. */
function interview(c: Card) {
  const ii = c.t.card.ii;
  const v = c.card.verdicts;
  const me = c.meta.people?.[c.fullName];
  const featured = c.gravest.map((f) => {
    const k = kindOf(f);
    const level = f.judge?.severity;
    const name = k === "falso" || k === "enganoso" ? c.t.word[k] : c.t.label[f.label as keyof typeof c.t.label] ?? c.t.word[k];
    return { f, k, verdict: ii.verdict(name, level ? ii.levels[level][0] : null), source: source(f) };
  });
  const devices = c.card.devices.map((d) => ({ label: c.t.label[d.label as keyof typeof c.t.label] ?? d.label, count: d.count }));
  const shown = devices.length <= DEVICE_SLOTS ? devices : [
    ...devices.slice(0, DEVICE_SLOTS - 1),
    { label: ii.more(devices.length - DEVICE_SLOTS + 1), count: devices.slice(DEVICE_SLOTS - 1).reduce((a, d) => a + d.count, 0) },
  ];
  return {
    ii, v, featured, devices: shown,
    wrong: v.false + v.misleading,
    kicker: [ii.kind[c.meta.type] ?? ii.kind.interview, c.published].filter(Boolean).join(" · "),
    title: programme(c.meta.title || c.meta.video_id),
    length: me?.spoken_s && c.meta.duration ? ii.speaking(length(me.spoken_s), length(c.meta.duration))
      : c.meta.duration ? length(c.meta.duration) : "",
    dodged: <T,>(b: (n: number) => T) => c.card.partial
      ? ii.dodgedPartial(b(c.card.dodged), b(c.card.partial), b(c.card.asked))
      : ii.dodged(b(c.card.dodged), b(c.card.asked)),
    // A debate of two shows the guest's half of the thumbnail (faces.ts).
    half: half(c.meta.guests, c.fullName, c.meta.swap),
  };
}

/** The seal of Correcto (tokens: disc in a ring, glyph ✓); the other verdicts draw with MarkIcon. */
const Correct = ({ size }: { size: number }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
    <circle cx="8" cy="8" r="7" fill="none" stroke="var(--st-correcto)" strokeWidth={1.5} /><circle cx="8" cy="8" r="4.75" fill="var(--st-correcto)" />
    <path d="M5.9 8.1l1.4 1.4 2.8-3" fill="none" stroke="var(--st-glyph)" strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const VerdictIcon = ({ k }: { k: (typeof VERDICTS)[number] }) =>
  k === "correct" ? <Correct size={30} /> : <MarkIcon mark={({ false: "falso", misleading: "enganoso", nitpick: "puntualizacion" } as const)[k]} size={30} />;

/** The plate: the thumbnail dimmed, a 45° band at full colour, cut by the Fault; plan C when the thumbnail cannot load. */
function Plate({ c, half }: { c: Card; half: Half | null }) {
  const { src, onError, onLoad } = useThumb(c.meta.video_id);
  const crop = half ? `half ${half}` : "";
  const img = (className: string) => (
    <img src={src!} alt="" crossOrigin="anonymous" data-half={half ?? undefined} className={className} onError={onError} onLoad={onLoad} />
  );
  return (
    <div data-part="plate" className="ii-plate">
      {src ? <>
        {img(`ii-dim ${crop}`)}
        {half && <div className="ii-fade" />}
        <div className="ii-band">{img(crop)}</div>
        {half && <div className="ii-fade-b" />}
      </> : <div className="ii-none" />}
      <div className="ii-edge" /><div className="ii-veil" /><div className="ii-side" />
    </div>
  );
}

function Interview({ c }: { c: Card }) {
  const x = interview(c);
  const { ii, v } = x;
  const size = c.name.length <= 18 ? 92 : c.name.length <= 24 ? 72 : 56;
  return (<>
    <Plate c={c} half={x.half} />
    <div aria-hidden="true" className="ii-fault"><i className="f-a" /><i className="f-d" /><i className="f-b" /></div>
    <div className="ii-kicker">{x.kicker}</div>
    <img src={wordmark} alt="Calvet" className="ii-logo" />
    <div style={{ fontSize: size }} className="ii-name">{c.name}</div>
    <div className="ii-sub">{[`«${cut(x.title, 40)}»`, x.length].filter(Boolean).join(" · ")}</div>
    <div className="ii-hook">
      <div className="ii-big num">{x.wrong}<span> {ii.of} {c.card.checked}</span></div>
      <p>{ii.hook[0]}<br /> {ii.hook[1]}</p>
    </div>
    <div data-part="bar" className="ii-bar">
      {VERDICTS.filter((k) => v[k]).map((k) => <i key={k} style={{ flexGrow: v[k], background: `var(--st-${VERDICT_INK[k]})` }} />)}
    </div>
    <div className="ii-legend">
      {VERDICTS.map((k) => <div key={k}><VerdictIcon k={k} /><span><b className="num">{v[k]}</b> {plural(v[k], ii.verdicts[k])}</span></div>)}
    </div>
    <div className="ii-weight"><span className="ii-h">{ii.weight}:</span>{" "}
      <span>{LEVELS.map((s, i) => <span key={s}>{i > 0 && " · "}<b className="num">{c.card.severity[s]}</b> {plural(c.card.severity[s], ii.levels[s])}</span>)}</span>
    </div>
    <div className="ii-devices"><div className="ii-h">{ii.devices}</div>
      <div className="ii-grid">
        {x.devices.length ? x.devices.map((d) => (
          <div key={d.label} className="ii-row"><MarkIcon mark="retorica" size={30} /><span className="ii-grow">{d.label}</span>
            <span className="num ii-bone">×{d.count}</span></div>
        )) : <div className="ii-row ii-muted">{ii.noDevices}</div>}
      </div>
    </div>
    <div className="ii-row ii-dodged"><MarkIcon mark="evasiva" size={30} />
      <span>{x.dodged((n) => n).map((part, i) => (i % 2 ? <b key={i} className="num">{part}</b> : part))}</span></div>
    <div className="ii-featured"><div className="ii-h">{ii.featured}</div>
      <div className="ii-items">
        {x.featured.length ? x.featured.map(({ f, k, verdict, source }) => (
          <div key={f.id} className="ii-item">
            <div className="ii-q"><MarkIcon mark={k} size={30} />
              <span lang={c.meta.lang} className="ii-quote">«{cut(f.quote, 60)}»</span><span className="num ii-min">{clock(f.t)}</span></div>
            <div className="ii-fix"><b style={{ color: `var(--st-${markFor(k)}-text)` }}>{verdict}</b>{" "}
              <span lang={c.meta.lang}>{cut(f.reason, 92)}</span>{source && <> <span className="ii-src">{cut(source, 30)}</span></>}</div>
          </div>
        )) : <div className="ii-item ii-muted">{ii.noFeatured}</div>}
      </div>
    </div>
  </>);
}

/** A QR code of `url`, one square per dark module, in the ink of the paper. */
function Qr({ url }: { url: string }) {
  const { data, size } = encode(url, { border: 0 });
  const d = data.flatMap((row, y) => row.map((on, x) => (on ? `M${x} ${y}h1v1h-1z` : ""))).join("");
  return <svg role="img" aria-label={url} data-part="qr" viewBox={`0 0 ${size} ${size}`} width="72" height="72" className="ficha-qr"><path d={d} /></svg>;
}

function PaperSheet({ c, paper }: { c: Card; paper: Paper }) {
  const { t, n, f, meta } = c;
  const p = t.profile;
  const spoken = allSpoken(meta);
  const people = meta.people ?? {};
  const voiced = [c.fullName, ...meta.guests.filter((g) => g !== c.fullName), ...Object.keys(people).filter((x) => !meta.guests.includes(x))]
    .filter((x) => people[x]?.spoken_s);
  const pct = (s: number) => `${(s / meta.duration) * 100}%`;
  const figure = (value: ReactNode, label: string) =>
    <div data-part="figure"><span className="paper-value num">{value}</span><span className="paper-label">{label}</span></div>;
  return (<>
    <div className="paper-head"><img src={inkmark} alt="Calvet" className="paper-mark" /><span>{t.card.paperHead(t.card[paper], day(c.lang, new Date()))}</span></div>
    <div className="paper-hero">
      <div aria-hidden="true" className="paper-cover"><span>{c.name}</span></div>
      <div className="paper-id">
        <span>{c.role}</span>
        <span className="paper-name">{c.name}</span>
        <span>{[meta.title, meta.channel, meta.duration > 0 && clock(meta.duration)].filter(Boolean).join(" · ")}</span>
      </div>
      <svg aria-hidden="true" height="33" className="paper-keel">
        <path d="M0 .5 H27.46 M60.95 .5 H2000" className="keel-line" />
        <path d="M27.46 0.5 L39.5 30.5 L49.5 30.5 L60.95 0.5" strokeLinejoin="miter" className="keel-v" />
      </svg>
    </div>
    <div className="paper-figures">
      {figure(f.share === null ? "–" : `${n.one(f.share)} %`, f.me ? `${p.share} · ${p.turnsMean(f.me.turns, clock(Math.round(f.me.spoken_s / (f.me.turns || 1))))}` : p.share)}
      {figure(n.one(f.rate), `${f.speech ? p.rate : p.rateVideo}${f.speech ? ` · ${p.levels[level(f.rate)]}` : ""}`)}
      {figure(f.correct === null ? "–" : `${f.correct} %`, `${p.correct} · ${t.card.of(c.card.verdicts.correct, c.card.checked)}`)}
      {figure(n.one(f.graves), f.speech ? p.graves : p.gravesVideo)}
      {figure(c.card.asked ? `${f.eluded}/${c.card.asked}` : "–", p.dodged)}
      {figure(f.me?.longest_s ? clock(f.me.longest_s) : "–", p.longest)}
    </div>
    {voiced.length > 0 && (
      <div data-part="voices" className="paper-voices">
        <span className="paper-title">{p.who}</span>
        {voiced.map((who) => (
          <div key={who} className={`paper-voice${who === c.fullName ? " me" : ""}`}>
            <span>{short(who)}</span>
            <span className="paper-lane">{(meta.turns ?? []).filter((x) => x.person === who).map((x) =>
              <span key={x.start} style={{ left: pct(x.start), width: pct(x.end - x.start) }} />)}</span>
            <span className="num">{n.one(Math.round((1000 * people[who].spoken_s) / spoken) / 10)} %</span>
          </div>
        ))}
      </div>
    )}
    <div className="paper-mixes"><Mix c={c} /><Legend c={c} size={11} /></div>
    <span className="paper-title">{t.card.avisosTitle(f.avisos.length)}</span>
    <ol className="paper-avisos">
      {c.timeline.map((x) => {
        const k = kindOf(x);
        const rank = c.gravest.indexOf(x);
        const device = k === "retorica" || k === "evasiva" ? t.label[x.label] : null;
        return (
          <li key={x.id} data-part="aviso">
            <span className="num">{clock(x.t)}</span><MarkIcon mark={k} size={11} />
            <span>{rank >= 0 && <b data-part="rank" className="paper-rank num">{rank + 1}</b>}
              <b style={{ color: `var(--st-${markFor(k)}-text)` }}>{t.word[k]}{device && ` · ${device}`}.</b>{" "}
              <span lang={meta.lang} className="paper-quote">«{x.quote}»</span> <span lang={meta.lang} className="paper-reason">{x.reason}</span></span>
          </li>
        );
      })}
    </ol>
    <div className="paper-foot">
      <Qr url={c.url} />
      <span><span className="paper-url">{t.card.more} {c.url.replace(/^https?:\/\//, "")}</span>
        <span className="ficha-ai paper-ai">{c.ai}</span></span>
    </div>
  </>);
}

/** The card of `format` at its full pixel size; `node` gets the element to draw. */
function CardFace({ c, format, paper, node }: { c: Card; format: Format; paper: Paper; node?: (el: HTMLDivElement | null) => void }) {
  const [w, h] = SIZE[format === "print" ? paper : format];
  if (format === "print") {
    return <div ref={node} lang={c.lang} data-card="print" data-paper={paper} className="paper" style={{ width: w, minHeight: h }}><PaperSheet c={c} paper={paper} /></div>;
  }
  return (
    <div ref={node} lang={c.lang} data-card={format} className={`ficha${format === "45" ? " ficha-ii" : ""}`} style={{ width: w, height: h }}>
      {format === "11" ? <Square c={c} /> : <Interview c={c} />}
      <p className="ficha-ai">{c.ai}</p>
    </div>
  );
}

/** What the card shows, in words, for a screen reader or a post's alt text; the 4:5 one as the helper's alt_text. */
function altText(c: Card, format: Format) {
  const { t, n, f, meta } = c;
  const a = t.card.alt;
  let parts: string;
  if (format === "45") {
    const x = interview(c);
    const { ii } = x;
    const counts = VERDICTS.filter((k) => x.v[k]).map((k) => `${x.v[k]} ${plural(x.v[k], k === "nitpick" ? ii.nitpicks : ii.verdicts[k])}`).join(", ");
    const weight = LEVELS.filter((s) => c.card.severity[s]).map((s) => `${c.card.severity[s]} ${plural(c.card.severity[s], ii.levels[s])}`).join(", ");
    const head = [
      ii.altOf(c.name, cut(x.title, 80), c.published),
      `${ii.altHook(x.wrong, c.card.checked)}${counts ? `: ${counts}` : ""}.`,
      weight && `${ii.weight}: ${weight}.`,
      x.devices.length > 0 && `${ii.devices}: ${x.devices.slice(0, 3).map((d) => `${d.label} ×${d.count}`).join(", ")}.`,
      `${x.dodged(String).join("")}.`,
    ].filter(Boolean).join(" ");
    const room = Math.floor((ALT_MAX - 3 - head.length - c.ai.length) / Math.max(x.featured.length, 1)) - 1;
    const items = x.featured.map(({ f: g, verdict, source }) =>
      cut(`${clock(g.t)} «${g.quote}» ${verdict} ${g.reason}${source ? ` (${source})` : ""}`, Math.max(room, 0)));
    parts = [head, ...items].filter(Boolean).join(" ");
  } else {
    parts = [
      a.of(c.name, c.role, meta.title, [meta.channel, c.published].filter(Boolean).join(", ")),
      f.share !== null && a.share(`${n.one(f.share)} %`),
      a.rate(n.one(f.rate), f.speech, c.mixed.map((k) => `${f.ofKind(k).length} ${t.word[k]}`).join(", ")),
      c.card.checked > 0 && a.correct(c.card.verdicts.correct, c.card.checked),
      c.card.asked > 0 && a.eluded(f.eluded, c.card.asked),
      format === "print" && a.graves(n.one(f.graves), f.speech),
    ].filter(Boolean).join(" ");
  }
  const room = ALT_MAX - 2 - c.ai.length;
  return `${parts.length > room ? `${parts.slice(0, room - 1)}…` : parts} ${c.ai}`;
}

/** The sheet of "Descargar ficha": the format, the language, the preview, the alt text and the actions. */
export function CardSheet(props: Props & { close: () => void }) {
  const phone = useMedia(READING_PHONE);
  const [format, setFormat] = useState<Format>("45");
  const [paper, setPaper] = useState<Paper>("a4");
  const [lang, setLang] = useState<Lang>(props.lang);
  const [printing, setPrinting] = useState(false);
  const shown = useRef<HTMLDivElement | null>(null);
  const closer = useRef<HTMLButtonElement>(null);
  const c = useCard(props, lang);
  const t = TEXTS[props.lang].card;
  const alt = altText(c, format);
  const file = `${slug(props.name)}-${props.meta.video_id}-${format === "11" ? "1x1" : "4x5"}${lang === props.lang ? "" : `-${lang}`}.png`;

  useEffect(() => {
    closer.current?.focus();
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") props.close(); };
    const done = () => { delete document.documentElement.dataset.print; setPrinting(false); };
    addEventListener("keydown", esc);
    addEventListener("afterprint", done);
    return () => { removeEventListener("keydown", esc); removeEventListener("afterprint", done); };
  }, []);

  const png = async () => {
    const [width, height] = SIZE[format];
    await document.fonts?.ready;
    return domToBlob(shown.current!, { width, height, scale: 1, type: "image/png" });
  };
  const download = async () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await png());
    a.download = file;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  const share = async () => {
    const title = `${c.name} · ${props.meta.title}`;
    const image = format === "print" ? null : new File([await png()], file, { type: "image/png" });
    const data = image && navigator.canShare?.({ files: [image] }) ? { title, url: c.url, files: [image] } : { title, url: c.url };
    await navigator.share(data).catch(() => {});
  };
  const print = () => {
    flushSync(() => setPrinting(true));
    document.documentElement.dataset.print = paper;
    window.print();
  };

  const radios = <T extends string>(label: string, value: T, set: (v: T) => void, options: [T, ReactNode][], className = "") => (
    <div role="radiogroup" aria-label={label} className={`ficha-radios ${className}`}>
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={v === value} onClick={() => set(v)}>{text}</button>
      ))}
    </div>
  );
  const [w, h] = SIZE[format === "print" ? paper : format];
  const scale = (phone ? 173 : 324) / w;
  const canShare = typeof navigator.share === "function";

  return (<>
    <div aria-hidden="true" onClick={props.close} className="ficha-scrim" />
    <div role="dialog" aria-modal="true" aria-label={t.title} className={`ficha-sheet${phone ? " phone" : ""}`}>
      {phone && <span aria-hidden="true" className="grab" />}
      <div className="ficha-sheet-head">
        <span>{t.title}</span>
        <button ref={closer} type="button" aria-label={TEXTS[props.lang].close} onClick={props.close} className="icon">×</button>
      </div>
      <div className="ficha-sheet-body">
        <div className="ficha-field"><span>{t.format}</span>
          {radios(t.format, format, setFormat, [
            ["11", <>{t.square} <span className="num">1:1</span></>],
            ["45", <>{t.vertical} <span className="num">4:5</span></>],
            ["print", t.forPrint],
          ])}
        </div>
        {format === "print" && <div className="ficha-field"><span>{t.paper}</span>
          {radios(t.paper, paper, setPaper, [["a4", t.a4], ["letter", t.letter]])}</div>}
        <div className="ficha-split">
          <div className="ficha-preview" style={{ width: w * scale, height: h * scale }}>
            <div style={{ transform: `scale(${scale})` }}>
              <CardFace c={c} format={format} paper={paper} node={(el) => { shown.current = el; }} />
            </div>
          </div>
          <div className="ficha-options">
            <div className="ficha-field"><span>{t.language}</span>
              {radios(t.language, lang, setLang, [["es", "ES"], ["en", "EN"]], "langs")}</div>
            <div className="ficha-field"><span>{t.carries}</span>
              <span className="ficha-check locked">{t.locked}</span>
            </div>
            {format !== "print" && <span className="num faint">PNG · {w} × {h}</span>}
          </div>
        </div>
        <div className="ficha-field">
          <span className="ficha-alt-head"><span>{t.altLabel}</span>
            <span><span className="num faint">{alt.length}/{ALT_MAX}</span>
              <button type="button" onClick={() => navigator.clipboard?.writeText(alt)} className="ficha-copy">{t.copy}</button></span></span>
          <div role="note" aria-label={t.altLabel} lang={lang} className="ficha-alt">{alt}</div>
        </div>
      </div>
      <div className="ficha-actions">
        {canShare && <button type="button" onClick={share} className="ficha-btn hi">{t.share}</button>}
        {format === "print"
          ? <>{<style>{`@page { size: ${paper === "a4" ? "A4" : "letter"}; margin: 0; }`}</style>}
              <button type="button" onClick={print} className="ficha-btn primary">{t.print}</button></>
          : <button type="button" onClick={download} className="ficha-btn primary">{t.png}</button>}
      </div>
    </div>
    {printing && createPortal(<div className="print-root"><CardFace c={c} format="print" paper={paper} /></div>, document.body)}
  </>);
}
