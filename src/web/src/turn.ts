// The turn of the DeFacto mark, like a lighthouse (owner, 2026-11-22; brand logo-spec.md §2, engine df-mark9.js): two
// sine-eased half turns with a short hold at 180°, where the mark reads «DE FACTO». Every other layer is a function of
// the angle, and the CSS keyframes sample it in 90 steps with linear timing between them, so all layers stay in step.

export interface Timing { dur: number; hold: number }
export const LARGE: Timing = { dur: 4.5, hold: 0.5 }; // «Cómo funciona» and the error pages
export const SMALL: Timing = { dur: 3.0, hold: 0.3 }; // the header
export const DELAY = 0.6; // after the first load; a hover turns at once

const sine = (x: number) => (1 - Math.cos(Math.PI * x)) / 2;
const bump = (a: number, c: number, w: number) => Math.exp(-(((a - c) / w) ** 2));

/** The arms' angle in degrees at time `t` (0–1) of the turn. */
export function angle({ dur, hold }: Timing, t: number): number {
  const h = hold / dur, half = (1 - h) / 2;
  return t < half ? 180 * sine(t / half) : t < half + h ? 180 : 180 + 180 * sine((t - half - h) / half);
}

/** The beam: on the way out, gone before it would cross ACTO; quieter on the way back. */
export const beam = (a: number) => a < 130 ? (0.3 * Math.min(1, a / 25) + 0.22 * bump(a, 90, 16)) * (a > 100 ? (130 - a) / 30 : 1)
  : a > 280 ? 0.18 * Math.sin(((a - 280) / 80) * Math.PI) : 0;
/** The halo flashes when the light faces the reader (90°) and dims behind the tower (270°). */
export const glow = (a: number) => ({ opacity: 0.4 + 0.5 * bump(a, 90, 18) - 0.15 * bump(a, 270, 40), scale: 1 + 0.45 * bump(a, 90, 18) });
/** The arms dim while they come back foreshortened, so they never read as a dash between E and A. */
export const arms = (a: number) => (a > 298 && a < 352 ? 1 - 0.65 * Math.sin(((a - 298) / 54) * Math.PI) : 1);
/** How far ACTO has stepped right (0–1) while the F faces it. */
export const shift = (a: number) => (1 - Math.cos(((a <= 180 ? a : 360 - a) * Math.PI) / 180)) / 2;

/** A CSS @keyframes rule that samples `prop` of the angle in 90 steps. */
export function keyframes(name: string, timing: Timing, prop: (a: number) => string): string {
  const frames = Array.from({ length: 91 }, (_, i) => `${((i / 90) * 100).toFixed(2)}%{${prop(angle(timing, i / 90))}}`);
  return `@keyframes ${name}{${frames.join("")}}`;
}

/** Every keyframes rule of both timings: spin, arms, beam, glow and ACTO's step, suffixed -l (large) and -s (small). */
export function turnCss(): string {
  return ([["l", LARGE], ["s", SMALL]] as const).flatMap(([k, timing]) => [
    keyframes(`df-spin-${k}`, timing, (a) => `transform:rotateY(${a.toFixed(2)}deg)`),
    keyframes(`df-arms-${k}`, timing, (a) => `opacity:${arms(a).toFixed(3)}`),
    keyframes(`df-beam-${k}`, timing, (a) => `opacity:${beam(a).toFixed(3)}`),
    keyframes(`df-glow-${k}`, timing, (a) => { const g = glow(a); return `opacity:${g.opacity.toFixed(3)};transform:scale(${g.scale.toFixed(3)})`; }),
    keyframes(`df-shift-${k}`, timing, (a) => `transform:translateX(calc(var(--df-shift) * ${shift(a).toFixed(4)}))`),
  ]).join("\n");
}
