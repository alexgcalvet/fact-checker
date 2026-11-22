// The comparison of a debate's guests (spec S10), as the owner approved it on the canvas board S5Compare: one row per
// figure, each guest measured per 10 minutes of their own speech, every row on its own shared scale, and each figure
// set only against "el debate" (the guests together), never ranked. Two guests face each other on a balance; three or
// more line up in columns. The face thumb is parked (RFC Open question 3): plan C, the name on night, stands in.
import type { ReactNode } from "react";
import { allSpoken, debateFigures, guestFigures, useNumbers } from "./figures";
import { AVISOS, type Flag } from "./marks";
import { Level, Voices } from "./Profile";
import { Footer } from "./Footer";
import { tip } from "./Tip";
import { TEXTS, type Lang } from "./texts";
import { clock, comparePath, profilePath, role, short, State, type Meta, type Summary } from "./Viewer";

type Guest = ReturnType<typeof guestFigures> & { name: string; card: Summary };
/** A figure: its label and help, the debate's own value, and per guest its value and its bar or cells. */
interface Figure {
  label: string;
  why: string;
  debate: string | null;
  value: (g: Guest) => ReactNode;
  bar: (g: Guest, mirrored: boolean) => ReactNode;
}

/** The comparison of the video's guests; their list when there is one guest, or when the figures cannot be set side by side. */
export function Compare({ lang, meta, flags }: { lang: Lang; meta: Meta; flags: Flag[] }) {
  const t = TEXTS[lang];
  const c = t.compare;
  const p = t.profile;
  const n = useNumbers(lang);
  const viewer = `/${lang}/v/${encodeURIComponent(meta.video_id)}`;
  const guests = meta.guests;
  const pool = debateFigures(meta, flags);
  const cards = guests.map((g) => meta.summary?.[g]);

  if (guests.length < 2 || !pool || cards.some((x) => !x)) {
    const [none, why] = guests.length < 2 ? [c.single, c.singleWhy] : !pool ? [c.noSpeech, c.noSpeechWhy] : [c.noSummary, c.noSpeechWhy];
    return (
      <State lang={lang}>
        <p className="none">{none}</p>
        <p className="dim">{why}</p>
        <ul className="guests">
          {guests.map((g) => <li key={g}><a href={profilePath(lang, meta.video_id, g)}>{short(g)}</a></li>)}
        </ul>
        <a href={viewer} className="plain">{p.back}</a>
      </State>
    );
  }

  const all: Guest[] = guests.map((name, i) => ({ name, card: cards[i]!, ...guestFigures(meta, flags, name, cards[i]!) }));
  const two = all.length === 2;
  const max = (f: (g: Guest) => number) => Math.max(...all.map(f));
  const scaled = (value: number, top: number) => `${top ? (100 * value) / top : 0}%`;
  const bar = (value: number, top: number, few: boolean) =>
    <span className={`bar-track${few ? " few" : ""}`}><span className="bar-fill" style={{ width: scaled(value, top) }} /></span>;
  const few = (g: Guest) => g.fewData && <span className="faint"> · <span {...tip(c.fewNote, true)}>{p.fewData}</span></span>;

  const shareTop = max((g) => g.share ?? 0);
  const rateTop = max((g) => g.rate);
  const gravesTop = max((g) => g.graves);
  // Every device of any guest, in the same order for all: by the debate's total, the guests summed.
  const counted = (g: Guest, label: string) => g.card.devices.find((d) => d.label === label)?.count ?? 0;
  const deviceTotal = (label: string) => all.reduce((a, g) => a + counted(g, label), 0);
  const devices = [...new Set(all.flatMap((g) => g.card.devices.map((d) => d.label)))].sort((a, b) => deviceTotal(b) - deviceTotal(a));
  const deviceTop = Math.max(0, ...all.flatMap((g) => g.card.devices.map((d) => d.count)));
  const figures: Figure[] = [
    {
      label: p.share, why: c.shareWhy, debate: null,
      value: (g) => <><span className="cmp-num num">{n.one(g.share ?? 0)} %</span>
        <span className="cmp-sub">{c.spokenTurns(clock(g.me!.spoken_s), g.me!.turns)}</span></>,
      bar: (g) => bar(g.share ?? 0, shareTop, false),
    },
    {
      label: p.rate, why: c.rateWhy, debate: n.one(pool.rate),
      value: (g) => <><span className="cmp-num"><span className="num">{n.one(g.rate)}</span> <Level rate={g.rate} t={t} /></span>
        <span className="cmp-sub">{t.list.avisos(g.avisos.length)}{few(g)}</span></>,
      // The mix bar, its segments drawn like the marks; mirrored on the left of the balance, so Falso meets the spine.
      bar: (g, mirrored) => {
        const kinds = AVISOS.filter((k) => g.ofKind(k).length);
        return (
          <span className={`bar-track${g.fewData ? " few" : ""}`}>
            <span role="img" aria-label={kinds.map((k) => `${g.ofKind(k).length} ${t.word[k]}`).join(", ")} className="mix"
              style={{ width: scaled(g.rate, rateTop) }}>
              {(mirrored ? [...kinds].reverse() : kinds).map((k) => <span key={k} className={`seg m-${k}`} style={{ flexGrow: g.ofKind(k).length }} />)}
            </span>
          </span>
        );
      },
    },
    {
      label: p.correct, why: c.correctWhy, debate: pool.correct === null ? null : `${pool.correct} %`,
      value: (g) => <><span className="cmp-num num">{g.correct === null ? "–" : `${g.correct} %`}</span>
        <span className="cmp-sub">{p.checkedOf(g.card.verdicts.correct, g.card.checked)}</span></>,
      bar: (g) => bar(g.correct ?? 0, 100, false),
    },
    {
      label: p.graves, why: c.gravesWhy, debate: n.one(pool.graves),
      value: (g) => <><span className="cmp-num num">{n.one(g.graves)}</span>
        <span className="cmp-sub">{c.gravesOf(g.card.severity.serious, g.avisos.length)}{few(g)}</span></>,
      bar: (g) => bar(g.graves, gravesTop, g.fewData),
    },
    {
      label: p.dodged, why: c.dodgedWhy, debate: pool.eluded === null ? null : `${pool.eluded} %`,
      value: (g) => <><span className="cmp-num"><span className="num">{g.card.asked ? g.eluded : "–"}</span>
        {g.card.asked > 0 && <span className="of"> {p.of(g.card.asked)}</span>}</span>
        <span className="cmp-sub">{g.card.asked ? p.dodgedHow(g.card.dodged, g.card.partial) : p.noQuestions}</span></>,
      // One cell per question: dodged full, partly answered half, answered empty.
      bar: (g, mirrored) => {
        const qs = [...Array(g.card.asked)].map((_, i) => (i < g.card.dodged ? "dodged" : i < g.eluded ? "partial" : "answered"));
        return <span aria-hidden="true" className="questions">
          {(mirrored ? qs.reverse() : qs).map((q, i) => <span key={i} className={`q ${q}`} />)}</span>;
      },
    },
    {
      // Every device, each with its count and a bar on one scale for all the guests; "–" for one they never use.
      label: p.repeats, why: c.repeatsWhy, debate: null,
      value: (g) => devices.length
        ? <ul className="device-list">{devices.map((label) => {
            const count = counted(g, label);
            return <li key={label} className={`device${count ? "" : " zero"}`}>
              <span className="device-name">{t.label[label] ?? label}</span>{" "}
              <span className="num">{count ? `×${count}` : "–"}</span>
              <span aria-hidden="true" className="device-bar"><span style={{ width: scaled(count, deviceTop) }} /></span>
            </li>;
          })}</ul>
        : <span className="faint">–</span>,
      bar: () => null,
    },
  ];
  const head = (f: Figure) => (
    <span role="rowheader" className="cmp-label">
      <span {...tip(f.why, true)} className="cmp-label-name">{f.label}</span>
      {f.debate !== null && <span className="cmp-debate">{p.debate} <span className="num">{f.debate}</span></span>}
    </span>
  );
  const thumb = (g: Guest) => <span aria-hidden="true" className="cmp-thumb"><span>{short(g.name)}</span></span>;
  // The guest's header: the thumb above the name and role, then the link to their profile.
  const who = (g: Guest) => (
    <span key={g.name} role="columnheader" className="cmp-head">
      {thumb(g)}
      <a href={profilePath(lang, meta.video_id, g.name)} className="who-link">
      <span className="who-id"><span className="who-name">{short(g.name)}</span>{role(g.name) && <span className="who-role">{role(g.name)}</span>}</span>
      <span className="see">{c.seeProfile}</span>
      </a>
    </span>
  );

  const date = meta.published_at && new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${meta.published_at}T00:00:00Z`));
  const names = all.map((g) => short(g.name));

  return (<>
    <main className="compare">
      <div className="compare-top">
        <a href={viewer} className="plain">{p.back}</a>
        <nav aria-label={p.guests} className="glass guest-pill">
          {guests.map((g) => <a key={g} href={profilePath(lang, meta.video_id, g)}>{short(g)}</a>)}
          <a href={comparePath(lang, meta.video_id)} aria-current="page">{c.link}</a>
        </nav>
      </div>

      <header className="compare-head">
        <span className="kicker">{c.kicker(all.length)}</span>
        <h1 {...tip(two ? c.leadTwo(names[0], names[1]) : c.leadMany)}>{two ? c.titleTwo(names[0], names[1]) : c.titleMany(all.length)}</h1>
        <span className="hero-source">{p.source} <a href={viewer}>{meta.title}</a>
          {meta.channel && <> · {meta.channel}</>}{date && <> · {date}</>}
          {meta.duration > 0 && <> · <span className="num">{clock(meta.duration)}</span></>}</span>
        <p className="ai">{t.ai}</p>
      </header>

      <section aria-label={c.figures} className="compare-figures">
        {two
          ? <div role="table" className="balance">
              <div role="row" className="bal-heads">{who(all[0])}{who(all[1])}</div>
              {figures.map((f) => (
                <div key={f.label} role="row" className="bal-row">
                  <span role="cell" className="bal-cell left"><span className="bal-value">{f.value(all[0])}</span>
                    <span className="bal-bar">{f.bar(all[0], true)}</span></span>
                  {head(f)}
                  <span role="cell" className="bal-cell right"><span className="bal-bar">{f.bar(all[1], false)}</span>
                    <span className="bal-value">{f.value(all[1])}</span></span>
                </div>
              ))}
            </div>
          : <div role="region" tabIndex={0} aria-label={c.figures} className={`cmp-frame${all.length > 4 ? " wide" : ""}`}>
              <div role="table" className="cmp-table" style={{ gridTemplateColumns: `var(--cmp-label) repeat(${all.length}, minmax(var(--cmp-col), 1fr))` }}>
                <div role="row" className="cmp-row cmp-heads">
                  <span aria-hidden="true" />
                  {all.map(who)}
                </div>
                {figures.map((f) => (
                  <div key={f.label} role="row" className="cmp-row">
                    {head(f)}
                    {all.map((g) => (
                      <span key={g.name} role="cell" className="cmp-cell">
                        <span className="cmp-who">{short(g.name)}</span>
                        <span className="cmp-value">{f.value(g)}</span>
                        {f.bar(g, false)}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </div>}
        <p className="faint small compare-notes">
          {p.debateNote(all.length)} {p.provisional}
        </p>
      </section>

      <Voices lang={lang} t={t} meta={meta} lead={c.voices(clock(allSpoken(meta)), clock(meta.duration))} />
    </main>
    <Footer lang={lang} prompts={meta.prompts} />
  </>);
}
