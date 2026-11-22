// The DeFacto mark (owner and design panel, 2026-11-22; brand sketches/defacto/logo-spec.md). Two masters of
// defacto-turn.json (cap height 100, baseline 0, y down) draw it, so the still mark and its turning layers share one
// geometry: `N`, tracked as an inscription, for the header; `L` for the large mark of «Cómo funciona» and the error
// pages. Under cap 24 the window is a flat 2×4 px amber pane on whole pixels, with no beam and no halo; from cap 24 it is
// a lit gradient with a halo, and a beam turns with the arms.
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { L, N } from "../brand/defacto-turn.json";
import phoneMark from "../brand/defacto-wordmark-phone.svg";
import { TEXTS, type Lang } from "./texts";
import { DELAY, LARGE, SMALL, turnCss } from "./turn";

// The turn's keyframes, sampled from its angle (turn.ts), added to the page once.
if (!document.getElementById("df-turn")) {
  document.head.append(Object.assign(document.createElement("style"), { id: "df-turn", textContent: turnCss() }));
}

type Master = typeof N;
const SHIFT = 8; // ACTO steps this many units right while the F faces it
const BEAM = 230, SPREAD = 10; // the beam's length and half-height at its far end, in units
const SEEN = "df-turned";

/** The box, the viewBox and the window of a master at `cap` px, as the brand's generator (r6-build.js) lays them out. */
function layout(o: Master, cap: number) {
  const s = cap / 100, small = cap < 24, [wx, wy, ww, wh] = o.win, lx = wx + ww / 2, ly = wy + wh / 2;
  const beam = small ? 0 : BEAM;
  const vx0 = Math.min(o.x0, lx - beam) - 2, vy0 = -103, vx1 = o.x1 + SHIFT + 2, vy1 = o.bot + 2;
  const w = Math.ceil((vx1 - vx0) * s), h = Math.ceil((vy1 - vy0) * s), axis = (o.axis - vx0) * s;
  // A small pane snaps to whole pixels: 2 px wide on the tower's axis, 4 px tall at the window's middle.
  const px = Math.round(axis - 1), py = Math.round((ly - vy0) * s - 2);
  return {
    o, cap, s, small, w, h, axis, viewBox: `${vx0} ${vy0} ${w / s} ${h / s}`, lx, ly, wh, beam,
    pane: small ? { x: vx0 + px / s, y: vy0 + py / s, width: 2 / s, height: 4 / s } : { x: wx, y: wy, width: ww, height: wh },
    glow: { left: px - 3, top: py - 3 },
    // How far the letters' centre sits right of the box's centre: the beam widens the box on the left.
    offset: ((o.x0 + o.x1) / 2 - (vx0 + vx1) / 2) * s,
  };
}
type Layout = ReturnType<typeof layout>;
const HEADER = layout(N, 18);

function Svg({ c, children }: { c: Layout; children: ReactNode }) {
  return <svg width={c.w} height={c.h} viewBox={c.viewBox} aria-hidden="true">{children}</svg>;
}

/** The window: a flat amber pane when small, else a lit gradient (ids unique per mark). */
function Pane({ c, id }: { c: Layout; id: string }) {
  if (c.small) return <rect className="df-pane" {...c.pane} style={{ fill: "var(--amber)" }} />;
  return <>
    <defs><linearGradient id={`${id}w`} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" style={{ stopColor: "var(--df-window-hi)" }} /><stop offset="1" style={{ stopColor: "var(--amber)" }} />
    </linearGradient></defs>
    <rect className="df-pane" {...c.pane} fill={`url(#${id}w)`} />
  </>;
}

/** The arms (and, when large, the beam behind the letters) turning about the tower's axis. */
function Turning({ c, children }: { c: Layout; children: ReactNode }) {
  return (
    <span className="df-axis" style={{ perspective: `${c.cap * 9}px`, perspectiveOrigin: `${c.axis}px 50%` }}>
      <span className="df-turn" style={{ transformOrigin: `${c.axis}px 50%` }}><Svg c={c}>{children}</Svg></span>
    </span>
  );
}

/** The layers of a turn: the beam, DE, ACTO (which steps right), the fixed tower with its window, and the arms. They exist
 * only while the mark turns. */
function Layers({ c, id, arms }: { c: Layout; id: string; arms: RefObject<SVGPathElement | null> }) {
  const { lx, ly, wh, beam } = c;
  return (
    <span className="df-layers" aria-hidden="true">
      {beam > 0 && <Turning c={c}>
        <defs><linearGradient id={`${id}b`} gradientUnits="userSpaceOnUse" x1={lx} y1="0" x2={lx - beam} y2="0">
          <stop offset="0" style={{ stopColor: "var(--amber)", stopOpacity: .8 }} />
          <stop offset=".45" style={{ stopColor: "var(--amber)", stopOpacity: .2 }} />
          <stop offset="1" style={{ stopColor: "var(--amber)", stopOpacity: 0 }} />
        </linearGradient></defs>
        <polygon className="df-beam" fill={`url(#${id}b)`}
          points={`${lx},${ly - wh * .3} ${lx - beam},${ly - SPREAD} ${lx - beam},${ly + SPREAD} ${lx},${ly + wh * .3}`} />
      </Turning>}
      <Svg c={c}><path d={c.o.de} /></Svg>
      <span className="df-shift" style={{ "--df-shift": `${SHIFT * c.s}px` } as React.CSSProperties}><Svg c={c}><path d={c.o.acto} /></Svg></span>
      <Svg c={c}><path d={c.o.tower} /><Pane c={c} id={`${id}t`} /></Svg>
      <Turning c={c}><path ref={arms} className="df-arms" d={c.o.arms} /></Turning>
    </span>
  );
}

/** A mark that turns for `seconds`: on load (`load` says whether it may), and again whenever `again` is called, unless
 * it is turning. `onStart` runs when the arms start. The layers go on animationend, animationcancel or after the delay,
 * the turn and half a second. */
function useTurn(seconds: number, load: () => boolean, may: () => boolean, onStart?: () => void) {
  const [turn, setTurn] = useState<"load" | "now" | null>(null);
  const arms = useRef<SVGPathElement>(null);
  useEffect(() => { if (load()) setTurn("load"); }, []);
  useEffect(() => {
    const el = arms.current;
    if (!turn || !el) return;
    const done = () => setTurn(null);
    const start = (e: Event) => { if (e.target === el) onStart?.(); };
    const end = (e: Event) => { if (e.target === el) done(); };
    el.addEventListener("animationstart", start);
    el.addEventListener("animationend", end);
    el.addEventListener("animationcancel", end);
    const timer = setTimeout(done, (DELAY + seconds + 0.5) * 1000); // never leave the layers mounted
    return () => {
      el.removeEventListener("animationstart", start);
      el.removeEventListener("animationend", end);
      el.removeEventListener("animationcancel", end);
      clearTimeout(timer);
    };
  }, [turn]);
  const again = () => { if (!turn && may()) setTurn("now"); };
  const classes = `${turn ? " df-once" : ""}${turn === "now" ? " df-now" : ""}`;
  return { turn, arms, again, classes };
}

const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
// Only a laptop header turns, and never with reduced motion.
const headerMay = () => !still() && matchMedia("(min-width: 768px)").matches;
const firstInSession = () => {
  try {
    return !sessionStorage.getItem(SEEN);
  } catch {
    return false; // no storage: never turn on every page
  }
};
const remember = () => { try { sessionStorage.setItem(SEEN, "1"); } catch { /* the next page turns */ } };

/** The header's link home: the DeFacto inscription. On a laptop it turns once per session after the first load, and
 * again at once whenever the mouse or the keyboard's focus comes to it (owner, 2026-11-22). A phone shows the still
 * phone master (cap 16, +12 tracking, no pane). */
export function HomeMark({ lang, home }: { lang: Lang; home: boolean }) {
  const id = useId();
  const { turn, arms, again, classes } = useTurn(SMALL.dur, () => firstInSession() && headerMay(), headerMay, remember);
  return (
    <a href={`/${lang}/`} className={`df-mark${classes}`} aria-label={TEXTS[lang].mark}
      aria-current={home ? "page" : undefined} onMouseEnter={again} onFocus={again}>
      <span className="df-laptop" style={{ width: HEADER.w }}>
        <Svg c={HEADER}><g className="df-rest"><path d={N.rest} /><Pane c={HEADER} id={id} /></g></Svg>
        <span className="df-hglow" style={HEADER.glow} />
        {turn && <Layers c={HEADER} id={id} arms={arms} />}
      </span>
      <img className="df-phone" src={phoneMark} alt="" width={107} height={17} />
    </a>
  );
}

/** The large mark (cap ≥ 24): centred on its letters, with its lit window and halo at rest; it turns with the beam and
 * the halo's flash once on load, never with reduced motion, and again under the mouse when `hover` is set. `caps` gives
 * the laptop and the phone size. */
export function BigMark({ caps, hover = false }: { caps: [number, number]; hover?: boolean }) {
  const id = useId();
  const [laptop] = useState(() => matchMedia("(min-width: 768px)").matches);
  // A narrow phone (360) cannot hold the letters at the phone cap within its 16 px gutters: the cap shrinks to fit.
  const fit = Math.floor((innerWidth - 2 * 16) * 100 / (L.x1 - L.x0));
  const c = layout(L, laptop ? caps[0] : Math.min(caps[1], fit));
  const { turn, arms, again, classes } = useTurn(LARGE.dur, () => !still(), () => hover && !still());
  return (
    <div className={`df-big df-mark-big${classes}`} role="img" aria-label="DeFacto" onMouseEnter={again}
      style={{ width: c.w, height: c.h, translate: `${-c.offset}px 0` }}>
      <Svg c={c}><g className="df-rest"><path d={L.rest} /><Pane c={c} id={`${id}r`} /></g></Svg>
      <span className="df-halo"><Svg c={c}>
        <defs><radialGradient id={`${id}h`}>
          <stop offset="0" style={{ stopColor: "var(--amber)", stopOpacity: .45 }} />
          <stop offset=".5" style={{ stopColor: "var(--amber)", stopOpacity: .12 }} />
          <stop offset="1" style={{ stopColor: "var(--amber)", stopOpacity: 0 }} />
        </radialGradient></defs>
        <circle className="df-glow" cx={c.lx} cy={c.ly} r={c.wh * .85} fill={`url(#${id}h)`} />
      </Svg></span>
      {turn && <Layers c={c} id={id} arms={arms} />}
    </div>
  );
}
