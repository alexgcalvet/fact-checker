"use strict";
(() => {
  // src/flags.ts
  var LABELS = {
    es: {
      ad_hominem: "Ad hominem",
      tu_quoque: "Y t\xFA m\xE1s",
      false_dilemma: "Falso dilema",
      straw_man: "Hombre de paja",
      false_cause: "Causa falsa",
      hasty_generalization: "Generalizaci\xF3n apresurada",
      vague_authority: "Autoridad vaga",
      insinuation: "Insinuaci\xF3n",
      double_standard: "Doble rasero",
      cherry_picking: "Datos a conveniencia",
      appeal_to_fear: "Apelaci\xF3n al miedo",
      false: "Dato falso",
      misleading: "Dato enga\xF1oso",
      disputed: "Dato discutido",
      definition_swap: "Cambio de m\xE9trica",
      plan_as_fact: "Plan contado como hecho",
      dodged: "Pregunta esquivada",
      partial: "Pregunta respondida a medias",
      self: "Contradicci\xF3n",
      record: "Contradice lo que dijo antes",
      promise: "Promesa incumplida",
      person: "Contexto",
      case: "Contexto",
      event: "Contexto"
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
      event: "Context"
    }
  };
  var NITPICK_NAME = { es: "Puntualizaci\xF3n", en: "Nitpick" };
  var SERIOUS_NAME = { es: "grave", en: "serious" };
  var HUES = {
    er: { text: "#F49A9C", marker: "#E5484D" },
    mi: { text: "#F0BE6A", marker: "#D99A2B" },
    rh: { text: "#E9A3CB", marker: "#D06BA8" },
    in: { text: "#9DB2D6", marker: "#5B8DE0" },
    ok: { text: "#7FD6C2", marker: "#29A98E" }
  };
  var GLYPHS = {
    er: "M-2.3 -2.3L2.3 2.3M2.3 -2.3L-2.3 2.3",
    mi: "M0 -3.1V0.6M0 2.7V2.8",
    rh: "M-3 0.9C-2 -1.5 -0.9 -1.3 0 0S2 1.5 3 -0.9",
    in: "M0 -2.9V-2.8M0 -0.6V3",
    ok: "M-2.8 0.1L-0.8 2.2L2.9 -2.1"
  };
  var TEXT_1 = "rgba(238,236,229,.95)";
  var TEXT_2 = "rgba(226,229,234,.6)";
  var GREY = "#5A6680";
  var disc = (fill, glyph) => `url("data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -8 16 16"><circle r="8" fill="${fill}" opacity=".1"/><circle r="7.2" fill="${fill}" opacity=".16"/><circle r="6.4" fill="${fill}" opacity=".3"/><circle r="5.6" fill="${fill}"/><circle r="3.4" fill="#FFF0D6" opacity=".22"/><path d="${glyph}" transform="scale(.92)" fill="none" stroke="#05070B" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round"/></svg>`
  )}")`;
  var verdictLook = (kind, family) => {
    const { marker, text } = HUES[kind];
    return { color: marker, dot: disc(marker, GLYPHS[kind]), word: text, mark: marker, family };
  };
  var FALSE = verdictLook("er", "Falsos");
  var MISLEADING = verdictLook("mi", "Falsos");
  var DISPUTED = { ...MISLEADING, word: TEXT_1 };
  var RHETORIC = verdictLook("rh", "Ret\xF3rica");
  var CONTRADICTION = { ...RHETORIC, dot: disc(HUES.rh.text, GLYPHS.rh), mark: HUES.rh.text };
  var CONTEXT = verdictLook("in", "Contexto");
  var NITPICK = { color: GREY, dot: disc(GREY, GLYPHS.mi), word: TEXT_2, mark: GREY, family: "Puntualizaciones" };
  var TYPE_LOOK = {
    inaccuracy: FALSE,
    fallacy: RHETORIC,
    question: RHETORIC,
    contradiction: CONTRADICTION,
    context: CONTEXT
  };
  var LABEL_LOOK = {
    misleading: MISLEADING,
    definition_swap: MISLEADING,
    plan_as_fact: MISLEADING,
    disputed: DISPUTED
  };
  var FAMILIES = [FALSE.family, RHETORIC.family, CONTEXT.family, NITPICK.family];
  var verdict = (f) => f.mark === "correct" ? void 0 : f.judge?.verdict;
  var look = (f) => verdict(f) === "nitpick" ? NITPICK : LABEL_LOOK[f.label] ?? TYPE_LOOK[f.type];
  var severity = (f) => verdict(f) === "nitpick" ? void 0 : f.judge?.severity;
  var title = (f, lang2 = "es") => verdict(f) === "nitpick" ? NITPICK_NAME[lang2] : (LABELS[lang2][f.label] ?? f.label) + (severity(f) === "serious" ? ` \xB7 ${SERIOUS_NAME[lang2]}` : "");

  // ../shared/feedback.ts
  var PRIVACY = "https://github.com/alexgcalvet/fact-checker/blob/main/PRIVACY.md";

  // src/texts.ts
  var AGENT_GUIDE = "https://github.com/alexgcalvet/fact-checker/blob/main/INSTALL-AGENT.md";
  var stopKind = (reason) => {
    const r = reason ?? "";
    if (r === "budget") return "budget";
    if (r.includes("yt-dlp")) return "captions";
    if (r.includes("speech engine")) return "speech";
    if (/claude -p|codex exec|API|is not set/.test(r)) return "provider";
    return "other";
  };
  var TEXTS = {
    es: {
      labels: LABELS.es,
      nitpick: NITPICK_NAME.es,
      serious: SERIOUS_NAME.es,
      families: { Falsos: "Falsos", Ret\u00F3rica: "Ret\xF3rica", Contexto: "Contexto", Puntualizaciones: "Puntualizaciones" },
      confidence: "Confianza",
      pin: "Fijar (P)",
      pinChip: "Fijar",
      close: "Cerrar",
      ask: "\xBFEs justo este aviso?",
      agree: "De acuerdo",
      disagree: "No",
      why: "\xBFPor qu\xE9? (opcional)",
      save: "Guardar",
      cancel: "Cancelar",
      markedCorrect: "Marcado: correcto",
      markedUnfair: "Marcado: injusto",
      youMarked: "Marcaste",
      change: "cambiar",
      before: "Antes",
      now: "Ahora",
      months: [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre"
      ],
      monthOf: (month2, year) => `${month2} de ${year}`,
      status: { met: "cumplida", "partly met": "cumplida a medias", "not met": "no cumplida", "in progress": "en curso" },
      promised: (made, figure, deadline, status) => `Prometido en ${made}: ${figure} para ${deadline} \xB7 Estado: ${status}`,
      controversy: "Pol\xE9mica",
      updated: "Dato actualizado",
      sources: (n) => `${n} ${n === 1 ? "fuente" : "fuentes"}`,
      details: "Detalles",
      panel: "Avisos",
      export: "Exportar resumen",
      settings: "Ajustes",
      keys: "Claves",
      all: "Todos",
      roles: { host: "Host", guest: "Invitada" },
      live: "Ir al directo",
      dropped: "Descartado por el juez",
      droppedAll: (n) => `Descartados por el juez (${n})`,
      size: "Texto",
      side: "Tarjetas",
      left: "izquierda",
      right: "derecha",
      quiet: "Solo graves",
      language: "Idioma",
      analyze: "Analizar este v\xEDdeo",
      preparing: "Preparando el an\xE1lisis\u2026",
      stopped: {
        captions: "YouTube no dio los subt\xEDtulos. Vuelve a intentarlo en unos minutos.",
        speech: "el v\xEDdeo no tiene subt\xEDtulos y este equipo no puede transcribir el audio. Ejecuta fact-checker doctor.",
        budget: "se lleg\xF3 al l\xEDmite de lecturas de este v\xEDdeo.",
        provider: "el modelo de IA no respondi\xF3. Vuelve a intentarlo o ejecuta fact-checker doctor.",
        other: "error inesperado. Vuelve a intentarlo o ejecuta fact-checker doctor."
      },
      stoppedLine: (why) => `El an\xE1lisis se par\xF3: ${why}`,
      shared: "An\xE1lisis compartido \xB7 gratis",
      helperDown: [
        "El ayudante de fact-checker no responde.",
        `\xBFNo lo has instalado, o falla? Dile a tu asistente de IA (Claude o ChatGPT): \xABInstala fact-checker siguiendo ${AGENT_GUIDE}\xBB`,
        "\xBFYa lo instalaste? Ejecuta fact-checker doctor en un terminal."
      ],
      sharing: {
        on: "Tus marcas se comparten con el autor para mejorar el detector \xB7 Desactivar en \u2699",
        off: "Tus marcas no se comparten \xB7 Activar en \u2699",
        toggle: "Compartir mis marcas y an\xE1lisis"
      },
      consent: {
        ask: "\xBFCompartir tus marcas y an\xE1lisis con el autor para mejorar el detector? Se env\xEDan el aviso, la frase, tu motivo y el v\xEDdeo; nada de tu equipo.",
        yes: "S\xED, compartir",
        no: "No",
        privacy: "Privacidad"
      },
      signals: "Se\xF1ales autom\xE1ticas, no veredictos",
      spend: {
        claude: "Usa tu suscripci\xF3n de Claude: un v\xEDdeo de 1 h gasta una parte notable de tu l\xEDmite",
        codex: "Usa tu suscripci\xF3n de ChatGPT: un v\xEDdeo de 1 h gasta una parte notable de tu l\xEDmite",
        api: "Se cobra en tu cuenta de API"
      }
    },
    en: {
      labels: LABELS.en,
      nitpick: NITPICK_NAME.en,
      serious: SERIOUS_NAME.en,
      families: { Falsos: "False", Ret\u00F3rica: "Rhetoric", Contexto: "Context", Puntualizaciones: "Nitpicks" },
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
      months: [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December"
      ],
      monthOf: (month2, year) => `${month2} ${year}`,
      status: { met: "kept", "partly met": "partly kept", "not met": "not kept", "in progress": "in progress" },
      promised: (made, figure, deadline, status) => `Promised in ${made}: ${figure} by ${deadline} \xB7 Status: ${status}`,
      controversy: "Controversy",
      updated: "Updated figure",
      sources: (n) => `${n} ${n === 1 ? "source" : "sources"}`,
      details: "Details",
      panel: "Flags",
      export: "Export summary",
      settings: "Settings",
      keys: "Keys",
      all: "All",
      roles: { host: "Host", guest: "Guest" },
      live: "Jump to now",
      dropped: "Dropped by the judge",
      droppedAll: (n) => `Dropped by the judge (${n})`,
      size: "Text",
      side: "Cards",
      left: "left",
      right: "right",
      quiet: "Serious only",
      language: "Language",
      analyze: "Analyze this video",
      preparing: "Preparing the analysis\u2026",
      stopped: {
        captions: "YouTube did not give the captions. Try again in a few minutes.",
        speech: "the video has no captions and this computer cannot transcribe the audio. Run fact-checker doctor.",
        budget: "it reached the reading limit of this video.",
        provider: "the AI model did not answer. Try again or run fact-checker doctor.",
        other: "unexpected error. Try again or run fact-checker doctor."
      },
      stoppedLine: (why) => `The analysis stopped: ${why}`,
      shared: "Shared analysis \xB7 free",
      helperDown: [
        "The fact-checker helper does not answer.",
        `Not installed, or broken? Tell your AI assistant (Claude or ChatGPT): "Install fact-checker by following ${AGENT_GUIDE}"`,
        "Already installed? Run fact-checker doctor in a terminal."
      ],
      sharing: {
        on: "Your marks are shared with the author to improve the detector \xB7 Turn off in \u2699",
        off: "Your marks are not shared \xB7 Turn on in \u2699",
        toggle: "Share my marks and analyses"
      },
      consent: {
        ask: "Share your marks and analyses with the author to improve the detector? The flag, the quote, your reason and the video are sent; nothing from your computer.",
        yes: "Yes, share",
        no: "No",
        privacy: "Privacy"
      },
      signals: "Automatic signals, not verdicts",
      spend: {
        claude: "Uses your Claude subscription: a 1-hour video spends a notable share of your limit",
        codex: "Uses your ChatGPT subscription: a 1-hour video spends a notable share of your limit",
        api: "Billed to your API account"
      }
    }
  };
  var browserLang = () => navigator.language.toLowerCase().startsWith("es") ? "es" : "en";

  // src/overlay.ts
  var ON_PLAYER = 0.8;
  var SHOW_FOR = 8;
  var READ_CHARS_PER_S = 15;
  var READ_MAX = 20;
  var LINGER = 3;
  var SHOWN_TYPES = ["fallacy", "inaccuracy", "question", "contradiction", "context"];
  var onPlayer = (f) => f.on_player ?? f.confidence >= ON_PLAYER;
  var settings = {
    size: "M",
    side: "right",
    quiet: false,
    lang: null
  };
  var ZOOM = { S: "0.85", M: "1", L: "1.25" };
  var QUIET = 0.9;
  var STYLE = `
.fc-layer{--t1:${TEXT_1};--t2:${TEXT_2};--t3:rgba(214,219,227,.55);--bone:#E6DCC4;--e:cubic-bezier(.2,.8,.2,1);
  font:450 13px/1.4 "Host Grotesk",system-ui,sans-serif;color:var(--t1);-webkit-font-smoothing:antialiased}
:where(.fc-layer) button{font:inherit;color:inherit;border:0;background:none;padding:0;cursor:pointer}
.fc-layer [hidden]{display:none !important}
.fc-s{box-sizing:border-box;position:relative;background:rgba(11,14,21,.8);backdrop-filter:blur(32px) saturate(.5);
  box-shadow:0 0 0 .5px rgba(255,255,255,.1),inset 0 .5px 0 rgba(255,255,255,.07),0 2px 4px rgba(0,0,0,.18),0 12px 32px -8px rgba(0,0,0,.55)}
.fc-s::before{content:"";position:absolute;left:12%;right:0;top:0;height:1px;pointer-events:none;
  background:linear-gradient(90deg,rgba(255,255,255,0),rgba(255,247,230,.32) 78%,rgba(255,255,255,0))}
.fc-ic{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
.fc-dot{width:16px;height:16px;flex-shrink:0;background:no-repeat center/16px 16px}
.fc-num,.fc-m{font-variant-numeric:tabular-nums}
.fc-m{color:var(--t3)}
.fc-fact{width:360px;margin-top:8px;padding:14px 16px 12px;border-radius:14px;pointer-events:auto;flex:0 1 auto;min-height:0;overflow-y:auto;scrollbar-width:thin;overscroll-behavior:contain}
.fc-hd{display:flex;align-items:center;gap:8px;min-height:22px}
.fc-hd b{font-weight:550}
.fc-conf{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--t2);white-space:nowrap}
.fc-slats{display:flex;gap:2px}
.fc-slats i{width:6px;height:12px;background:rgba(255,255,255,.2);clip-path:polygon(3.5px 0,100% 0,2.5px 100%,0 100%)}
.fc-row .fc-slats i{width:5px;height:10px;clip-path:polygon(2.5px 0,100% 0,1.5px 100%,0 100%)}
.fc-ibs{display:flex;gap:2px;margin:0 -6px 0 6px}
.fc-ib{width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:7px;font-size:15px;color:var(--t3)}
.fc-ib:hover,.fc-ib.on{color:var(--t1);background:rgba(255,255,255,.07)}
.fc-fault{position:relative;height:6px;margin:12px -16px 0;pointer-events:none}
.fc-fault i{position:absolute;height:1px}
.fc-fault i:nth-child(1){left:0;top:5px;width:104px;transform-origin:100% 0;background:linear-gradient(90deg,rgba(255,247,230,0),rgba(255,247,230,.22))}
.fc-fault i:nth-child(2){left:104px;top:5px;width:7.07px;transform-origin:0 0;transform:rotate(-45deg);background:rgba(255,247,230,.42)}
.fc-fault i:nth-child(3){left:109px;right:0;top:0;transform-origin:0 0;background:linear-gradient(90deg,rgba(255,247,230,.42),rgba(255,247,230,.12))}
.fc-enter{animation:fc-enter 240ms var(--e) both}
.fc-enter .fc-fault i:nth-child(odd){animation:fc-draw 320ms var(--e) 240ms both}
@keyframes fc-enter{from{opacity:0;filter:blur(4px);transform:translateY(4px)}}
@keyframes fc-draw{from{transform:scaleX(0)}}
.fc-who{margin-top:12px;font-size:12.5px;color:var(--t3)}
.fc-q{margin-top:4px;font-size:15px;line-height:1.47;color:var(--bone)}
.fc-was{margin-top:4px;line-height:1.47;color:var(--t2)}
.fc-was a,.fc-ft a{color:var(--t1)}
.fc-bd{margin-top:10px;line-height:1.6;color:var(--t2)}
.fc-ft{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px;font-size:12.5px;color:var(--t2)}
.fc-ft summary{display:inline-flex;align-items:center;gap:6px;cursor:pointer;list-style:none}
.fc-ft summary::-webkit-details-marker{display:none}
.fc-ft summary .fc-ic{width:13px;height:13px;color:var(--t3)}
.fc-ft details[open]{order:1;flex-basis:100%}
.fc-ft details div{margin-top:6px;line-height:1.5}
.fc-ref a{color:var(--t1);text-decoration:underline;text-decoration-color:rgba(255,255,255,.3);text-underline-offset:2px}
.fc-ref .fc-ic{display:inline-block;width:11px;height:11px;margin-left:2px;vertical-align:-1px;color:var(--t3)}
.fc-marks{display:flex;flex-basis:100%;order:2;align-items:center;gap:8px;margin-top:2px;padding-top:12px;
  border-top:.5px solid rgba(255,255,255,.08);white-space:nowrap}
.fc-ask{margin-right:auto;font-size:13px;font-weight:550;color:var(--t1)}
.fc-btn{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 10px;border-radius:8px;font-size:12.5px;
  color:var(--t2);box-shadow:0 0 0 .5px rgba(255,255,255,.12)}
.fc-btn:hover,.fc-btn.on{color:var(--t1);background:rgba(255,255,255,.08);
  box-shadow:0 0 0 .5px rgba(255,255,255,.16),inset 0 .5px 0 rgba(255,255,255,.08)}
.fc-vote{display:inline-flex;align-items:center;gap:7px;height:34px;padding:0 14px;border-radius:10px;font-size:13.5px;
  font-weight:550;color:var(--t1);background:rgba(255,255,255,.07);transition:background .15s,box-shadow .15s}
.fc-vote:hover{background:rgba(255,255,255,.12)}
.fc-yes:hover{box-shadow:0 0 0 1px rgba(127,214,194,.45),inset 0 .5px 0 rgba(255,255,255,.1)}
.fc-no:hover{box-shadow:0 0 0 1px rgba(244,154,156,.45),inset 0 .5px 0 rgba(255,255,255,.1)}
.fc-marks input{flex:1;min-width:0;height:26px;padding:0 8px;border:0;border-radius:8px;outline:none;font:inherit;color:var(--t1);
  background:rgba(255,255,255,.06);box-shadow:0 0 0 .5px rgba(255,255,255,.16)}
.fc-link{text-decoration:underline}
.fc-nit{padding:10px 14px 10px;border:.5px solid;font-size:12px}
.fc-nit .fc-q{font-size:13px}
.fc-nit .fc-fault{margin:10px -14px 0}
.fc-chip{display:flex;align-items:center;gap:9px;width:max-content;max-width:520px;margin-top:8px;padding:8px 14px 8px 12px;font-size:13px;border-radius:10px;overflow:hidden;pointer-events:auto;cursor:pointer}
.fc-chip:hover .fc-life{animation-play-state:paused}
.fc-chip .fc-k{white-space:nowrap}
.fc-life{position:absolute;left:14px;right:14px;bottom:0;height:1px;transform-origin:0 0;animation:fc-life linear both;
  background:linear-gradient(90deg,rgba(255,247,230,0),rgba(255,247,230,.4))}
@keyframes fc-life{to{transform:scaleX(0)}}
.fc-tog{display:inline-flex;align-items:center;gap:8px;height:30px;padding:0 11px;border-radius:10px;font-size:12.5px;color:var(--t2);pointer-events:auto}
.fc-tog:hover{color:var(--t1)}
.fc-tog .fc-n{color:var(--t3)}
.fc-panel{position:absolute;right:12px;top:12px;bottom:112px;width:372px;display:flex;flex-direction:column;border-radius:14px;overflow:hidden;pointer-events:auto}
.fc-fh{padding:14px 16px 0}
.fc-t{display:flex;align-items:center;gap:8px;height:24px;font-size:14px;font-weight:550}
.fc-cnt{display:inline-flex;align-items:center;height:18px;padding:0 6px;border-radius:5px;background:rgba(255,255,255,.08);font-size:11.5px;font-weight:450}
.fc-t .fc-btn{margin-left:auto;height:24px;font-weight:450;font-size:12px}
.fc-t .fc-ib{font-weight:450}
.fc-t .fc-ib:last-child{margin-right:-6px}
.fc-flt{display:flex;flex-wrap:wrap;gap:2px;margin:12px 0 0 -4px}
.fc-flt button{display:inline-flex;align-items:center;gap:5px;height:26px;padding:0 9px;border-radius:999px;font-size:12px;color:var(--t2)}
.fc-flt button.on{color:var(--t1);background:rgba(255,255,255,.08);box-shadow:0 0 0 .5px rgba(255,255,255,.12),inset 0 .5px 0 rgba(255,255,255,.08)}
.fc-n{color:var(--t2);font-size:12px}
.fc-people{margin:10px 0 0;font-size:12px;color:var(--t2)}
.fc-people button{padding:0 4px;color:var(--t1);text-decoration:underline dotted}
.fc-flt .fc-dot{width:14px;height:14px;background-size:14px 14px}
.fc-panel .fc-fault{margin:12px 0 0;flex-shrink:0}
.fc-list{position:relative;flex:1;overflow-y:auto;padding:4px 8px 8px;scrollbar-width:none;
  mask-image:linear-gradient(to bottom,transparent,#000 56px,#000 calc(100% - 24px),transparent)}
.fc-row{padding:9px 10px;border-radius:10px;cursor:pointer}
.fc-row:hover{background:rgba(255,255,255,.04)}
.fc-rh{display:flex;align-items:center;gap:7px;min-height:18px;font-size:12px}
.fc-rh b{font-weight:550}
.fc-rq{margin-top:4px;padding-left:13px;line-height:1.45;color:var(--t2)}
/* A context entity takes one line: it does not compete with the claims. */
.fc-one{display:flex;align-items:center;gap:7px;padding:6px 10px;font-size:12px}
.fc-one .fc-e{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12.5px}
.fc-nowtag{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--t3)}
.fc-live{width:6px;height:6px;border-radius:50%;background:#ECE9E1;animation:fc-pulse 2.4s ease-in-out infinite}
@keyframes fc-pulse{50%{opacity:.35}}
.fc-x{margin-top:8px;padding-left:13px;font-size:12.5px;line-height:1.55;color:var(--t2)}
.fc-rft{display:flex;align-items:center;gap:6px;margin-top:8px;padding-left:13px;font-size:12px;color:var(--t2)}
.fc-rft a{display:inline-flex;align-items:center;gap:6px;color:inherit;text-decoration:none}
.fc-rft .fc-ic{width:12px;height:12px;color:var(--t3)}
.fc-rft .fc-conf{color:var(--t3)}
.fc-jump{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);display:inline-flex;align-items:center;gap:7px;
  height:28px;padding:0 12px;border-radius:999px;font-size:12px;white-space:nowrap}
.fc-jump .fc-ic{width:13px;height:13px}
.fc-why{margin-top:4px;padding-left:13px;font-size:12px;color:var(--t3)}
.fc-one{flex-wrap:wrap}
.fc-one .fc-why{flex-basis:100%;margin-top:0;padding-left:23px}
.fc-past{opacity:.72}
.fc-dropped{margin-top:6px}
.fc-dropped summary{padding:8px 10px;font-size:12px;color:var(--t3);cursor:pointer}
.fc-now{background:rgba(255,255,255,.055);box-shadow:inset 0 .5px 0 rgba(255,255,255,.08),0 0 0 .5px rgba(255,255,255,.08)}
.fc-now .fc-rq{color:var(--bone)}
.fc-settings{margin-top:10px;padding:8px 10px;border-radius:10px;background:rgba(255,255,255,.04);font-size:12px;color:var(--t2)}
.fc-settings>div,.fc-settings label{display:flex;align-items:center;gap:4px;margin-bottom:6px}
.fc-settings>div>span{width:60px}
.fc-settings .fc-btn{height:22px;padding:0 8px}
.fc-strip{position:absolute;left:12px;right:12px;bottom:52px;height:18px}
.fc-analysed,.fc-pending{position:absolute;top:7.5px;height:3px;border-radius:2px;background:rgba(255,255,255,.16)}
.fc-pending{background:rgba(255,255,255,.07)}
.fc-done .fc-analysed{background:none}
.fc-tip{position:absolute;bottom:22px;transform:translateX(-50%);display:inline-flex;align-items:center;gap:8px;height:28px;
  padding:0 10px;border-radius:10px;font-size:12.5px;white-space:nowrap}
.fc-tip .fc-m{color:var(--t3)}
.fc-mark{position:absolute;top:50%;transform:translate(-50%,-50%);border-radius:50%;background:no-repeat center/16px 16px;
  box-shadow:0 0 0 1.5px rgba(10,14,21,.7);cursor:pointer;pointer-events:auto}
/* Like YouTube's own bar, the strip and the Avisos button show only while the player shows its controls. */
.fc-strip,.fc-panel-tab{transition:opacity .25s}
.ytp-autohide .fc-strip,.ytp-autohide .fc-panel-tab{opacity:0;pointer-events:none}
@media (prefers-reduced-motion:reduce){.fc-layer *{animation:none !important;transition:none !important}}
`;
  var ICONS = {
    pin: "M6 2.5h4M7 2.5v4L4.5 9h7L9 6.5v-4M8 9v4.5",
    x: "M4.5 4.5l7 7M11.5 4.5l-7 7",
    arrow: "M5 11l6-6M6 5h5v5",
    down: "M8 3v9.5M4 8.5l4 4 4-4"
  };
  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 16 16");
    svg.setAttribute("class", "fc-ic");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", ICONS[name]);
    svg.append(path);
    return svg;
  }
  var lang = () => settings.lang ?? browserLang();
  var words = () => TEXTS[lang()];
  function setSettings(change, layer) {
    Object.assign(settings, change);
    try {
      chrome.storage.local.set({ settings }).catch(() => {
      });
    } catch {
    }
    layer.dispatchEvent(new Event("fc-settings"));
  }
  var seconds = (f) => f.type === "context" ? Math.min(READ_MAX, Math.max(SHOW_FOR, (f.quote.length + f.reason.length) / READ_CHARS_PER_S)) : SHOW_FOR;
  var loud = (f) => {
    if (verdict(f) === "nitpick") return false;
    const rated = severity(f);
    return rated ? rated === "serious" : f.confidence >= QUIET;
  };
  var shows = (f) => SHOWN_TYPES.includes(f.type) && onPlayer(f) && verdict(f) !== "drop" && (!settings.quiet || loud(f));
  function button(text, onClick, className = "fc-btn") {
    const b = document.createElement("button");
    b.className = className;
    b.textContent = text;
    b.addEventListener("click", onClick);
    return b;
  }
  function div(className, text) {
    const el = document.createElement("div");
    el.className = className;
    if (text !== void 0) el.textContent = text;
    return el;
  }
  function span(className, text) {
    const el = document.createElement("span");
    el.className = className;
    if (text !== void 0) el.textContent = text;
    return el;
  }
  function dot(l) {
    const el = span("fc-dot");
    el.style.backgroundImage = l.dot;
    return el;
  }
  function confidence(flag, l) {
    const percent = `${Math.round(flag.confidence * 100)}%`;
    const el = span("fc-conf fc-num");
    el.title = `${words().confidence} ${percent}`;
    const slats = span("fc-slats");
    const lit = Math.round(flag.confidence * 5);
    for (let i = 0; i < 5; i++) {
      const slat = document.createElement("i");
      if (i < lit) slat.style.background = l.color;
      slats.append(slat);
    }
    el.append(slats, percent);
    return el;
  }
  var fault = () => {
    const el = div("fc-fault");
    el.append(document.createElement("i"), document.createElement("i"), document.createElement("i"));
    return el;
  };
  function marks(flag, onMark, video) {
    const w = words();
    const row = div("fc-marks");
    const done = (text) => row.replaceChildren(span("", text));
    const unfair = () => {
      const playing = !video.paused;
      if (playing) video.pause();
      const resume = () => {
        if (playing) video.play();
      };
      const input = document.createElement("input");
      input.placeholder = w.why;
      const save = () => {
        onMark(flag, "unfair", input.value);
        done(w.markedUnfair);
        resume();
      };
      const cancel = () => {
        ask();
        resume();
      };
      for (const type of ["keydown", "keypress", "keyup"]) {
        input.addEventListener(type, (e) => {
          e.stopPropagation();
          if (type !== "keydown") return;
          if (e.key === "Enter") save();
          if (e.key === "Escape") cancel();
        });
      }
      row.replaceChildren(input, button(w.save, save), button(w.cancel, cancel));
      input.focus();
    };
    const vote = (glyph, color, text, className, onClick) => {
      const b = button("", onClick, `fc-vote fc-s ${className}`);
      const sign = span("", glyph);
      sign.style.color = color;
      b.append(sign, ` ${text}`);
      return b;
    };
    const ask = () => row.replaceChildren(
      span("fc-ask", w.ask),
      vote("\u2713", HUES.ok.text, w.agree, "fc-yes", () => {
        onMark(flag, "correct", "");
        done(w.markedCorrect);
      }),
      vote("\u2717", HUES.er.text, w.disagree, "fc-no", unfair)
    );
    if (flag.mark) {
      row.replaceChildren(
        `${w.youMarked}: ${flag.mark === "correct" ? `\u2713 ${w.agree}` : `\u2717 ${w.disagree}`}`,
        button(w.change, ask, "fc-link")
      );
    } else {
      ask();
    }
    return row;
  }
  function minute(t) {
    const s = Math.floor(t);
    const two = (n) => String(n).padStart(2, "0");
    const h = Math.floor(s / 3600);
    return h ? `${h}:${two(Math.floor(s / 60) % 60)}:${two(s % 60)}` : `${Math.floor(s / 60)}:${two(s % 60)}`;
  }
  function month(made, w) {
    const [year, m] = made.split("-");
    return m ? w.monthOf(w.months[Number(m) - 1], year) : year;
  }
  function details(flag) {
    const w = words();
    const lines = [];
    const used = /* @__PURE__ */ new Set();
    const outlet = (publisher) => publisher.split(" (")[0].trim().toLowerCase();
    const link = (s) => Object.assign(document.createElement("a"), {
      href: s.url,
      target: "_blank",
      rel: "noopener",
      textContent: s.publisher,
      title: s.date
    });
    const line = (text) => {
      const ref = div("fc-ref", text);
      for (const s of flag.sources) {
        if (!text.toLowerCase().includes(outlet(s.publisher))) continue;
        ref.append(" ", link(s), icon("arrow"));
        used.add(s.url);
      }
      lines.push(ref);
    };
    if (flag.promise) {
      const p = flag.promise;
      line(w.promised(month(p.made, w), p.figure, p.deadline, w.status[p.status]));
    }
    for (const m of flag.measures ?? []) line(`${m.name}: ${m.value} (${m.source})`);
    if (flag.controversy) line(`${w.controversy}: ${flag.controversy}`);
    if (flag.note) line(`${w.updated}: ${flag.note}`);
    for (const s of flag.sources) {
      if (used.has(s.url)) continue;
      const ref = div("fc-ref");
      ref.append(link(s), ` \xB7 ${s.date}`, icon("arrow"));
      lines.push(ref);
    }
    if (!lines.length) return null;
    const box = document.createElement("details");
    const summary = document.createElement("summary");
    const n = flag.sources.length;
    summary.append(n ? w.sources(n) : w.details, icon("arrow"));
    box.append(summary, ...lines);
    return box;
  }
  function card(flag, video, pinned, pin, close, onMark) {
    const w = words();
    const l = look(flag);
    const el = div("fc-card fc-s fc-fact");
    const head = div("fc-hd");
    const name = document.createElement("b");
    name.textContent = title(flag, lang());
    name.style.color = l.word;
    const pinButton = button("", pin, `fc-ib fc-pin${pinned ? " on" : ""}`);
    pinButton.append(icon("pin"));
    pinButton.dataset.pinned = String(pinned);
    pinButton.title = pinned ? w.close : w.pin;
    const closeButton = button("", close, "fc-ib fc-close");
    closeButton.append(icon("x"));
    closeButton.title = w.close;
    const icons = span("fc-ibs");
    icons.append(pinButton, closeButton);
    head.append(name, span("fc-m", minute(flag.t)), confidence(flag, l), icons);
    el.append(head, fault());
    const nitpick = verdict(flag) === "nitpick";
    if (nitpick) {
      el.classList.add("fc-nit");
      el.style.borderColor = "rgba(226,231,238,.22)";
    }
    const speaker = flag.judge?.speaker ?? flag.speaker;
    if (speaker) el.append(div("fc-who", speaker));
    const quote = div("fc-q", `\xAB${flag.type === "question" && flag.related ? flag.related.quote : flag.quote}\xBB`);
    if (flag.type === "contradiction" && flag.related) {
      const { t, quote: said, date, source } = flag.related;
      const earlier = div("fc-was");
      if (t === null && source) {
        const link = Object.assign(document.createElement("a"), { href: source.url, target: "_blank", textContent: source.publisher });
        earlier.append(`${w.before} (${date}, `, link, `): \xAB${said}\xBB`);
      } else {
        earlier.textContent = `${w.before} (${minute(t)}): \xAB${said}\xBB`;
      }
      quote.textContent = `${w.now}: ${quote.textContent}`;
      el.append(earlier);
    }
    el.append(quote, div("fc-bd", nitpick ? flag.judge.reason : flag.reason));
    const foot = div("fc-ft");
    const more = details(flag);
    if (more) foot.append(more);
    if (onMark) foot.append(marks(flag, onMark, video));
    if (foot.childElementCount) el.append(foot);
    return el;
  }
  function chip(flag, left) {
    const el = div("fc-card fc-pill fc-s fc-chip");
    const l = look(flag);
    const kind = span("fc-k", words().labels[flag.label] ?? flag.label);
    kind.style.color = l.word;
    el.append(dot(l), kind, span("", `${flag.quote} \u2014 ${flag.reason}`));
    if (left !== null) {
      const life = span("fc-life");
      life.style.animationDuration = `${left}s`;
      el.append(life);
    }
    return el;
  }
  function mountOverlay(player, video, getFlags, onMark) {
    const layer = document.createElement("div");
    layer.className = "fc-layer";
    layer.style.cssText = "position:absolute;inset:0;z-index:60;pointer-events:none";
    const style = document.createElement("style");
    style.textContent = STYLE;
    const cards = document.createElement("div");
    cards.style.cssText = "position:absolute;top:12px;bottom:72px;display:flex;flex-direction:column";
    const pills = document.createElement("div");
    pills.style.cssText = "position:absolute;left:12px;bottom:72px";
    layer.append(style, cards, pills);
    player.appendChild(layer);
    const fit = () => {
      const p = player.getBoundingClientRect(), v = video.getBoundingClientRect();
      const ratio = video.videoWidth / video.videoHeight;
      if (!ratio || !v.width) return;
      const w = Math.min(v.width, v.height * ratio), h = w / ratio;
      Object.assign(layer.style, {
        inset: "auto",
        left: `${v.left - p.left + (v.width - w) / 2}px`,
        top: `${v.top - p.top + (v.height - h) / 2}px`,
        width: `${w}px`,
        height: `${h}px`
      });
    };
    const resized = new ResizeObserver(fit);
    resized.observe(player);
    video.addEventListener("loadedmetadata", fit);
    fit();
    const shown = { cards: "", pills: "" };
    let before = /* @__PURE__ */ new Set();
    const pinned = /* @__PURE__ */ new Set();
    const closed = /* @__PURE__ */ new Set();
    const held = /* @__PURE__ */ new Set();
    const lingerUntil = /* @__PURE__ */ new Map();
    const hold = (box, linger) => {
      box.addEventListener("pointerenter", () => {
        for (const el of box.children) held.add(el.dataset.id);
      });
      box.addEventListener("pointerleave", () => {
        for (const id of held) lingerUntil.set(id, video.currentTime + linger);
        held.clear();
        draw();
      });
    };
    hold(cards, 0);
    hold(pills, LINGER);
    const toggle = (flag) => {
      if (pinned.delete(flag.id)) {
        closed.add(flag.id);
        held.delete(flag.id);
      } else {
        pinned.add(flag.id);
      }
      draw();
    };
    const close = (flag) => {
      pinned.delete(flag.id);
      held.delete(flag.id);
      closed.add(flag.id);
      draw();
    };
    const draw = () => {
      cards.style.zoom = pills.style.zoom = ZOOM[settings.size];
      const side = layer.classList.contains("fc-panel-open") ? "left" : settings.side;
      cards.style.left = side === "left" ? "12px" : "";
      cards.style.right = side === "right" ? "12px" : "";
      const now = video.currentTime;
      const flags = getFlags()?.flags ?? [];
      const due = (f) => shows(f) && f.t <= now && now < f.t + seconds(f);
      for (const id of closed) if (!flags.some((f) => f.id === id && due(f))) closed.delete(id);
      const visible = flags.filter((f) => pinned.has(f.id) || held.has(f.id) || now < (lingerUntil.get(f.id) ?? 0) || due(f) && !closed.has(f.id)).sort((a, b) => a.t - b.t);
      const key = (fs) => lang() + fs.map((f) => `${f.id}${pinned.has(f.id) ? "*" : ""}`).join("|");
      const facts = visible.filter((f) => f.type !== "context");
      const chips = visible.filter((f) => f.type === "context");
      const enter = (f, el) => {
        if (!before.has(f.id)) el.classList.add("fc-enter");
        el.dataset.id = f.id;
        return el;
      };
      const cardsHeld = facts.some((f) => held.has(f.id));
      if (!cardsHeld && key(facts) !== shown.cards) {
        shown.cards = key(facts);
        cards.replaceChildren(...facts.map((f) => enter(f, card(f, video, pinned.has(f.id), () => toggle(f), () => close(f), onMark))));
      }
      if (key(chips) !== shown.pills) {
        shown.pills = key(chips);
        pills.replaceChildren(...chips.map((f) => {
          const el = enter(f, chip(f, pinned.has(f.id) ? null : Math.max(f.t + seconds(f) - now, LINGER)));
          el.title = pinned.has(f.id) ? words().close : words().pinChip;
          el.addEventListener("click", () => toggle(f));
          return el;
        }));
      }
      before = new Set(visible.map((f) => f.id));
    };
    const render = () => draw();
    try {
      chrome.storage.local.get("settings").then((stored) => {
        Object.assign(settings, stored.settings);
        layer.dispatchEvent(new Event("fc-settings"));
      }, () => {
      });
    } catch {
    }
    layer.addEventListener("fc-settings", draw);
    layer.addEventListener("fc-flags", draw);
    video.addEventListener("timeupdate", render);
    video.addEventListener("seeked", render);
    draw();
    return {
      layer,
      show: (flag) => {
        pinned.add(flag.id);
        closed.delete(flag.id);
        draw();
      },
      unmount: () => {
        video.removeEventListener("timeupdate", render);
        video.removeEventListener("seeked", render);
        video.removeEventListener("loadedmetadata", fit);
        resized.disconnect();
        layer.remove();
      }
    };
  }

  // ../shared/panel.ts
  var inOrder = (flags) => [...flags].sort((a, b) => a.t - b.t);
  var litAt = (flags, now) => flags.filter((f) => f.t <= now).pop();

  // src/panel.ts
  var HEADS_UP = 2;
  var STRIP_MIDDLE = 9;
  var TYPE_COLOR = Object.fromEntries(Object.entries(TYPE_LOOK).map(([type, l]) => [type, l.mark]));
  function mountPanel(layer, video, getFlags, show, exportSummary = () => {
  }, sharing, setRole = () => {
  }, openKeys = () => {
  }) {
    const strip = div("fc-strip");
    const tip = div("fc-tip fc-s");
    tip.hidden = true;
    const tab = document.createElement("button");
    tab.className = "fc-panel-tab fc-s fc-tog";
    tab.style.cssText = "position:absolute;right:12px;bottom:72px";
    const panel = div("fc-panel fc-s");
    panel.style.display = "none";
    const stopped = div("fc-stopped fc-s");
    stopped.style.cssText = "position:absolute;left:12px;top:56px;max-width:380px;padding:10px 12px;border-radius:10px;font-size:12.5px;line-height:1.5;color:var(--t1);pointer-events:auto";
    const share = div("fc-share fc-m");
    share.style.cssText = "padding:10px 16px;font-size:12px;border-top:.5px solid rgba(255,255,255,.08)";
    let shared = null;
    const shown = (on) => {
      shared = on;
      share.hidden = on === null;
      share.textContent = on === null ? "" : on ? words().sharing.on : words().sharing.off;
      if (box.style.display !== "none") drawBox();
    };
    const ask = async () => shown(await sharing?.get() ?? null);
    const setOpen = (open) => {
      if (open) ask();
      panel.style.display = open ? "" : "none";
      layer.classList.toggle("fc-panel-open", open);
      layer.dispatchEvent(new Event("fc-settings"));
    };
    tab.addEventListener("click", () => setOpen(panel.style.display === "none"));
    layer.prepend(strip, panel, tab);
    const size = () => {
      panel.style.zoom = ZOOM[settings.size];
    };
    layer.addEventListener("fc-settings", size);
    size();
    const jump = (flag) => {
      video.currentTime = flag.t;
      show(flag);
    };
    const box = div("fc-settings");
    box.style.display = "none";
    const drawBox = () => {
      const w = words();
      const choice = (label, key, options) => {
        const line = div("");
        line.append(span("", label), ...options.map(([value, text]) => {
          const b = button(text, () => change({ [key]: value }));
          if ((key === "lang" ? lang() : settings[key]) === value) b.classList.add("on");
          return b;
        }));
        return line;
      };
      const quiet = document.createElement("label");
      const check = Object.assign(document.createElement("input"), { type: "checkbox", checked: settings.quiet });
      check.addEventListener("change", () => change({ quiet: check.checked }));
      quiet.append(check, ` ${w.quiet}`);
      box.replaceChildren(
        choice(w.size, "size", [["S", "S"], ["M", "M"], ["L", "L"]]),
        choice(w.side, "side", [["left", w.left], ["right", w.right]]),
        quiet,
        choice(w.language, "lang", Object.keys(TEXTS).map((l) => [l, l.toUpperCase()])),
        button(w.keys, openKeys)
      );
      if (sharing && shared !== null) {
        const line = document.createElement("label");
        const on = Object.assign(document.createElement("input"), { type: "checkbox", checked: shared });
        on.addEventListener("change", async () => shown(await sharing.set(on.checked) ?? shared));
        line.append(on, ` ${w.sharing.toggle}`);
        box.append(line);
      }
    };
    const change = (c) => {
      setSettings(c, layer);
      drawBox();
    };
    const list = div("fc-list");
    const feed = div("fc-feed");
    feed.style.cssText = "position:relative;flex:1;min-height:0;display:flex;flex-direction:column";
    let following = true;
    const live = button("", () => {
      following = true;
      live.hidden = true;
      scrollToNow();
    }, "fc-jump fc-s");
    live.hidden = true;
    for (const type of ["wheel", "touchmove"]) {
      list.addEventListener(type, () => {
        following = false;
        live.hidden = false;
      }, { passive: true });
    }
    feed.append(list, live);
    let only = null;
    let marks2 = [];
    let rows = [];
    let drawn = "";
    let seen = /* @__PURE__ */ new Set();
    let lit;
    let litParts = [];
    const scrollToNow = () => {
      const row = rows.find(([f]) => f === lit)?.[1];
      if (row) list.scrollTop = row.offsetTop - list.clientHeight / 3;
    };
    const render = () => {
      const file = getFlags();
      const flags = inOrder((file?.flags ?? []).filter((f) => SHOWN_TYPES.includes(f.type)));
      const analysed = file?.status === "done" ? 100 : Math.min(100, (file?.analysed_until ?? 0) / video.duration * 100);
      const preparing = file?.status === "running" && file.first_flags_s === void 0;
      const stop = file?.status === "stopped" ? file.stop_reason : void 0;
      const people = Object.entries(file?.people ?? {});
      const key = `${lang()}|${video.duration}|${analysed}|${only}|${preparing}|${stop}|${flags.map((f) => f.id).join("|")}|` + people.map(([name, p]) => `${name}:${p.role}`).join("|");
      if (key === drawn) return;
      drawn = key;
      const w = words();
      const standing = flags.filter((f) => verdict(f) !== "drop");
      if (preparing) tab.replaceChildren(w.preparing);
      else tab.replaceChildren(`${w.panel} `, span("fc-n", `(${standing.length})`));
      if (stop === void 0) stopped.remove();
      else {
        stopped.textContent = w.stoppedLine(w.stopped[stopKind(stop)]);
        layer.append(stopped);
      }
      marks2 = video.duration > 0 ? flags.map((f) => {
        const mark = div("fc-mark");
        mark.addEventListener("pointerenter", () => {
          tip.replaceChildren(dot(look(f)), span("fc-m fc-num", minute(f.t)), title(f, lang()));
          tip.style.left = mark.style.left;
          tip.hidden = false;
        });
        mark.addEventListener("pointerleave", () => {
          tip.hidden = true;
        });
        mark.style.left = `${f.t / video.duration * 100}%`;
        const full = onPlayer(f) && verdict(f) !== "drop";
        mark.style.width = mark.style.height = full ? "12px" : "6px";
        mark.style.backgroundColor = look(f).mark;
        if (full) mark.style.backgroundImage = look(f).dot;
        mark.addEventListener("click", () => jump(f));
        return [f, mark];
      }) : [];
      const part = (className, left, width) => {
        const el = div(className);
        el.style.left = `${left}%`;
        el.style.width = `${width}%`;
        return el;
      };
      const parts = video.duration > 0 ? [part("fc-analysed", 0, analysed), part("fc-pending", analysed, 100 - analysed)] : [];
      strip.replaceChildren(...parts, ...marks2.map(([, mark]) => mark), tip);
      strip.classList.toggle("fc-done", analysed >= 100);
      const head = div("fc-t");
      const gear = button("\u2699", () => {
        box.style.display = box.style.display === "none" ? "" : "none";
        drawBox();
      }, "fc-ib");
      gear.title = w.settings;
      const close = button("", () => setOpen(false), "fc-ib");
      close.append(icon("x"));
      close.title = w.close;
      head.append(w.panel, span("fc-cnt fc-num", String(standing.length)), button(w.export, exportSummary), gear, close);
      const filters = div("fc-flt");
      const filter = (family, ...content) => {
        const b = button("", () => {
          only = only === family ? null : family;
          render();
        }, only === family ? "on" : "");
        b.append(...content);
        filters.append(b);
      };
      filter(null, w.all);
      for (const family of FAMILIES) {
        const of = standing.filter((f) => look(f).family === family);
        if (of.length) filter(family, dot(look(of[0])), w.families[family], span("fc-n fc-num", String(of.length)));
      }
      const top = div("fc-fh");
      top.append(head, box, filters);
      if (people.length) {
        const list2 = div("fc-people");
        for (const [name, p] of people) {
          const line = div("");
          line.append(span("", p.person), " \xB7 ", button(w.roles[p.role], () => {
            p.role = p.role === "host" ? "guest" : "host";
            p.set_by = "person";
            setRole(name, p.role);
            render();
          }, ""));
          list2.append(line);
        }
        top.append(list2);
      }
      rows = flags.filter((f) => !only || look(f).family === only).map((f) => {
        const l = look(f);
        const row = div("fc-row");
        if (seen.size && !seen.has(f.id)) row.classList.add("fc-enter");
        const dropped2 = verdict(f) === "drop";
        if (!onPlayer(f) || dropped2) row.style.opacity = "0.5";
        let struck;
        if (f.type === "context") {
          row.classList.add("fc-one");
          row.title = f.reason;
          const entity = span("fc-e", f.quote);
          row.append(dot(l), span("fc-m fc-num", minute(f.t)), entity);
          struck = [entity];
        } else {
          const line = div("fc-rh");
          const word = document.createElement("b");
          word.textContent = title(f, lang());
          word.style.color = l.word;
          line.append(dot(l), word, span("fc-m fc-num", minute(f.t)));
          const quote = div("fc-rq", `\xAB${f.quote}\xBB`);
          row.append(line, quote);
          struck = [line, quote];
        }
        if (dropped2) {
          for (const el of struck) el.style.textDecoration = "line-through";
          row.append(div("fc-why", `${w.dropped}: ${f.judge.reason}`));
        }
        row.addEventListener("click", () => {
          following = true;
          live.hidden = true;
          jump(f);
        });
        return [f, row];
      });
      seen = new Set(flags.map((f) => f.id));
      lit = void 0;
      litParts = [];
      live.replaceChildren(icon("down"), w.live);
      const dropped = rows.filter(([f]) => verdict(f) === "drop");
      list.replaceChildren(...rows.filter(([f]) => verdict(f) !== "drop").map(([, row]) => row));
      if (dropped.length) {
        const folded = document.createElement("details");
        folded.className = "fc-dropped";
        const summary = document.createElement("summary");
        summary.textContent = w.droppedAll(dropped.length);
        folded.append(summary, ...dropped.map(([, row]) => row));
        list.append(folded);
      }
      const signals = div("fc-signals fc-m", w.signals);
      signals.style.cssText = "padding:8px 16px 0;font-size:12px";
      panel.replaceChildren(top, fault(), feed, signals, ...sharing ? [share] : []);
    };
    const place = () => {
      const bar = layer.parentElement?.querySelector(".ytp-progress-bar")?.getBoundingClientRect();
      if (!bar?.width) return;
      const box2 = layer.getBoundingClientRect();
      Object.assign(strip.style, {
        left: `${bar.left - box2.left}px`,
        width: `${bar.width}px`,
        right: "auto",
        top: `${bar.top - box2.top + bar.height / 2 - STRIP_MIDDLE}px`,
        bottom: "auto"
      });
    };
    const follow = () => {
      place();
      const now = video.currentTime;
      for (const [f, mark] of marks2) {
        const soon = shows(f) && f.t - HEADS_UP <= now && now < f.t;
        mark.style.filter = soon ? "brightness(1.6)" : "";
        mark.style.boxShadow = soon ? `0 0 0 1.5px rgba(10,14,21,.7),0 0 8px 2px ${look(f).mark}` : "";
      }
      const at = litAt(rows.map(([f]) => f).filter((f) => verdict(f) !== "drop"), now);
      for (const [f, row] of rows) {
        row.classList.toggle("fc-now", f === at);
        row.classList.toggle("fc-past", !!at && f.t < at.t);
      }
      if (at === lit) return;
      for (const el of litParts) el.remove();
      lit = at;
      litParts = at ? nowParts(at) : [];
      if (following) scrollToNow();
    };
    const nowParts = (f) => {
      const row = rows.find(([r]) => r === f)?.[1];
      if (!row || f.type === "context") return [];
      const w = words();
      const l = look(f);
      const tag = span("fc-nowtag");
      tag.append(span("fc-live"), w.now);
      row.querySelector(".fc-rh").append(tag);
      const why = div("fc-x", verdict(f) === "nitpick" ? f.judge.reason : f.reason);
      const foot = div("fc-rft");
      const source = f.sources[0];
      if (source) {
        const link = Object.assign(document.createElement("a"), { href: source.url, target: "_blank", rel: "noopener" });
        link.append(w.sources(f.sources.length), icon("arrow"));
        link.addEventListener("click", (e) => e.stopPropagation());
        foot.append(link);
      }
      foot.append(confidence(f, l));
      row.querySelector(".fc-rq").after(why, foot);
      return [tag, why, foot];
    };
    const update = () => {
      render();
      follow();
    };
    update();
    layer.addEventListener("fc-settings", () => {
      shown(shared);
      update();
    });
    layer.addEventListener("fc-flags", update);
    for (const type of ["timeupdate", "durationchange"]) video.addEventListener(type, update);
    return () => {
      for (const type of ["timeupdate", "durationchange"]) video.removeEventListener(type, update);
    };
  }

  // src/content.ts
  var POLL_MS = 3e3;
  var unmount = null;
  async function send(message) {
    try {
      return await chrome.runtime.sendMessage(message);
    } catch (error) {
      if (chrome.runtime?.id && !String(error).includes("context invalidated")) throw error;
      unmount?.();
      unmount = null;
      document.removeEventListener("yt-navigate-finish", start);
      return null;
    }
  }
  async function start() {
    unmount?.();
    unmount = null;
    const videoId = new URLSearchParams(location.search).get("v");
    const player = document.getElementById("movie_player");
    const video = player?.querySelector("video");
    if (location.pathname !== "/watch" || !videoId || !player || !video) return;
    let flags = null;
    let poll;
    let alive = true;
    let asking = null;
    const ask = async () => {
      const res = await send({ kind: "share", videoId });
      if (!res?.ok || !res.data) {
        asking = null;
        return;
      }
      if (res.data.share !== null) return;
      const w = words().consent;
      const box = div("fc-consent fc-s");
      box.style.cssText = "position:absolute;left:12px;top:12px;max-width:400px;padding:12px;border-radius:10px;font-size:12.5px;line-height:1.5;color:var(--t1);pointer-events:auto;display:flex;flex-direction:column;gap:8px";
      const privacy = Object.assign(
        document.createElement("a"),
        { href: PRIVACY, target: "_blank", rel: "noopener", textContent: w.privacy }
      );
      privacy.style.color = "inherit";
      const share = await new Promise((done) => {
        const answers = div("");
        answers.style.cssText = "display:flex;gap:8px;align-items:center";
        answers.append(button(w.yes, () => done(true)), button(w.no, () => done(false)), privacy);
        box.append(div("", w.ask), answers);
        overlay.layer.append(box);
      });
      box.remove();
      await send({ kind: "set-share", videoId, share });
    };
    const consent = () => asking ??= ask();
    const overlay = mountOverlay(player, video, () => flags, (flag, verdict2, reason) => {
      flag.mark = verdict2;
      consent().then(() => send({ kind: "mark", videoId, flagId: flag.id, verdict: verdict2, reason }));
    });
    const shareReply = async (message) => {
      const res = await send(message);
      return res?.ok && res.data ? res.data.share : null;
    };
    const unmountPanel = mountPanel(
      overlay.layer,
      video,
      () => flags,
      overlay.show,
      () => send({ kind: "summary", videoId }),
      { get: () => shareReply({ kind: "share", videoId }), set: (on) => shareReply({ kind: "set-share", videoId, share: on }) },
      (name, role) => send({ kind: "role", videoId, name, role }),
      () => send({ kind: "keys", videoId, lang: lang() })
    );
    unmount = () => {
      alive = false;
      clearInterval(poll);
      unmountPanel();
      overlay.unmount();
    };
    const notice = div("fc-down fc-s");
    notice.style.cssText = "position:absolute;left:12px;top:12px;max-width:380px;padding:10px 12px;border-radius:10px;font-size:12.5px;line-height:1.5;color:var(--t1);pointer-events:auto";
    const down = (res) => {
      if (res?.down) {
        notice.replaceChildren(...words().helperDown.map((text) => div("", text)));
        overlay.layer.append(notice);
      } else {
        notice.remove();
      }
      return Boolean(res?.down);
    };
    const refresh = async () => {
      const res = await send({ kind: "flags", videoId, at: video.currentTime, lang: lang() });
      if (!alive) return null;
      down(res);
      if (res?.ok && res.data) {
        flags = res.data;
        overlay.layer.dispatchEvent(new Event("fc-flags"));
      }
      if (flags && flags.status !== "running") clearInterval(poll);
      return res;
    };
    const follow = () => {
      clearInterval(poll);
      poll = setInterval(refresh, POLL_MS);
      refresh();
    };
    const button2 = document.createElement("button");
    button2.className = "fc-start fc-s fc-tog";
    button2.textContent = words().analyze;
    overlay.layer.addEventListener("fc-settings", () => {
      button2.textContent = words().analyze;
    });
    button2.style.cssText = "position:absolute;left:12px;top:12px";
    const note = div("fc-shared fc-s fc-m", words().shared);
    note.style.cssText = "position:absolute;left:12px;top:12px;padding:6px 10px;border-radius:8px;font-size:12px";
    overlay.layer.addEventListener("fc-settings", () => {
      note.textContent = words().shared;
    });
    const spend = div("fc-spend fc-m");
    spend.style.cssText = "position:absolute;left:12px;top:48px;max-width:360px;font-size:12px;line-height:1.4";
    let provider = "";
    const spent = () => {
      spend.textContent = words().spend[provider] ?? words().spend.api;
    };
    overlay.layer.addEventListener("fc-settings", () => {
      if (provider) spent();
    });
    const look2 = async () => {
      const res = await refresh();
      if (!alive || down(res)) return;
      clearInterval(poll);
      const known = flags;
      const retry = known?.status === "stopped" && Boolean(known.stop_reason?.startsWith("error"));
      if (!known || retry) {
        overlay.layer.append(button2);
        const res2 = await send({ kind: "provider", videoId });
        provider = res2?.ok && res2.data ? res2.data.provider : "";
        if (provider && button2.isConnected) {
          spent();
          overlay.layer.append(spend);
        }
      } else if (known.source === "shared") overlay.layer.append(note);
      else if (known.status === "running") follow();
    };
    button2.addEventListener("click", async () => {
      button2.remove();
      spend.remove();
      await consent();
      const res = await send({ kind: "analyze", videoId, from: video.currentTime, lang: lang() });
      if (!alive) return;
      if (down(res)) {
        poll = setInterval(look2, POLL_MS);
        return;
      }
      follow();
    });
    poll = setInterval(look2, POLL_MS);
    await look2();
  }
  document.addEventListener("yt-navigate-finish", start);
  start();
})();
