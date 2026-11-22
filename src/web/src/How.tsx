// S6: the page "Cómo funciona" (/es/como-funciona, /en/how-it-works), as the canvas page s6-como. Diagrams of the
// method; a hover, a keyboard focus or a tap on a box opens its detail in the solid tooltip: its sentence, then the
// facts (owner, live review: no marker, no kicker, no switch). The instructions are the prompts file of the newest
// approved video, and the reader can comment on a sentence of them or send a general correction.
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { Footer } from "./Footer";
import { usePromptComment, type Sent } from "./Feedback";
import { markFor, type Kind } from "./marks";
import { tip } from "./Tip";
import { TEXTS, type Lang, type Texts } from "./texts";
import { Keel, MarkIcon } from "./Viewer";
import { BigMark } from "./DeFacto";

interface Prompts { version: string; components: { id: string; role: string; text: string; rules: { id: string; text: string }[] }[] }

/** The prompts file that the newest approved video names, or null when it names none. */
async function newestPrompts(lang: Lang): Promise<Prompts | null> {
  try {
    const [newest] = (await (await fetch("/api/videos")).json()).videos as { video_id: string }[];
    if (!newest) return null;
    const meta = await fetch(`/api/videos/${encodeURIComponent(newest.video_id)}?lang=${lang}`);
    const version = meta.ok ? (await meta.json()).prompts as string | null : null;
    if (!version) return null;
    const file = await fetch(`/api/prompts/${encodeURIComponent(version)}`);
    return file.ok ? await file.json() as Prompts : null;
  } catch {
    return null;
  }
}

// A detail is its sentence, then its facts 8 px below (Tip.tsx: a blank line starts a block). Backticks mark code.
const detail = ([lead, ...facts]: string[]) => [lead, facts.join("\n")].filter(Boolean).join("\n\n").replaceAll("`", "");

/** A box with a detail: the whole box opens it on hover, keyboard focus or a tap; with `href` the box is also a link. */
function Box({ lines, className = "", top, href, children }: { lines: string[]; className?: string; top?: number; href?: string; children: ReactNode }) {
  const style = top === undefined ? undefined : { top };
  return href
    ? <a href={href} className={`box ${className}`} style={style} {...tip(detail(lines))}>{children}</a>
    : <div className={`box ${className}`} style={style} {...tip(detail(lines), true)}>{children}</div>;
}

/** The level meter: three ticks, lit to the level, no hue (severity is not a verdict). */
const Meter = ({ lit }: { lit: number }) => (
  <span aria-hidden="true" className="how-meter">{[1, 2, 3].map((i) => <i key={i} className={i <= lit ? "on" : ""} />)}</span>
);

// The tree's fixed drawing (board S6How, 936 × 444): each source's row centre, and the leaves 64 tall every 76 px.
const LEAVES: Kind[] = ["falso", "enganoso", "evasiva", "retorica", "contexto", "puntualizacion"];
const SOURCES = [70, 184, 260, 336, 412];

/** The route of a video and its open loop. The home page omits Aprobar (`approve` false) and links Tú das feedback to
 * the form on this page. */
export function Route({ t, feedback, approve = true }: { t: Texts; feedback: string; approve?: boolean }) {
  const h = t.how;
  const steps = h.steps.filter((s) => approve || s !== h.steps[6]);
  return (
    <div className={`route-wrap${approve ? "" : " no-approve"}`}>
      <ol className="route" aria-label={h.route.label}>
        {steps.map((s, i) => (
          <li key={s.name} className={s === h.steps[6] ? "approve" : s === h.steps[7] ? "publish" : ""}>
            <Box lines={[s.line, ...s.tip]}>
              <span className="num step-n">{String(i + 1).padStart(2, "0")}</span>
              <span className="box-name">{s.name}</span>
              <span className="box-model">{s.model}</span>
            </Box>
          </li>
        ))}
      </ol>
      <span aria-hidden="true" className="bracket" />
      <p className="bracket-note"><span>{h.route.bracket}</span></p>
      <div {...tip(h.loop.noteLine)} className="loop-note"><span className="num">{h.loop.note}</span><span>{h.loop.noteShort}</span></div>
      <ol className="loop" aria-label={h.loop.label}>
        {h.loop.boxes.map((b, i) => (
          <li key={b.name} className={b.planned ? "planned" : ""}>
            {/* "Tú das feedback" leads to the form (owner: commenting must be easy to find). */}
            <Box lines={[b.line, ...b.tip]} href={i === 0 ? feedback : undefined}>
              <span className="num plan-word">{b.planned && h.loop.planned}</span>
              <span className="box-name">{b.name}</span>
            </Box>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** The project's progress in one line of steps, one version each: done, in progress, next. A step's detail opens
 * on hover, keyboard focus or a tap. */
function Roadmap({ t }: { t: Texts }) {
  const r = t.how.roadmap;
  return (
    <section className="how-sec">
      <h2>{r.title}</h2>
      <ol className="roadmap" aria-label={r.label}>
        {r.steps.map((s) => (
          <li key={s.v} className={`rm-${s.state}`} {...tip(detail(s.tip), true)}>
            <span className="rm-state num">{s.v} · {r.states[s.state as keyof typeof r.states]}</span>
            <span className="rm-name">{s.name}</span>
            <span className="rm-line">{s.line}</span>
          </li>
        ))}
      </ol>
      <p className="rm-note small faint">{r.note}</p>
    </section>
  );
}

export function How({ lang }: { lang: Lang }) {
  const t = TEXTS[lang];
  const h = t.how;
  const [prompts, setPrompts] = useState<Prompts | null | undefined>(undefined);
  const say = usePromptComment(prompts?.version, t);

  useEffect(() => { newestPrompts(lang).then(setPrompts); }, [lang]);

  const leafLines = (k: Kind) => {
    const [quote, ...rest] = h.tree.tips[k];
    return [t.legend[k], `${h.example}: ${quote}`, ...rest];
  };
  const sources = [h.tree.fact, h.tree.question, h.tree.device, h.tree.reference, h.tree.judge];

  return (<>
    <main className="how">
      {/* The page name as a kicker over the large DeFacto mark, which turns once, then its line and the lede (design
          panel, 2026-11-22; logo-spec.md §3). */}
      <section className="how-hero">
        <h1>{h.title}</h1>
        <BigMark caps={[96, 56]} />
        <p className="df-line"><span>{h.mark[0]}</span> <span>{h.mark[1]}</span></p>
        <p className="how-lede">{h.lede}</p>
        <a href="#feedback" className="how-to-form">{h.toForm}</a>
      </section>
      <Keel />

      <section className="how-sec how-first">
        <div className="how-head">
          <h2>{h.route.title}</h2>
          <span className="how-legend">
            <span className="key today">{h.loop.today}</span>
            <span className="key plan">{h.loop.planned}</span>
          </span>
        </div>
        <Route t={t} feedback="#feedback" />
      </section>

      <Roadmap t={t} />

      <section className="how-sec">
        <h2>{h.tree.title}</h2>
        <div className="tree" role="group" aria-label={h.tree.label}>
          <svg aria-hidden="true" className="tree-edges" width="936" height="444">
            <path d="M248 70 H294 M496 70 H520 V32 H614 M520 70 V108 H614 M248 184 H614 M248 260 H614 M248 336 H614" />
            <path d="M248 412 H614" className="dashed" />
            {[32, 108, ...SOURCES.slice(1)].map((y) => <path key={y} d={`M607 ${y - 4} L614 ${y} L607 ${y + 4}`} className="head" />)}
            <path d="M287 66 L294 70 L287 74" className="head" />
          </svg>
          {sources.map((name, i) => (
            <span key={name} {...(i === 4 ? tip(h.tree.judgeWhy, true) : {})} className="src" style={{ top: SOURCES[i] - 24 }}>{name}</span>
          ))}
          <span className="ask">{h.tree.ask}</span>
          <span className="num fork whole">{h.tree.whole}</span>
          <span className="num fork part">{h.tree.part}</span>
          {LEAVES.map((k, i) => (
            <Box key={k} lines={leafLines(k)} className="leaf" top={i * 76}>
              <span className="leaf-word"><MarkIcon mark={k} /><span style={{ color: `var(--st-${markFor(k)}-text)` }}>{t.word[k]}</span></span>
              <span className="num faint">{k === "contexto" ? h.tree.nota : h.tree.aviso}</span>
            </Box>
          ))}
        </div>
        <Box lines={[h.tree.correctLine, ...h.tree.correctTip]} className="correct">
          <span className="leaf-word">{h.tree.correct}</span><span className="dim">{h.tree.noMark}</span>
        </Box>
      </section>

      <section className="how-sec">
        <h2>{h.severity.title}</h2>
        <Box lines={[h.severity.ratio, ...h.severity.tip]} className="severity">
          <span className="num faint">{h.severity.figure}</span>
          <ol className="levels">
            {h.severity.levels.map((l) => (
              <li key={l.name} {...tip(l.full)} className={`level-${l.ticks}`}>
                <span className="level-name">{l.ticks ? <Meter lit={l.ticks} /> : <MarkIcon mark="puntualizacion" />}
                  <span>{l.name}</span></span>
                <span aria-hidden="true" className="level-bar" />
                <span className="num">{l.ratio}</span>
                <span className="level-example">{l.example}</span>
              </li>
            ))}
          </ol>
          <span className="passing"><span className="num">−1</span> {h.severity.passing}</span>
        </Box>
        <div className="not-figure">
          <span className="num faint">{h.severity.notFigure}</span>
          {h.severity.anchors.map((a, i) => (
            <span key={a.name} {...tip(a.items.join("\n"), true)} className="level-chip"><Meter lit={3 - i} /><span>{a.name}</span></span>
          ))}
        </div>
      </section>

      <section className="how-sec how-pair">
        <div>
          <h2>{h.confidence.title}</h2>
          <Box lines={h.confidence.tip} className="confidence">
            <div className="conf-scale">
              <span className="conf-cut" />
              {h.confidence.samples.map((s) => <span key={s.value} className="conf-dot" style={{ left: `${s.value}%` }} />)}
            </div>
            <div className="conf-ticks num faint">
              <span>0 %</span><span>{h.confidence.low}</span><span>60 %</span><span>{h.confidence.normal}</span><span>100 %</span>
            </div>
          </Box>
          <ul className="samples">
            {h.confidence.samples.map((s) => {
              const low = s.value < 60;
              return (
                <li key={s.value}>
                  <span className="num faint">{h.example}</span>
                  <span className="sample-head">
                    <MarkIcon mark={s.kind} dim={low} />
                    <span className="leaf-word" style={{ color: low ? "var(--t4)" : `var(--st-${markFor(s.kind)}-text)` }}>{t.word[s.kind]}</span>
                    <span className="num faint">{s.value} %{low && ` · ${h.confidence.lowWord}`}</span>
                  </span>
                  <span className="quote">{s.quote}</span>
                </li>
              );
            })}
          </ul>
        </div>
        <div>
          <h2>{h.sources.title}</h2>
          <Box lines={h.sources.tip} className="sources">
            <ol className="cascade">
              {h.sources.steps.map((s, i) => (
                <li key={s}>
                  <span className="num faint">{String(i + 1).padStart(2, "0")}</span>
                  <span className="box-name">{s}</span>
                  {i === 0 && <span className="num weight">{h.sources.more}</span>}
                  {i === 2 && <span className="num weight">{h.sources.less}</span>}
                  {i < 2 && <span className="small faint next">{h.sources.next}</span>}
                </li>
              ))}
            </ol>
          </Box>
        </div>
      </section>

      <Instructions t={t} prompts={prompts} say={say} />
      <General t={t} prompts={prompts} say={say} />
      {say.question}
    </main>
    <Footer lang={lang} prompts={prompts?.version} />
  </>);
}

type Say = ReturnType<typeof usePromptComment>;
const said = (t: Texts, sent: Sent) =>
  sent === "ok" ? t.how.feedback.sent : sent === "closed" ? t.say.commentsClosed : sent === "declined" ? t.say.notSent : t.say.failed;

/** A component's text cut into plain stretches and its rules, in text order; a rule may span several lines. */
function segments(c: Prompts["components"][number]): { text: string; rule?: string }[] {
  const found = c.rules.map((r) => ({ r, at: c.text.indexOf(r.text) })).filter((x) => x.at >= 0).sort((a, b) => a.at - b.at);
  const out: { text: string; rule?: string }[] = [];
  let at = 0;
  for (const { r, at: start } of found) {
    if (start < at) continue;
    out.push({ text: c.text.slice(at, start) }, { text: r.text, rule: r.id });
    at = start + r.text.length;
  }
  out.push({ text: c.text.slice(at) });
  return out;
}

/** Prompt text as prose (owner review 2026-11-21): a single newline joins its lines, a blank line or a "- " item starts
 * a new paragraph, and each {placeholder} is a small mono chip. */
function Prose({ text }: { text: string }) {
  const paragraphs: string[] = [];
  for (const block of text.split(/\n\s*\n/)) {
    let fresh = true;
    for (const raw of block.split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      if (fresh || line.startsWith("- ")) paragraphs.push(line);
      else paragraphs[paragraphs.length - 1] += ` ${line}`;
      fresh = false;
    }
  }
  return <>{paragraphs.map((para, i) => (
    <p key={i}>{para.split(/(\{[^{}\s]+\})/).map((part, j) => (j % 2 ? <code key={j} className="ph">{part}</code> : part))}</p>
  ))}</>;
}

interface Picked { component: string; rule?: string; quote?: string; range?: Range }
/** Where the floating "Comentar" sits: just after the selection's end, in the section's own coordinates. */
interface Spot { left: number; top: number }
const HIGHLIGHT = "say-quote";

/** The instructions: the version, one closed block per component. Each rule has its "Comentar" button (the comment
 * names the rule, with no quote); words selected inside a block get one small "Comentar" right beside them, which
 * comments with their quote. */
function Instructions({ t, prompts, say }: { t: Texts; prompts: Prompts | null | undefined; say: Say }) {
  const p = t.how.prompts;
  const box = useRef<HTMLElement>(null);
  const [picked, setPicked] = useState<(Picked & Spot) | null>(null);
  const [writing, setWriting] = useState<Picked | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    const change = () => {
      const sel = getSelection();
      const quote = sel?.toString().trim().slice(0, 1000) ?? "";
      const at = (n: Node | null | undefined) => (n?.nodeType === Node.ELEMENT_NODE ? n as Element : n?.parentElement) ?? null;
      const block = at(sel?.anchorNode)?.closest<HTMLElement>("[data-component]");
      if (!quote || !block || !box.current?.contains(block) || !block.contains(sel!.focusNode)) return setPicked(null);
      const rule = at(sel!.anchorNode)?.closest<HTMLElement>("[data-rule]");
      const range = sel!.getRangeAt(0).cloneRange();
      // The selection's last line box; jsdom has no layout for ranges, so it falls back to the end's element.
      const end = [...(range.getClientRects?.() ?? [])].at(-1) ?? at(sel!.focusNode)!.getBoundingClientRect();
      const frame = box.current.getBoundingClientRect();
      setPicked({ component: block.dataset.component!, quote, range, left: end.right - frame.left + 4, top: end.bottom - frame.top + 4,
        ...(rule?.contains(sel!.focusNode) ? { rule: rule.dataset.rule } : {}) });
    };
    document.addEventListener("selectionchange", change);
    return () => document.removeEventListener("selectionchange", change);
  }, []);

  // While the composer is open, its selected words stay marked (CSS Custom Highlight; browsers without it skip it).
  useEffect(() => {
    if (!writing?.range || typeof Highlight !== "function") return;
    CSS.highlights.set(HIGHLIGHT, new Highlight(writing.range));
    return () => { CSS.highlights.delete(HIGHLIGHT); };
  }, [writing]);

  const send = async () => {
    if (!writing || !text.trim()) return;
    setBusy(true);
    const { component, rule, quote } = writing;
    const sent = await say.send(component, text.trim(), { rule, quote });
    setBusy(false);
    setStatus(said(t, sent));
    if (sent === "ok") {
      setWriting(null);
      setText("");
    }
  };

  const ask = (what: Picked) => {
    setStatus("");
    setText("");
    setWriting(what);
    setPicked(null);
    getSelection()?.removeAllRanges();
  };
  const form = writing && (
    <div className="say-box">
      {writing.quote && <p className="quote small">«{writing.quote}»</p>}
      <textarea rows={3} maxLength={1000} value={text} readOnly={busy} aria-label={p.placeholder} placeholder={p.placeholder}
        onChange={(e) => setText(e.target.value)} />
      <div className="say-foot">
        <button type="button" className="pill quiet" disabled={busy} onClick={() => { setWriting(null); setText(""); }}>{t.say.cancel}</button>
        <button type="button" className="pill" disabled={busy || !text.trim()} onClick={send}>{busy ? t.say.sending : t.say.send}</button>
      </div>
    </div>
  );

  return (
    <section ref={box} id={p.id} className="how-sec how-prompts">
      <h2>{p.title}</h2>
      {prompts === undefined ? <p className="small dim">{p.loading}</p> : prompts === null ? <p className="small dim">{p.none}</p> : <>
        {/* The accordion as the board (S6How): the version row, then one row per component (title, id, rule count,
            chevron); open, its text as prose under the title column, each rule with its "Comentar". */}
        <div className="version">
          <span className="version-word">{p.version}</span> <span className="num">{prompts.version}</span>
          <a href={`/api/prompts/${encodeURIComponent(prompts.version)}`} download>{p.download}</a>
        </div>
        {prompts.components.map((c) => (
          <details key={c.id} data-component={c.id} className="component">
            <summary>
              <span className="box-name">{p.names[c.id] ?? c.id}</span>
              <span className="num comp-id">{c.id}</span>
              <span className="num">{c.rules.length > 0 && p.rules(c.rules.length)}</span>
              <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className="chevron"><path d="M3 4.5l3 3 3-3" /></svg>
            </summary>
            <div className="component-text">
              {segments(c).map((seg, i) => seg.rule
                ? (
                  <Fragment key={i}>
                    <div data-rule={seg.rule} className={`rule-row${writing?.component === c.id && writing.rule === seg.rule ? " on" : ""}`}>
                      <div className="rule"><Prose text={seg.text} /></div>
                      <button type="button" className="rule-say" onClick={() => ask({ component: c.id, rule: seg.rule })}>{p.commentRule}</button>
                    </div>
                    {writing?.component === c.id && writing.rule === seg.rule && form}
                  </Fragment>
                )
                : seg.text.trim() && <div key={i} className="text-run"><Prose text={seg.text} /></div>)}
              {!c.rules.length && !writing && (
                <button type="button" className="rule-say whole" onClick={() => ask({ component: c.id })}>{p.commentRule}</button>
              )}
              {writing?.component === c.id && !writing.rule && form}
            </div>
          </details>
        ))}
        {picked && !writing && (
          <button type="button" aria-label={p.commentSelection} className="pick-say" style={{ left: picked.left, top: picked.top }}
            onMouseDown={(e) => e.preventDefault()} onClick={() => ask(picked)}>{p.commentRule}</button>
        )}
        {status && <p role="status" className="small dim">{status}</p>}
      </>}
    </section>
  );
}

/** Ayúdanos, #feedback: a comment on the method, about one step (a component of the prompts file). */
function General({ t, prompts, say }: { t: Texts; prompts: Prompts | null | undefined; say: Say }) {
  const f = t.how.feedback;
  const [step, setStep] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [sent, setSent] = useState(false);

  const send = async () => {
    setBusy(true);
    setStatus("");
    const result = await say.send(step!, text.trim());
    setBusy(false);
    if (result === "ok") setSent(true);
    else setStatus(said(t, result));
  };

  // Two columns (canvas v58, S6-spec §8.2): the title and the anonymity line on the left, the one card on the right.
  return (
    <section id="feedback" className="how-sec how-feedback">
      <div className="feedback-side">
        <h2>{f.title}</h2>
        <p className="anon">{f.anonymous}</p>
      </div>
      <div className="say-card">
        {prompts === null && <p className="small dim">{t.how.prompts.none}</p>}
        {sent
          ? <p role="status" className="sent">{said(t, "ok")}</p>
          : <>
              {/* One select over every component of the served prompts file (9 today), none picked at first. */}
              <span className="step-pick">
                <select aria-label={f.step} value={step ?? ""} onChange={(e) => setStep(e.target.value || null)}>
                  <option value="" disabled>{f.step}</option>
                  {prompts?.components.map((c) => <option key={c.id} value={c.id}>{f.steps[c.id] ?? c.id}</option>)}
                </select>
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className="chevron"><path d="M3 4.5l3 3 3-3" /></svg>
              </span>
              <textarea rows={4} maxLength={1000} value={text} readOnly={busy} aria-label={f.placeholder} placeholder={f.placeholder}
                onChange={(e) => setText(e.target.value)} />
              <div className="card-foot">
                {status && <span role="status" className="small dim">{status}</span>}
                <button type="button" className="bone-button" disabled={busy || !step || !text.trim()} onClick={send}>
                  {busy ? t.say.sending : t.say.send}
                </button>
              </div>
            </>}
      </div>
    </section>
  );
}
