// The CALVET verdict mark of each flag (ARCHITECTURE Decisions, S1). Its colours are the brand's --st-* tokens; the
// kinds themselves live in src/shared/kinds.ts, shared with the collector.
import { markOf } from "../../shared/kinds";

export { AVISOS, KINDS, MARKS, kindOf, markFor, markOf, nitpick, type Kind, type Mark } from "../../shared/kinds";

/** A flag as the public API serves it (docs/api-examples/debate-flags.json). */
export interface Flag {
  id: string;
  t: number;
  speaker: string;
  quote: string;
  type: string;
  label: string;
  reason: string;
  confidence: number;
  sources: { publisher: string; url: string; date: string }[];
  judge?: { verdict: "keep" | "nitpick" | "drop"; reason: string; severity?: "serious" | "moderate" | "minor" };
}

/** Under this confidence a flag keeps its mark, dims its word and reads "confianza baja". */
const LOW = 0.6;

/** A context note states no verdict, so it is never low. */
export const low = (f: Flag) => f.confidence < LOW && markOf(f) !== "contexto";

/** The colour of the mark's word on night: dimmed under the low confidence. */
export const wordColor = (f: Flag) => (low(f) ? "var(--t4)" : `var(--st-${markOf(f)}-text)`);
