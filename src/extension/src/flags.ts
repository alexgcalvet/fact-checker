export interface Flag {
  id: string;
  t: number;
  speaker: string;
  quote: string;
  type: string;
  label: string;
  reason: string;
  confidence: number;
  related: {
    t: number | null;
    quote: string;
    date?: string;
    source?: { publisher: string; url: string };
  } | null;
  sources: { publisher: string; url: string; date: string }[];
  note: string | null;
  measures?: { name: string; value: string; source: string; tier: number; supports: boolean }[];
  controversy?: string | null;
  answer?: "answered" | "partial" | "dodged";
  promise?: { made: string; figure: string; deadline: string; status: "met" | "partly met" | "not met" | "in progress" } | null;
  on_player?: boolean;
  /** The person's latest mark, added by the helper on GET. */
  mark?: "correct" | "unfair";
  /** The judge's ruling after the whole video: `speaker` when the line belongs to someone else. */
  judge?: { verdict: "keep" | "nitpick" | "drop"; reason: string; speaker?: string; severity?: Severity };
}

export type Severity = "minor" | "moderate" | "serious";

export interface FlagFile {
  video_id: string;
  published_at: string | null;
  status: "running" | "done" | "stopped";
  stop_reason: string | null;
  /** The end of the parts analysed without a gap from the start second. */
  analysed_until?: number;
  /** Seconds from the analyse request to the first part written; absent until then, and in a shared copy. */
  first_flags_s?: number;
  /** "shared" when the flags came from another person's analysis through the author's collector. */
  source?: "shared";
  /** Per speaker name, once the voices are told apart: the role, the person's name, seconds of speech, who set the role. */
  people?: Record<string, { role: "host" | "guest"; person: string; spoken_s: number; set_by: "llm" | "person" }>;
  flags: Flag[];
}

/** The display name of each label id, per language of the interface (texts.ts holds every other text). */
export const LABELS: Record<"es" | "en", Record<string, string>> = {
  es: {
    ad_hominem: "Ad hominem",
    tu_quoque: "Y tú más",
    false_dilemma: "Falso dilema",
    straw_man: "Hombre de paja",
    false_cause: "Causa falsa",
    hasty_generalization: "Generalización apresurada",
    vague_authority: "Autoridad vaga",
    insinuation: "Insinuación",
    double_standard: "Doble rasero",
    cherry_picking: "Datos a conveniencia",
    appeal_to_fear: "Apelación al miedo",
    false: "Dato falso",
    misleading: "Dato engañoso",
    disputed: "Dato discutido",
    definition_swap: "Cambio de métrica",
    plan_as_fact: "Plan contado como hecho",
    dodged: "Pregunta esquivada",
    partial: "Pregunta respondida a medias",
    self: "Contradicción",
    record: "Contradice lo que dijo antes",
    promise: "Promesa incumplida",
    person: "Contexto",
    case: "Contexto",
    event: "Contexto",
  },
  en: {
    ad_hominem: "Ad hominem",
    tu_quoque: "Whataboutism",
    false_dilemma: "False dilemma",
    straw_man: "Straw man",
    false_cause: "False cause",
    hasty_generalization: "Hasty generalization",
    vague_authority: "Vague authority",
    insinuation: "Insinuation",
    double_standard: "Double standard",
    cherry_picking: "Cherry-picking",
    appeal_to_fear: "Appeal to fear",
    false: "False claim",
    misleading: "Misleading claim",
    disputed: "Disputed claim",
    definition_swap: "Metric swap",
    plan_as_fact: "Plan told as fact",
    dodged: "Dodged question",
    partial: "Half-answered question",
    self: "Contradiction",
    record: "Contradicts what they said before",
    promise: "Broken promise",
    person: "Context",
    case: "Context",
    event: "Context",
  },
};
export const NITPICK_NAME = { es: "Puntualización", en: "Nitpick" };
export const SERIOUS_NAME = { es: "grave", en: "serious" };

/**
 * The verdict look of a flag: its word (`word`), its 16 px disc (`dot`, a CSS background image), the hue of its
 * confidence slats (`color`) and of its strip mark (`mark`). It never tints a surface. `family` names the panel filter.
 */
export interface Look { color: string; dot: string; word: string; mark: string; family: string }

/** The five verdict hues of the design: a text tone for the word, a marker tone for the disc. */
export const HUES = {
  er: { text: "#F49A9C", marker: "#E5484D" },
  mi: { text: "#F0BE6A", marker: "#D99A2B" },
  rh: { text: "#E9A3CB", marker: "#D06BA8" },
  in: { text: "#9DB2D6", marker: "#5B8DE0" },
  ok: { text: "#7FD6C2", marker: "#29A98E" },
};
type Kind = keyof typeof HUES;
// ✕ false, ! misleading, ~ rhetoric, i context, ✓ correct, on a 16 px grid centred on 0.
const GLYPHS: Record<Kind, string> = {
  er: "M-2.3 -2.3L2.3 2.3M2.3 -2.3L-2.3 2.3",
  mi: "M0 -3.1V0.6M0 2.7V2.8",
  rh: "M-3 0.9C-2 -1.5 -0.9 -1.3 0 0S2 1.5 3 -0.9",
  in: "M0 -2.9V-2.8M0 -0.6V3",
  ok: "M-2.8 0.1L-0.8 2.2L2.9 -2.1",
};
export const TEXT_1 = "rgba(238,236,229,.95)";
export const TEXT_2 = "rgba(226,229,234,.6)";
const GREY = "#5A6680";

/** A verdict disc: a soft halo, the disc, a warm core and the glyph in night ink. */
const disc = (fill: string, glyph: string) => `url("data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -8 16 16"><circle r="8" fill="${fill}" opacity=".1"/>` +
  `<circle r="7.2" fill="${fill}" opacity=".16"/><circle r="6.4" fill="${fill}" opacity=".3"/>` +
  `<circle r="5.6" fill="${fill}"/><circle r="3.4" fill="#FFF0D6" opacity=".22"/><path d="${glyph}" ` +
  `transform="scale(.92)" fill="none" stroke="#05070B" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
)}")`;
const verdictLook = (kind: Kind, family: string): Look => {
  const { marker, text } = HUES[kind];
  return { color: marker, dot: disc(marker, GLYPHS[kind]), word: text, mark: marker, family };
};

const FALSE = verdictLook("er", "Falsos");
// The figure is not false, but it does not say what it seems to say: an amber "!" in the same family.
const MISLEADING = verdictLook("mi", "Falsos");
const DISPUTED: Look = { ...MISLEADING, word: TEXT_1 };
const RHETORIC = verdictLook("rh", "Retórica");
// A contradiction is rhetoric too; its lighter disc tells it apart from a fallacy on the strip.
const CONTRADICTION: Look = { ...RHETORIC, dot: disc(HUES.rh.text, GLYPHS.rh), mark: HUES.rh.text };
const CONTEXT = verdictLook("in", "Contexto");
// A nitpick is a minor correction: the "!" on a grey disc, its word in the secondary text tone.
const NITPICK: Look = { color: GREY, dot: disc(GREY, GLYPHS.mi), word: TEXT_2, mark: GREY, family: "Puntualizaciones" };

export const TYPE_LOOK: Record<string, Look> = {
  inaccuracy: FALSE, fallacy: RHETORIC, question: RHETORIC, contradiction: CONTRADICTION, context: CONTEXT,
};
const LABEL_LOOK: Record<string, Look> = {
  misleading: MISLEADING, definition_swap: MISLEADING, plan_as_fact: MISLEADING, disputed: DISPUTED,
};

/** Every family, in the order of the panel filters; texts.ts holds its name in each language. */
export const FAMILIES = [FALSE.family, RHETORIC.family, CONTEXT.family, NITPICK.family];

/** The judge's verdict; a flag the person marked correct stays as found. */
export const verdict = (f: Pick<Flag, "judge" | "mark">) => (f.mark === "correct" ? undefined : f.judge?.verdict);

export const look = (f: Pick<Flag, "type" | "label" | "judge" | "mark">): Look =>
  verdict(f) === "nitpick" ? NITPICK : LABEL_LOOK[f.label] ?? TYPE_LOOK[f.type];

/** The judge's severity of a kept flag; a nitpick has none. */
export const severity = (f: Pick<Flag, "judge" | "mark">) => (verdict(f) === "nitpick" ? undefined : f.judge?.severity);

/** The card title: "Puntualización" for a nitpick, else the name of the label, with "· grave" when serious. */
export const title = (f: Flag, lang: "es" | "en" = "es") =>
  (verdict(f) === "nitpick" ? NITPICK_NAME[lang]
    : (LABELS[lang][f.label] ?? f.label) + (severity(f) === "serious" ? ` · ${SERIOUS_NAME[lang]}` : ""));
