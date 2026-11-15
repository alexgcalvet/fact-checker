// Every text a person reads, per language. The interface speaks the browser's language unless the ⚙ box picks one.
import { LABELS, NITPICK_NAME, SERIOUS_NAME } from "./flags";

export const AGENT_GUIDE = "https://github.com/alexgcalvet/fact-checker/blob/main/INSTALL-AGENT.md";
export const PRIVACY = "https://github.com/alexgcalvet/fact-checker/blob/main/PRIVACY.md";

/** The kind of the helper's stop reason, which picks its line in `stopped`; the raw reason stays in the flag file. */
export type StopKind = "captions" | "speech" | "budget" | "provider" | "other";
export const stopKind = (reason: string | null): StopKind => {
  const r = reason ?? "";
  if (r === "budget") return "budget";
  if (r.includes("yt-dlp")) return "captions";
  if (r.includes("speech engine")) return "speech";
  if (/claude -p|codex exec|API|is not set/.test(r)) return "provider";
  return "other";
};

export const TEXTS = {
  es: {
    labels: LABELS.es,
    nitpick: NITPICK_NAME.es,
    serious: SERIOUS_NAME.es,
    families: { Falsos: "Falsos", Retórica: "Retórica", Contexto: "Contexto", Puntualizaciones: "Puntualizaciones" } as
      Record<string, string>,
    confidence: "Confianza",
    pin: "Fijar (P)",
    pinChip: "Fijar",
    close: "Cerrar",
    ask: "¿Es justo este aviso?",
    agree: "De acuerdo",
    disagree: "No",
    why: "¿Por qué? (opcional)",
    save: "Guardar",
    cancel: "Cancelar",
    markedCorrect: "Marcado: correcto",
    markedUnfair: "Marcado: injusto",
    youMarked: "Marcaste",
    change: "cambiar",
    before: "Antes",
    now: "Ahora",
    months: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
      "noviembre", "diciembre"],
    monthOf: (month: string, year: string) => `${month} de ${year}`,
    status: { met: "cumplida", "partly met": "cumplida a medias", "not met": "no cumplida", "in progress": "en curso" } as
      Record<string, string>,
    promised: (made: string, figure: string, deadline: string, status: string) =>
      `Prometido en ${made}: ${figure} para ${deadline} · Estado: ${status}`,
    controversy: "Polémica",
    updated: "Dato actualizado",
    sources: (n: number) => `${n} ${n === 1 ? "fuente" : "fuentes"}`,
    details: "Detalles",
    panel: "Avisos",
    export: "Exportar resumen",
    settings: "Ajustes",
    all: "Todos",
    roles: { host: "Host", guest: "Invitada" },
    live: "Ir al directo",
    dropped: "Descartado por el juez",
    droppedAll: (n: number) => `Descartados por el juez (${n})`,
    size: "Texto",
    side: "Tarjetas",
    left: "izquierda",
    right: "derecha",
    quiet: "Solo graves",
    language: "Idioma",
    analyze: "Analizar este vídeo",
    preparing: "Preparando el análisis…",
    stopped: {
      captions: "YouTube no dio los subtítulos. Vuelve a intentarlo en unos minutos.",
      speech: "el vídeo no tiene subtítulos y este equipo no puede transcribir el audio. Ejecuta fact-checker doctor.",
      budget: "se llegó al límite de lecturas de este vídeo.",
      provider: "el modelo de IA no respondió. Vuelve a intentarlo o ejecuta fact-checker doctor.",
      other: "error inesperado. Vuelve a intentarlo o ejecuta fact-checker doctor.",
    } as Record<StopKind, string>,
    stoppedLine: (why: string) => `El análisis se paró: ${why}`,
    shared: "Análisis compartido · gratis",
    helperDown: [
      "El ayudante de fact-checker no responde.",
      `¿No lo has instalado, o falla? Dile a tu asistente de IA (Claude o ChatGPT): «Instala fact-checker siguiendo ${AGENT_GUIDE}»`,
      "¿Ya lo instalaste? Ejecuta fact-checker doctor en un terminal.",
    ],
    sharing: {
      on: "Tus marcas se comparten con el autor para mejorar el detector · Desactivar en ⚙",
      off: "Tus marcas no se comparten · Activar en ⚙",
      toggle: "Compartir mis marcas y análisis",
    },
    consent: {
      ask: "¿Compartir tus marcas y análisis con el autor para mejorar el detector? Se envían el aviso, la frase, tu motivo y el vídeo; nada de tu equipo.",
      yes: "Sí, compartir",
      no: "No",
      privacy: "Privacidad",
    },
    signals: "Señales automáticas, no veredictos",
    spend: {
      claude: "Usa tu suscripción de Claude: un vídeo de 1 h gasta una parte notable de tu límite",
      codex: "Usa tu suscripción de ChatGPT: un vídeo de 1 h gasta una parte notable de tu límite",
      api: "Se cobra en tu cuenta de API",
    } as Record<string, string>,
  },
  en: {
    labels: LABELS.en,
    nitpick: NITPICK_NAME.en,
    serious: SERIOUS_NAME.en,
    families: { Falsos: "False", Retórica: "Rhetoric", Contexto: "Context", Puntualizaciones: "Nitpicks" } as
      Record<string, string>,
    confidence: "Confidence",
    pin: "Pin (P)",
    pinChip: "Pin",
    close: "Close",
    ask: "Is this flag fair?",
    agree: "Agree",
    disagree: "Disagree",
    why: "Why? (optional)",
    save: "Save",
    cancel: "Cancel",
    markedCorrect: "Marked: correct",
    markedUnfair: "Marked: unfair",
    youMarked: "You marked",
    change: "change",
    before: "Before",
    now: "Now",
    months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
      "November", "December"],
    monthOf: (month: string, year: string) => `${month} ${year}`,
    status: { met: "kept", "partly met": "partly kept", "not met": "not kept", "in progress": "in progress" } as
      Record<string, string>,
    promised: (made: string, figure: string, deadline: string, status: string) =>
      `Promised in ${made}: ${figure} by ${deadline} · Status: ${status}`,
    controversy: "Controversy",
    updated: "Updated figure",
    sources: (n: number) => `${n} ${n === 1 ? "source" : "sources"}`,
    details: "Details",
    panel: "Flags",
    export: "Export summary",
    settings: "Settings",
    all: "All",
    roles: { host: "Host", guest: "Guest" },
    live: "Jump to now",
    dropped: "Dropped by the judge",
    droppedAll: (n: number) => `Dropped by the judge (${n})`,
    size: "Text",
    side: "Cards",
    left: "left",
    right: "right",
    quiet: "Serious only",
    language: "Language",
    analyze: "Analyze this video",
    preparing: "Preparing the analysis…",
    stopped: {
      captions: "YouTube did not give the captions. Try again in a few minutes.",
      speech: "the video has no captions and this computer cannot transcribe the audio. Run fact-checker doctor.",
      budget: "it reached the reading limit of this video.",
      provider: "the AI model did not answer. Try again or run fact-checker doctor.",
      other: "unexpected error. Try again or run fact-checker doctor.",
    } as Record<StopKind, string>,
    stoppedLine: (why: string) => `The analysis stopped: ${why}`,
    shared: "Shared analysis · free",
    helperDown: [
      "The fact-checker helper does not answer.",
      `Not installed, or broken? Tell your AI assistant (Claude or ChatGPT): "Install fact-checker by following ${AGENT_GUIDE}"`,
      "Already installed? Run fact-checker doctor in a terminal.",
    ],
    sharing: {
      on: "Your marks are shared with the author to improve the detector · Turn off in ⚙",
      off: "Your marks are not shared · Turn on in ⚙",
      toggle: "Share my marks and analyses",
    },
    consent: {
      ask: "Share your marks and analyses with the author to improve the detector? The flag, the quote, your reason and the video are sent; nothing from your computer.",
      yes: "Yes, share",
      no: "No",
      privacy: "Privacy",
    },
    signals: "Automatic signals, not verdicts",
    spend: {
      claude: "Uses your Claude subscription: a 1-hour video spends a notable share of your limit",
      codex: "Uses your ChatGPT subscription: a 1-hour video spends a notable share of your limit",
      api: "Billed to your API account",
    } as Record<string, string>,
  },
};

export type Lang = keyof typeof TEXTS;
export type Words = (typeof TEXTS)[Lang];

/** Spanish for a Spanish browser, English for any other. */
export const browserLang = (): Lang => (navigator.language.toLowerCase().startsWith("es") ? "es" : "en");
