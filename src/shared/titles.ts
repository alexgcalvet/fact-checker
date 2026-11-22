// The title a reader sees (owner, 2026-11-22), in Spanish sentence case: a YouTube title without its leading live tag,
// its shouted words in lower case, a capital on the first word of the title and of each part after « | », « - » or
// «: », and a shouted word that is a known proper name (a guest, a channel or outlet of our own data) in that name's
// own case. Acronyms stay in capitals, and words the title did not shout keep their case. The collector computes it
// (with the owner's own display title winning) and the raw title stays in the data.

// A live tag that opens a title, with its separator: «🔴 DIRECTO |», «EN DIRECTO:», «LIVE -».
const TAG = /^\s*(?:🔴\s*)?(?:EN\s+)?(?:DIRECTO|VIVO|LIVE|STREAM)\s*[|:\-–—]\s*/iu;
// Acronyms of 4 or more letters that stay in capitals; shorter shouted words (PP, CIS, UE, 23J) stay as they are unless
// they are a known name or a small word.
const ACRONYMS = new Set(["PSOE", "RTVE", "OTAN", "NATO", "EEUU", "CCOO", "IBEX", "UNED", "OCDE", "FAES", "CEOE", "DANA", "MUFACE"]);
// Short words that go lower case when shouted beside a shouted word.
const SMALL = new Set(["A", "Y", "E", "O", "U", "DE", "DEL", "EL", "LA", "LO", "LOS", "LAS", "EN", "CON", "POR", "AL", "UN",
  "UNA", "SU", "SUS", "SE", "QUE", "SIN", "THE", "OF", "AND", "IN", "ON", "TO"]);

const shouted = (w: string) => w === w.toUpperCase() && w !== w.toLowerCase();
const key = (w: string) => w.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

export function cleanTitle(raw: string, names: string[] = []): string {
  let title = raw;
  while (TAG.test(title)) title = title.replace(TAG, "");
  // Words and what lies between them, alternately: parts[1], parts[3]… are the words.
  const parts = title.split(/([\p{L}\p{N}]+)/u);
  const words = parts.map((_, i) => i % 2 === 1);
  const loud = (i: number) => words[i] && shouted(parts[i]) && parts[i].length >= 4 && !ACRONYMS.has(parts[i]);
  // Each shouted word that may change: lowered, or kept as it is but still open to a name.
  const open = parts.map((p, i) => words[i] && shouted(p) && !ACRONYMS.has(p));
  const out = parts.map((p, i) => {
    if (!open[i]) return p;
    if (loud(i) || (SMALL.has(p) && (loud(i - 2) || loud(i + 2)))) return p.toLowerCase();
    return p;
  });
  // A known name, its words matched as a whole and only on shouted words joined by spaces, takes its own case.
  const named = new Set<number>();
  for (const name of [...names].sort((a, b) => b.split(/\s+/).length - a.split(/\s+/).length)) {
    // A name our data keeps in capitals has no case of its own: a capital on each word but the small ones, and a short
    // word that is not a small one stays an acronym («CADENA SER» → «Cadena SER»).
    const want = name.split(/\s+/).map((w, k) => !shouted(w) ? w
      : k > 0 && SMALL.has(w) ? w.toLowerCase() : w.length <= 3 && !SMALL.has(w) ? w : w[0] + w.slice(1).toLowerCase());
    for (let i = 1; i < parts.length; i += 2) {
      const at = want.map((_, k) => i + 2 * k);
      if (at.every((j, k) => open[j] && !named.has(j) && key(parts[j]) === key(want[k]) && (k === 0 || /^\s+$/.test(parts[j - 1])))) {
        at.forEach((j, k) => { out[j] = want[k]; named.add(j); });
      }
    }
  }
  // The first word of the title and of each part takes a capital.
  for (let i = 1; i < parts.length; i += 2) {
    if (open[i] && !named.has(i) && (i === 1 || /[|:\-–—]/.test(parts[i - 1]))) out[i] = out[i][0].toUpperCase() + out[i].slice(1);
  }
  return out.join("");
}
