// The verdict kind of a flag (ARCHITECTURE Components: Verdict kinds): the web app names and draws it, the collector
// counts it for the video list.

/** The fields of a flag that decide its kind. */
export interface Judged {
  type: string;
  label: string;
  judge?: { verdict: string };
}

/** The marks in the brand's fixed order; each name is its token, `--st-<mark>`. */
export const MARKS = ["falso", "enganoso", "retorica", "evasiva", "contexto"] as const;
export type Mark = (typeof MARKS)[number];

/** What a flag is called and filtered by: its mark, except a judge's nitpick, a "Puntualización". */
export const KINDS = ["falso", "enganoso", "retorica", "evasiva", "puntualizacion", "contexto"] as const;
export type Kind = (typeof KINDS)[number];
/** An aviso is every kind but a context note (owner, S4). */
export const AVISOS = KINDS.filter((k) => k !== "contexto");

export const nitpick = (f: Judged) => f.judge?.verdict === "nitpick";

export function markOf(f: Judged): Mark {
  if (f.type === "context" || nitpick(f)) return "contexto";
  if (f.type === "question") return "evasiva";
  if (f.type === "inaccuracy") return f.label === "false" ? "falso" : "enganoso";
  return "retorica";
}

export const kindOf = (f: Judged): Kind => (nitpick(f) ? "puntualizacion" : markOf(f));
export const markFor = (k: Kind): Mark => (k === "puntualizacion" ? "contexto" : k);

/** How many flags of each kind. */
export function countKinds(flags: Judged[]): Record<Kind, number> {
  const counts = Object.fromEntries(KINDS.map((k) => [k, 0])) as Record<Kind, number>;
  for (const f of flags) counts[kindOf(f)] += 1;
  return counts;
}
