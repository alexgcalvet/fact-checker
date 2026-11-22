// The figures of a guest and of "el debate" (canvas S5 §4), computed once for the profile and the comparison: every rate
// per 10 minutes of the person's own speech, and the debate pooled over its guests, never one other person.
import { kindOf, type Flag, type Kind } from "./marks";
import type { Lang } from "./texts";
import type { Meta, Summary } from "./Viewer";

export const FEW_DATA_S = 900; // under 15 min of speech a rate is shaky: it reads "pocos datos"
export const LIT = { bajo: 1, medio: 2, alto: 3 };

export type Person = NonNullable<Meta["people"]>[string];

export const per10 = (n: number, seconds: number) => n / (seconds / 600);
export const r1 = (x: number) => Math.round(x * 10) / 10;
export const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
/** A person's level, provisional (owner, S5): under 5 avisos per 10 min of their speech, to 8,9, from 9. */
export const level = (rate: number) => (rate >= 9 ? "alto" : rate >= 5 ? "medio" : "bajo");
const pct = (n: number, of: number) => Math.round((100 * n) / of);

export function useNumbers(lang: Lang) {
  const one = new Intl.NumberFormat(lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const whole = new Intl.NumberFormat(lang, { maximumFractionDigits: 0 });
  return { one: (x: number) => one.format(x), whole: (x: number) => whole.format(x) };
}

/** The seconds every voice spoke, the host's included: the base of a speaking share. */
export const allSpoken = (meta: Meta) => sum(Object.values(meta.people ?? {}).map((x) => x.spoken_s ?? 0));

/** One guest's figures; with no speaking time the rates use the video's length. */
export function guestFigures(meta: Meta, flags: Flag[], name: string, card: Summary) {
  const people = meta.people ?? {};
  const me: Person | undefined = people[name];
  const speech = !!me?.spoken_s;
  const base = speech ? me.spoken_s : meta.duration;
  const mine = flags.filter((f) => f.speaker === name);
  const avisos = mine.filter((f) => kindOf(f) !== "contexto");
  const spoken = allSpoken(meta);
  const eluded = card.dodged + card.partial;
  return {
    me, speech, base, mine, avisos,
    ofKind: (k: Kind) => mine.filter((f) => kindOf(f) === k),
    rate: r1(per10(avisos.length, base)),
    share: speech && spoken ? r1((100 * me.spoken_s) / spoken) : null,
    fewData: speech && me.spoken_s < FEW_DATA_S,
    graves: r1(per10(card.severity.serious, base)),
    correct: card.checked ? pct(card.verdicts.correct, card.checked) : null,
    eluded,
    eludedPct: card.asked ? pct(eluded, card.asked) : null,
  };
}

/** "El debate": the guests together, by their own speaking time; null for an interview or without speaking time. */
export function debateFigures(meta: Meta, flags: Flag[]) {
  const people = meta.people ?? {};
  const guests = meta.guests;
  if (guests.length < 2 || !guests.every((g) => people[g]?.spoken_s)) return null;
  const spoken = sum(guests.map((g) => people[g].spoken_s));
  const cards = guests.map((g) => meta.summary?.[g]).filter((c): c is Summary => !!c);
  const count = (k?: Kind) => flags.filter((f) => guests.includes(f.speaker) && (k ? kindOf(f) === k : kindOf(f) !== "contexto")).length;
  const checked = sum(cards.map((c) => c.checked));
  const asked = sum(cards.map((c) => c.asked));
  return {
    rate: r1(per10(count(), spoken)),
    kindRate: (k: Kind) => r1(per10(count(k), spoken)),
    graves: r1(per10(sum(cards.map((c) => c.severity.serious)), spoken)),
    correct: checked ? pct(sum(cards.map((c) => c.verdicts.correct)), checked) : null,
    eluded: asked ? pct(sum(cards.map((c) => c.dodged + c.partial)), asked) : null,
  };
}
