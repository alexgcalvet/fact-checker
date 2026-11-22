// S12: the home page (/es/, /en/). Its top follows the owner's board A7 (2026-11-22): the title, one line whose
// «método público» leads to «Cómo funciona», and the newest video as one card (thumbnail, title, source and date, how
// many lines were reviewed and marked, a strip of one tick per line, the button). Then the plain section line and three
// sections with a title and at most one link: checked claims, the most disputed videos and the route of the method
// (How.tsx's, without Aprobar). No severity, no ranking.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { kindOf, type Flag, type Kind } from "./marks";
import { Footer } from "./Footer";
import { Route } from "./How";
import { tip } from "./Tip";
import { TEXTS, type Lang, type Texts } from "./texts";
import { day, density, Density, href, List, newest, served, thumb, type Listed } from "./List";
import { ticks } from "./strip";
import { clock, Keel, MarkIcon, READING_PHONE, short, useMedia, type Summary } from "./Viewer";

const FACT_KINDS: Kind[] = ["falso", "enganoso"];
const SURE = 0.6; // the confidence a checked claim needs
const NEWEST = 5; // the videos whose flags the page reads
const FACTS = 3;
const HOT = 4;

interface Fact { v: Listed; f: Flag }

/** The flags of the newest videos, by video id; null while they load. A video whose flags fail has none. */
function useNewestFlags(videos: Listed[] | null, lang: Lang) {
  const [flags, setFlags] = useState<Map<string, Flag[]> | null>(null);
  useEffect(() => {
    if (!videos) return;
    Promise.all(videos.map(async (v): Promise<[string, Flag[]]> => {
      try {
        const res = await fetch(`/api/videos/${encodeURIComponent(v.video_id)}/flags?lang=${served(v, lang)}`);
        return [v.video_id, res.ok ? (await res.json()).flags as Flag[] : []];
      } catch {
        return [v.video_id, []];
      }
    })).then((answers) => setFlags(new Map(answers)));
  }, [videos, lang]);
  return flags;
}

/** Falso and Engañoso claims of enough confidence that the judge kept: the surest first (then the newest video and the
 * earliest second), one per speaker. */
function factsOf(videos: Listed[], flags: Map<string, Flag[]>): Fact[] {
  const all = videos.flatMap((v, rank) => (flags.get(v.video_id) ?? [])
    .filter((f) => f.judge?.verdict !== "drop" && f.confidence >= SURE && FACT_KINDS.includes(kindOf(f)))
    .map((f) => ({ v, f, rank })));
  all.sort((a, b) => b.f.confidence - a.f.confidence || a.rank - b.rank || a.f.t - b.f.t);
  const facts: Fact[] = [];
  for (const { v, f } of all) {
    if (facts.length < FACTS && !facts.some((x) => x.f.speaker === f.speaker)) facts.push({ v, f });
  }
  return facts;
}

/** A section: its title and at most one link, which reads "Todos" on a phone (`phone`). */
function Section({ title, link, label, children, phone, t }: {
  title: string; link: string; label: string; children: ReactNode; phone: boolean; t: Texts;
}) {
  return (
    <section className="home-sec">
      <div className="home-head">
        <h2>{title}</h2>
        <a href={link} className="home-more">{phone ? t.all : label} <span aria-hidden="true">→</span></a>
      </div>
      {children}
    </section>
  );
}

/** The checked lines of the newest video that came out with no mark, from its guests' summary; null while it loads or
 * when the analysis has none. */
function useClean(v: Listed | undefined, lang: Lang) {
  const [clean, setClean] = useState<number | null>(null);
  useEffect(() => {
    if (!v) return;
    fetch(`/api/videos/${encodeURIComponent(v.video_id)}?lang=${served(v, lang)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((meta: { summary: Record<string, Summary> | null } | null) => {
        const guests = meta?.summary ? Object.values(meta.summary) : [];
        setClean(guests.length ? guests.reduce((n, g) => n + g.verdicts.correct, 0) : null);
      }, () => setClean(null));
  }, [v, lang]);
  return clean;
}

/** The newest video as one card (board A7): the title's link covers the whole card, and the button leads to the same
 * place. The stat and the strip count the lines with a mark and the checked lines with none. */
function Lead({ v, t, lang, flags, clean }: { v: Listed; t: Texts; lang: Lang; flags?: Flag[]; clean: number | null }) {
  const h = t.homePage;
  const target = href(lang, v.video_id);
  const marked = flags?.filter((f) => f.judge?.verdict !== "drop" && kindOf(f) !== "contexto").map((f) => f.t);
  const lines = marked && clean !== null ? marked.length + clean : null;
  const row = marked && lines ? ticks(lines, marked, v.duration || Math.max(...marked) + 1) : null;
  return (
    <article className="home-lead">
      <div className="home-thumb">
        <img src={thumb(v.video_id, "hq")} alt="" />
        {v.duration > 0 && <span className="badge num">{clock(v.duration)}</span>}
        <span aria-hidden="true" className="lead-play" />
      </div>
      <div className="home-lead-text">
        <div className="lead-top">
          <h2><a href={target} className="lead-link">{v.title}</a></h2>
          <span className="home-meta">{[v.channel, v.published_at && day(lang, v.published_at)].filter(Boolean).join(" · ")}</span>
          {marked && <p className="lead-stat">
            {lines !== null && <><span className="num">{lines}</span> {h.reviewed} <span aria-hidden="true">·</span> </>}
            <span aria-hidden="true" className="lead-tick" /><span className="num">{marked.length}</span> {h.marked}
          </p>}
        </div>
        <div className="lead-bottom">
          {row && <div aria-hidden="true" className="lead-strip">
            {row.map((on, i) => <span key={i} className={on ? "on" : undefined} style={{ left: `calc(${((i + .5) * 100) / row.length}% - .5px)` }} />)}
          </div>}
          <a href={target} className="bone-button">{t.list.watch}</a>
        </div>
      </div>
    </article>
  );
}

function FactCard({ v, f, t, lang }: Fact & { t: Texts; lang: Lang }) {
  const h = t.homePage;
  const kind = kindOf(f);
  const lines = [v.title, f.sources[0] && h.source(f.sources[0].publisher), h.confidence(Math.round(f.confidence * 100)), h.open];
  return (
    <a href={`${href(lang, v.video_id)}?t=${Math.floor(f.t)}`} {...tip(lines.filter(Boolean).join("\n\n"))} className="fact">
      <span className="fact-mark"><MarkIcon mark={kind} /><span style={{ color: `var(--st-${kind}-text)` }} className="fact-kind">{t.word[kind]}</span></span>
      <blockquote>«{f.quote}»</blockquote>
      <span className="fact-foot"><span className="fact-who">{short(f.speaker)}</span><span className="fact-time num">{clock(f.t)}</span></span>
    </a>
  );
}


/** The home page; `videos` is null while the list loads. With no approved video it is the list's empty state. */
export function Home({ lang, videos }: { lang: Lang; videos: Listed[] | null }) {
  const t = TEXTS[lang];
  const h = t.homePage;
  const phone = useMedia(READING_PHONE);
  const sorted = useMemo(() => videos && [...videos].sort(newest), [videos]);
  const newestFive = useMemo(() => sorted?.slice(0, NEWEST) ?? null, [sorted]);
  const flags = useNewestFlags(newestFive, lang);
  const clean = useClean(sorted?.[0], lang);
  if (videos && !videos.length) return <List lang={lang} videos={[]} />;

  const all = `/${lang}/videos`;
  const lead = sorted?.[0];
  const facts = flags && newestFive && factsOf(newestFive, flags);
  const hot = videos && videos.filter((v) => density(v) !== null)
    .sort((a, b) => density(b)! - density(a)! || newest(a, b)).slice(0, HOT);

  return (<>
    <main aria-busy={!videos} className="home">
      <section className="home-hero">
        <h1><span>{h.title[0]}</span> <span>{h.title[1]}</span></h1>
        <p className="home-lede">{h.lede[0]}<a href={`/${lang}/${t.list.howPath}`}>{h.lede[1]}</a>{h.lede[2]}</p>
      </section>
      {lead
        ? <Lead v={lead} t={t} lang={lang} flags={flags?.get(lead.video_id)} clean={clean} />
        : <div className="home-lead"><span className="block home-thumb" /><span className="home-lead-text"><span className="block" style={{ width: 120 }} />
            <span className="block tall" style={{ width: "80%" }} /><span className="block" style={{ width: "40%" }} /></span></div>}
      <Keel />

      {(!facts || facts.length > 0) && (
        <Section title={h.facts} link={all} label={h.allVideos} phone={phone} t={t}>
          <div className="facts">
            {facts
              ? facts.map((x) => <FactCard key={`${x.v.video_id}-${x.f.id}`} {...x} t={t} lang={lang} />)
              : [1, 2, 3].map((i) => <span key={i} className="block fact-block" />)}
          </div>
        </Section>
      )}
      {(!hot || hot.length > 0) && (
        <Section title={h.hot} link={all} label={h.seeVideos(videos?.length ?? 0)} phone={phone} t={t}>
          <ol className="hot">
            {hot
              ? hot.map((v) => (
                <li key={v.video_id}>
                  <a href={href(lang, v.video_id)}>
                    <span className="hot-thumb"><img src={thumb(v.video_id, "mq")} alt="" loading="lazy" />
                      {v.duration > 0 && <span className="badge num">{clock(v.duration)}</span>}</span>
                    <span className="hot-title">{v.title}</span>
                    <Density d={density(v)!} t={t} lang={lang} long={!phone} focus={false} />
                  </a>
                </li>
              ))
              : [1, 2, 3, 4].map((i) => <li key={i}><span className="block hot-thumb" /></li>)}
          </ol>
        </Section>
      )}
      <Section title={h.how} link={`/${lang}/${t.list.howPath}`} label={t.list.how} phone={false} t={t}>
        <Route t={t} feedback={`/${lang}/${t.list.howPath}#feedback`} approve={false} />
      </Section>
    </main>
    <Footer lang={lang} />
  </>);
}
