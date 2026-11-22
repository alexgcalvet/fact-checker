// A guest's profile (spec S5), as the owner approved it on the canvas page s5-perfil: the name on night over the line,
// six figures measured per 10 minutes of the guest's own speech and compared only with "el debate" (the guests
// together), who speaks when with the guest's avisos under their lane, and the avisos by kind. The cover is the video's
// thumbnail (her half in a debate, as on the 4:5 card), plan C when it cannot load. The topic and the question of a
// flag are parked (RFC Open question 3): the canvas fallbacks stand in for them.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CardSheet } from "./Card";
import { half, useThumb } from "./faces";
import { useFeedback } from "./Feedback";
import { allSpoken, debateFigures, guestFigures, level, LIT, per10, r1, sum, useNumbers } from "./figures";
import { AVISOS, kindOf, markFor, type Flag, type Kind } from "./marks";
import { Footer } from "./Footer";
import { lane, stop, tip } from "./Tip";
import { TEXTS, type Lang, type Texts } from "./texts";
import { Keel, clock, comparePath, MarkIcon, profilePath, READING_PHONE, role, Row, short, slug, State, useMedia, type Meta, type Summary } from "./Viewer";

const TIPOS: Kind[] = [...AVISOS, "contexto"];
const NEAR = 1 / 80; // marks closer than this share of the video (about 12 px on the laptop lane) join one cluster
const NEAR_STRIP = 1 / 13; // the same 12 px on a type's 152 px strip
const SEVERITY = ["serious", "moderate", "minor"];
// At equal severity the gravest kind first (canvas §5).
const GRAVE: Kind[] = ["falso", "enganoso", "retorica", "evasiva", "puntualizacion"];

const severity = (f: Flag) => {
  const i = SEVERITY.indexOf(f.judge?.severity ?? "");
  return i < 0 ? SEVERITY.length : i;
};
const graver = (a: Flag, b: Flag) => severity(a) - severity(b) || GRAVE.indexOf(kindOf(a)) - GRAVE.indexOf(kindOf(b)) || a.t - b.t;
/** The list's filter, from `?tipo=` and, under Retórica only, `&recurso=<rule id>`. */
type Filter = { tipo: Kind | null; recurso: string | null };
const filterOf = (search: string): Filter => {
  const q = new URLSearchParams(search);
  const tipo = q.get("tipo") as Kind;
  if (!TIPOS.includes(tipo)) return { tipo: null, recurso: null };
  return { tipo, recurso: tipo === "retorica" ? q.get("recurso") : null };
};

/** The figure against the debate: arrow, sign and the delta pair's colour; "= igual" when the shown values match. */
export function Delta({ value, debate, lower, unit, t, show }: { value: number; debate: number; lower: boolean; unit: string; t: Texts; show: (x: number) => string }) {
  if (show(value) === show(debate)) return <span className="delta flat">{t.profile.same}</span>;
  const up = value > debate;
  return (
    <span className={`delta ${up !== lower ? "better" : "worse"}`}>
      {up ? "▲ +" : "▼ −"}{show(Math.abs(value - debate))}{unit}
    </span>
  );
}

function Tile({ label, value, sub, foot }: { label: string; value: ReactNode; sub?: ReactNode; foot?: ReactNode }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
      {sub && <span className="tile-sub">{sub}</span>}
      {foot && <span className="tile-foot">{foot}</span>}
    </div>
  );
}

/** The 3-tick meter of a level, in the delta pair's colours, and its word. */
export function Level({ rate, t }: { rate: number; t: Texts }) {
  const lvl = level(rate);
  return (
    <span className={`density l-${lvl}`}>
      <span aria-hidden="true" className="meter">{[1, 2, 3].map((i) => <span key={i} className={i <= LIT[lvl] ? "lit" : ""} />)}</span>
      {t.profile.levels[lvl]}
    </span>
  );
}

/** The profile of the guest whose slug is `guest`; the guest list when no guest has it; a note when the video has no
 * summary yet. */
export function Profile({ lang, meta, flags, guest }: { lang: Lang; meta: Meta; flags: Flag[]; guest: string }) {
  const t = TEXTS[lang];
  const p = t.profile;
  const viewer = `/${lang}/v/${encodeURIComponent(meta.video_id)}`;
  const name = meta.guests.find((g) => slug(g) === guest);
  const [filter, setFilter] = useState(() => filterOf(location.search));
  useEffect(() => {
    const back = () => setFilter(filterOf(location.search));
    addEventListener("popstate", back);
    return () => removeEventListener("popstate", back);
  }, []);

  if (!name) {
    return (
      <State lang={lang}>
        <p className="none">{p.noProfile}</p>
        <p className="dim">{p.noProfileWhy}</p>
        <ul className="guests">
          {meta.guests.map((g) => <li key={g}><a href={profilePath(lang, meta.video_id, g)}>{short(g)}</a></li>)}
        </ul>
        <a href={viewer} className="plain">{p.back}</a>
      </State>
    );
  }
  const card = meta.summary?.[name];
  if (!card) {
    return (
      <State lang={lang}>
        <span className="dim">{role(name) ?? p.guest} · {short(name)}</span>
        <p className="none">{p.missing}</p>
        <p className="dim">{p.missingWhy}</p>
        <a href={viewer} className="plain">{p.watch}</a>
      </State>
    );
  }
  return <GuestProfile lang={lang} t={t} meta={meta} flags={flags} name={name} card={card} filter={filter} setFilter={setFilter} />;
}

function GuestProfile({ lang, t, meta, flags, name, card, filter, setFilter }: {
  lang: Lang; t: Texts; meta: Meta; flags: Flag[]; name: string; card: Summary; filter: Filter; setFilter: (f: Filter) => void;
}) {
  const { tipo, recurso } = filter;
  const p = t.profile;
  const n = useNumbers(lang);
  const viewer = `/${lang}/v/${encodeURIComponent(meta.video_id)}`;
  const at = (s: number) => `${viewer}?t=${Math.floor(s)}`;
  const guests = meta.guests;
  const { me, speech, base, mine, avisos, ofKind, rate, share, fewData, graves, correct, eluded, eludedPct } =
    guestFigures(meta, flags, name, card);
  // "El debate": the guests together, by their own speaking time; never one other person, never an interview.
  const pool = speech ? debateFigures(meta, flags) : null;
  const pooled = pool !== null;
  const spoken = allSpoken(meta);
  const say = useFeedback(meta.video_id, meta.prompts, t);
  const [open, setOpen] = useState<string | null>(null);
  const [export_, setExport] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const phone = useMedia(READING_PHONE);

  const notes = mine.length - avisos.length;
  const kindRate = (k: Kind) => n.one(r1(per10(ofKind(k).length, base)));
  const poolRate = pool?.rate ?? null;
  const myTurns = (meta.turns ?? []).filter((x) => x.person === name);
  const longest = myTurns.reduce<(typeof myTurns)[number] | null>((a, x) => (!a || x.end - x.start > a.end - a.start ? x : a), null);

  // Her two gravest avisos: the summary's, else by severity, then Falso, Engañoso, Retórica.
  const byId = new Map(avisos.map((f) => [f.id, f]));
  const listed = card.gravest.map((id) => byId.get(id)).filter((f): f is Flag => !!f);
  const gravest = (listed.length ? listed : [...avisos].sort(graver)).slice(0, 2);
  const rest = avisos.filter((f) => !gravest.includes(f));

  const pick = (k: Kind | null, device: string | null = null) => () => {
    const q = new URLSearchParams();
    if (k) q.set("tipo", k);
    if (device) q.set("recurso", device);
    history.pushState(null, "", q.size ? `${location.pathname}?${q}` : location.pathname);
    setFilter({ tipo: k, recurso: device });
  };
  const shown = (f: Flag) => (!tipo || kindOf(f) === tipo) && (!recurso || f.label === recurso);
  // A figure's delta against the debate, and the debate's own figure; `pct` for a percentage, whose delta is in points.
  const debateFoot = (value: number, debate: number | null, lower: boolean, show: (x: number) => string, pct = false) =>
    debate !== null && <><Delta value={value} debate={debate} lower={lower} unit={pct ? ` ${p.pt}` : ""} t={t} show={show} />
      <span>{p.debate} {show(debate)}{pct && " %"}</span></>;

  const date = meta.published_at && new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${meta.published_at}T00:00:00Z`));

  // Marks on the video's time axis: one per cluster (`near`, a share of the video), the gravest kind on top, 1 and 2
  // over her two gravest; each mark links to its second.
  const pct = (s: number) => `${(s / meta.duration) * 100}%`;
  const marks = (these: Flag[], near: number) => {
    const clusters: Flag[][] = [];
    for (const f of these) {
      const last = clusters.at(-1);
      if (last && f.t - last[0].t < near * meta.duration) last.push(f);
      else clusters.push([f]);
    }
    return clusters.map((c, i) => {
      const lead = [...c].sort(graver)[0];
      const rank = gravest.findIndex((g) => c.includes(g));
      const k = kindOf(lead);
      return (
        <a key={lead.id} href={at(lead.t)} style={{ left: pct(lead.t) }}
          {...tip(`${clock(lead.t)} · ${t.word[k]}${lead.judge?.severity ? ` · ${p.severity[lead.judge.severity]}` : ""} · «${lead.quote}» · ${p.tip}`)}
          {...stop(i === 0)} className={`lane-pin${c.some(shown) ? "" : " off"}`}>
          {rank >= 0 && <span className="pin-rank num">{rank + 1}</span>}
          <span aria-hidden="true" className={`lane-mark m-${k}`} />
          {c.length > 1 && <span className="plus num">+{c.length - 1}</span>}
          <span className="sr">{clock(lead.t)} · {t.word[k]}</span>
        </a>
      );
    });
  };
  const avisosLane = <div {...lane(t.markLane)} className="voice-track marks-track">{marks(avisos, NEAR)}</div>;

  // The filter bar: every kind with its count; a kind she has none of reads "–" and cannot be tapped.
  const chip = (k: Kind) => {
    const count = ofKind(k).length;
    return (
      <li key={k}>
        <button type="button" aria-pressed={tipo === k} disabled={!count} onClick={pick(k)}>
          <MarkIcon mark={k} dim={!count} />{t.word[k]} <span className="num">{count || "–"}</span>
        </button>
      </li>
    );
  };

  // The type panel (board S5Profile, "Sus avisos por tipo"): a row per kind with its count, rate and strip; a row is
  // the same filter as its chip. A kind she has none of reads "–" and "ninguno" and cannot be pressed.
  const typeRow = (k: Kind) => {
    const these = ofKind(k);
    return (
      <div key={k} className={`type-row${tipo === k ? " on" : ""}`}>
        <button type="button" aria-pressed={tipo === k} disabled={!these.length} onClick={pick(k)} className="type-pick">
          <MarkIcon mark={k} dim={!these.length} />
          <span style={{ color: these.length ? `var(--st-${markFor(k)}-text)` : undefined }} className="type-word">{t.word[k]}</span>
          <span className="num type-count">{these.length || "–"}</span>
          <span className="num type-rate">{these.length ? `${kindRate(k)}/10′` : ""}</span>
        </button>
        {these.length ? <div {...lane(t.markLane)} className="type-strip">{marks(these, NEAR_STRIP)}</div> : <span className="type-none">{p.noneOf}</span>}
      </div>
    );
  };
  const mixed = AVISOS.filter((k) => ofKind(k).length);
  const devices = card.devices.length > 0 && (
    <section aria-label={p.repeats} className="types-block">
      <span className="block-title">{p.repeats} <span className="faint">{p.repeatsWhy}</span></span>
      <ul className="device-lines">
        {card.devices.map((d) => (
          <li key={d.label}>
            <button type="button" aria-pressed={recurso === d.label} disabled={!mine.some((f) => f.label === d.label)}
              onClick={pick("retorica", recurso === d.label ? null : d.label)} className="device-line">
              <span className="device-name">{t.label[d.label] ?? d.label}</span>{" "}
              <span aria-hidden="true" className="device-marks">
                {[...Array(Math.min(d.count, 4))].map((_, i) => <MarkIcon key={i} mark="retorica" size={10} />)}</span>{" "}
              <span className="num">×{d.count}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
  // One cell per question: dodged the Evasiva mark, partly answered a quarter fill, answered a ring.
  const questions = card.asked > 0 && (
    <button type="button" aria-pressed={tipo === "evasiva"} disabled={!ofKind("evasiva").length} onClick={pick("evasiva")} className="types-block asked">
      <span className="block-title">{p.asked} <span className="num">{card.asked}</span></span>
      <span aria-hidden="true" className="questions">
        {[...Array(card.asked)].map((_, i) => i < card.dodged
          ? <MarkIcon key={i} mark="evasiva" />
          : <span key={i} className={`q ${i < eluded ? "partial" : "answered"}`} />)}
      </span>
      <span className="small dim">{p.askedHow(card.dodged, card.partial, card.asked - eluded)}</span>
    </button>
  );
  const types = (
    <section aria-label={p.byKind} className={`profile-types${tipo === "evasiva" ? " ask-first" : ""}`}>
      <div className="types-head">
        <h2>{p.byKind}</h2>
        <span className="small faint">{p.typesLead}</span>
      </div>
      <div className="type-rows">
        <div aria-hidden="true" className="type-row heads">
          <span className="type-pick"><span /><span>{p.typeHead}</span><span /><span className="type-rate">{p.per10Head}</span></span>
          <span className="type-axis num"><span>{clock(0)}</span><span>{clock(meta.duration)}</span></span>
        </div>
        <div className={`type-row all${tipo ? "" : " on"}`}>
          <button type="button" aria-pressed={!tipo} onClick={pick(null)} className="type-pick">
            <span /><span className="type-word">{p.allAvisos}</span>
            <span className="num type-count">{avisos.length}</span>
            <span className="num type-rate">{n.one(rate)}/10′</span>
          </button>
          <span role="img" aria-label={mixed.map((k) => `${ofKind(k).length} ${t.word[k]}`).join(", ")} className="type-mix mix">
            {mixed.map((k) => <span key={k} className={`seg m-${k}`} style={{ flexGrow: ofKind(k).length }} />)}
          </span>
        </div>
        {AVISOS.map(typeRow)}
        <span className="type-apart">{p.outside}</span>
        {typeRow("contexto")}
      </div>
      {devices}
      {questions}
    </section>
  );

  // A flag as an open row of the viewer's panel: its time leads to the video, a tap on the quote opens its reason.
  const rows = (these: Flag[]) => (
    <ol className={`rows${meta.duration >= 3600 ? " long" : ""}`}>
      {these.map((f) => (
        <li key={f.id}>
          <Row f={f} t={t} lang={meta.lang} say={say} phone={phone} open={open === f.id}
            go={() => setOpen(open === f.id ? null : f.id)} more={() => setOpen(f.id)}
            time={<a href={at(f.t)} aria-label={p.goTo(clock(f.t))} className="time num">{clock(f.t)}</a>} />
        </li>
      ))}
    </ol>
  );
  // The flags of one kind (and device): its rate against the debate, then its flags.
  const kindList = (k: Kind) => (
    <section aria-label={t.word[k]} className="list-part">
      <div className="list-head">
        <span className="block-title">{t.word[k]}{recurso && <span className="faint"> · {t.label[recurso] ?? recurso}</span>}</span>
        <span className="small dim">{p.kindLead(kindRate(k), pool && k !== "contexto"
          ? n.one(pool.kindRate(k)) : null, speech)}</span>
      </div>
      {rows(ofKind(k).filter(shown))}
    </section>
  );

  const figures = (
    <section aria-label={p.figures} className="figures">
      <div className="tiles">
        {share !== null
          ? <Tile label={p.share} value={<span className="num">{n.one(share)} %</span>} sub={p.spokenOf(clock(me.spoken_s), clock(spoken))}
              foot={p.turnsMean(me.turns, clock(Math.round(me.spoken_s / (me.turns || 1))))} />
          : <Tile label={p.share} value={<span className="none-value">{p.noData}</span>} />}
        <Tile label={speech ? p.rate : p.rateVideo} value={<span className="num">{n.one(rate)}</span>}
          sub={<>{t.list.avisos(avisos.length)} · {speech ? <Level rate={rate} t={t} /> : <span {...tip(p.videoNote, true)}>{p.noLevel}</span>}
            {fewData && <> · {p.fewData}</>}</>}
          foot={debateFoot(rate, poolRate, true, n.one)} />
        <Tile label={p.correct} value={<span className="num">{correct === null ? "–" : `${correct} %`}</span>}
          sub={p.checkedOf(card.verdicts.correct, card.checked)}
          foot={correct !== null && debateFoot(correct, pool?.correct ?? null, false, n.whole, true)} />
        <Tile label={speech ? p.graves : p.gravesVideo} value={<span className="num">{n.one(graves)}</span>}
          sub={p.severities(card.severity.serious, card.severity.moderate, card.severity.minor)}
          foot={debateFoot(graves, pool?.graves ?? null, true, n.one)} />
        <Tile label={p.dodged} value={<><span className="num">{card.asked ? eluded : "–"}</span> {card.asked > 0 && <span className="of">{p.of(card.asked)}</span>}</>}
          sub={card.asked ? p.dodgedHow(card.dodged, card.partial) : p.noQuestions}
          foot={eludedPct !== null && debateFoot(eludedPct, pool?.eluded ?? null, true, n.whole, true)} />
        {speech
          ? <Tile label={p.longest} value={<span className="num">{clock(me.longest_s)}</span>}
              sub={longest && p.fromTo(clock(longest.start), clock(longest.end))}
              foot={longest && <a href={at(longest.start)}>{p.seeIt}</a>} />
          : <Tile label={p.longest} value={<span className="none-value">{p.noData}</span>} />}
      </div>
    </section>
  );

  return (<>
    <main className="profile">
      <div className="profile-top">
        <a href={viewer} className="plain">{p.back}</a>
        {guests.length > 1 && (
          <nav aria-label={p.guests} className="glass guest-pill">
            {guests.map((g) => <a key={g} href={profilePath(lang, meta.video_id, g)} aria-current={g === name ? "page" : undefined}>{short(g)}</a>)}
            <a href={comparePath(lang, meta.video_id)}>{t.compare.link}</a>
          </nav>
        )}
      </div>

      {/* The hero band: the cover and her header text share one floor, and the line runs across both. */}
      <Cover meta={meta} name={name} />
      <div className="profile-head">
        <div className="hero-id">
          <span className="kicker">{role(name) ?? p.guest}</span>
          <div className="hero-name">
            <h1>{short(name)}</h1>
            <button ref={opener} type="button" aria-haspopup="dialog" onClick={() => setExport(true)} className="ficha-btn primary">{t.card.open}</button>
          </div>
          <span className="hero-source">{p.source} <a href={viewer}>{meta.title}</a>
            {meta.channel && <> · {meta.channel}</>}{date && <> · {date}</>}
            {meta.duration > 0 && <> · <span className="num">{clock(meta.duration)}</span></>}</span>
        </div>
        <div className="hero-lead">
          <p className="sentence-line">
            {speech && share !== null
              ? p.sentence(`${n.one(share)} %`, me.turns, n.one(rate), poolRate === null ? null : n.one(poolRate))
              : p.sentenceVideo(avisos.length, clock(meta.duration))}
          </p>
          <div className="hero-counts">
            <span className="tally">{p.total(avisos.length, notes)}</span>
          </div>
        </div>
      </div>
      <Keel />

      {/* Under the hero: the disclosure on the left, her figures on the right. */}
      <div className="profile-side">
        <div className="under">
          <p className="ai">{t.ai}</p>
          {speech && <p className="faint small">{pooled ? `${p.debateNote(guests.length)} ` : ""}{p.provisional}</p>}
        </div>
      </div>
      <div className="profile-main">{figures}</div>

      <Voices lang={lang} t={t} meta={meta} me={name} lead={spoken
        ? p.whoWhy(short(name), clock(spoken), clock(meta.duration))
        : p.whoNone(short(name))}>
        <div className="voice-row avisos-row">
          <span className="voice-name faint">{p.hers}</span>
          {avisosLane}
          <span className="cell wide">{t.list.avisos(avisos.length)} · <span className="num">{n.one(rate)}</span> {speech ? p.perTenSpeech : t.list.perTen}</span>
        </div>
      </Voices>

      {/* Her avisos: the type panel on the left; on the right the list, under the filter bar that sticks over it. */}
      {types}
      <div className="profile-list">
        <nav aria-label={p.byKind} className="glass chips filter kind-bar">
          <ul className="marks">
            <li>
              <button type="button" aria-pressed={!tipo} onClick={pick(null)}>{p.all} <span className="num">{avisos.length}</span></button>
            </li>
            {AVISOS.map(chip)}
            <li aria-hidden="true" className="apart" />
            {chip("contexto")}
          </ul>
        </nav>
        <div className="kind-list">
          {tipo ? kindList(tipo) : <>
            <section aria-label={p.gravestTitle} className="list-part">
              <div className="list-head"><span {...tip(p.gravestWhy, true)} className="block-title">{p.gravestTitle}</span></div>
              {rows(gravest)}
            </section>
            {rest.length > 0 && (
              <section aria-label={p.rest} className="list-part">
                <div className="list-head"><span {...tip(p.restWhy, true)} className="block-title">{p.rest}</span><span className="num faint">{rest.length}</span></div>
                {rows(rest)}
              </section>
            )}
          </>}
        </div>
      </div>
      {say.question}
      {export_ && <CardSheet lang={lang} meta={meta} flags={flags} name={name} card={card} gravest={gravest} close={() => { setExport(false); opener.current?.focus(); }} />}
    </main>
    <Footer lang={lang} prompts={meta.prompts} />
  </>);
}

/** Who speaks when: every voice's lane on the video's time axis and its turns, the host's included. `me` leads and is
 * highlighted, with `children` (their avisos) under their lane; with no `me`, nobody is highlighted. */
export function Voices({ lang, t, meta, me, lead, children }: {
  lang: Lang; t: Texts; meta: Meta; me?: string; lead: string; children?: ReactNode;
}) {
  const p = t.profile;
  const n = useNumbers(lang);
  const people = meta.people ?? {};
  const guests = meta.guests;
  const spoken = allSpoken(meta);
  const pct = (s: number) => `${(s / meta.duration) * 100}%`;
  const order = [...(me ? [me] : []), ...guests.filter((g) => g !== me), ...Object.keys(people).filter((x) => !guests.includes(x))];
  const voiced = order.filter((x) => people[x]?.spoken_s);
  const voiceRow = (who: string) => {
    const x = people[who];
    const hosted = !guests.includes(who);
    return (
      <div key={who} className={`voice-row${who === me ? " me" : hosted ? " host" : ""}`}>
        <span className="voice-name">{short(who)}{hosted && <span className="faint"> · {p.host[meta.type] ?? p.host.debate}</span>}</span>
        <div className="voice-track">
          {(meta.turns ?? []).filter((turn) => turn.person === who).map((turn) => (
            <span key={turn.start} className="turn" style={{ left: pct(turn.start), width: pct(turn.end - turn.start) }} />
          ))}
        </div>
        <span className="cell share-bar"><span style={{ width: `${(100 * x.spoken_s) / spoken}%` }} /></span>
        <span className="cell num">{n.one(r1((100 * x.spoken_s) / spoken))} %</span>
        <span className="cell num">{clock(x.spoken_s)}</span>
        <span className="cell num extra">{x.turns}</span>
        <span className="cell num extra">{x.turns ? clock(Math.round(x.spoken_s / x.turns)) : "–"}</span>
        <span className="cell num extra">{clock(x.longest_s)}</span>
      </div>
    );
  };
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * meta.duration));
  return (
    <section aria-label={p.who} className="voices">
      <h2 {...tip(lead, true)}>{p.who}</h2>
      <div className="voice-grid">
        {voiced.length > 0 && (
          <div className="voice-row heads">
            <span /><span />
            <span className="cell">{p.heads.speaks}</span><span className="cell">{p.heads.share}</span><span className="cell">{p.heads.time}</span>
            <span className="cell extra">{p.heads.turns}</span><span className="cell extra">{p.heads.mean}</span><span className="cell extra">{p.heads.longest}</span>
          </div>
        )}
        {me && voiced.includes(me) && voiceRow(me)}
        {children}
        {voiced.filter((x) => x !== me).map(voiceRow)}
        {voiced.length > 0 && (
          <div className="voice-row">
            <span {...tip(p.silenceWhy)} className="voice-name faint">{p.silence}</span>
            <div className="voice-track" />
            <span className="cell share-bar" /><span className="cell num">–</span>
            <span className="cell num">{clock(Math.max(0, meta.duration - spoken))}</span>
          </div>
        )}
        <div className="voice-row axis">
          <span />
          <div className="axis-ticks num faint">{ticks.map((s) => <span key={s} style={{ left: pct(s) }}>{clock(s)}</span>)}</div>
        </div>
      </div>
    </section>
  );
}

/** The cover: her half of the thumbnail in a debate (the left half mirrored, as on the 4:5 plate), the whole one in an
 * interview, dimmed like the list's thumbnails at rest, under the plate's fades; plan C (her name on night) when it
 * cannot load. */
function Cover({ meta, name }: { meta: Meta; name: string }) {
  const { src, onError, onLoad } = useThumb(meta.video_id);
  const h = half(meta.guests, name, meta.swap);
  return (
    <div aria-hidden="true" className="cover">
      {src && (
        <div className="cover-art">
          <img src={src} alt="" data-half={h ?? undefined} className={h ? `half ${h}` : undefined} onError={onError} onLoad={onLoad} />
          {h && <div className="cover-fade" />}
          <div className="cover-fade-b" />
        </div>
      )}
      <span>{short(name)}</span>
    </div>
  );
}
