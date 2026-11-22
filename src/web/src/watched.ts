// What this browser watched (S9): each video's progress and the list's last view, in local storage only. No request
// carries them, and a browser that blocks storage simply shows nothing as watched.
export type View = "lista" | "cuadricula";
export type State = "nuevo" | "empezado" | "visto" | null;
/** A video's progress: the second reached, the video's length, and whether it was watched to the end. */
interface Progress { at: number; of: number; end?: boolean }

const PROGRESS = "calvet-watched";
const VIEW = "calvet-list-view";
const STARTED_S = 30;
const SEEN = 0.9;
const NEW_DAYS = 7;

function load(): Record<string, Progress> {
  try {
    return JSON.parse(localStorage.getItem(PROGRESS) ?? "{}");
  } catch { return {}; } // storage blocked or broken: nothing watched
}

export const progress = (id: string): Progress | undefined => load()[id];

/** Saves the second reached; a video seen to 90 % or to the player's end stays seen. */
export function save(id: string, at: number, of: number, end = false) {
  const all = load();
  const was = all[id];
  all[id] = { at, of, ...((end || was?.end || (of > 0 && at / of >= SEEN)) ? { end: true } : {}) };
  try {
    localStorage.setItem(PROGRESS, JSON.stringify(all));
  } catch { /* storage blocked: the progress lives for this page only */ }
}

/** The bar's share, 0 to 1; null when nothing shows. */
export function share(p: Progress | undefined): number | null {
  if (!p) return null;
  if (p.end) return 1;
  return p.at >= STARTED_S && p.of > 0 ? Math.min(1, p.at / p.of) : null;
}

/** "Nuevo" (published 7 days ago or less, never opened here), "Empezado" (from 30 s), "Visto" (from 90 % or the end). */
export function stateOf(id: string, published: string | null, p = progress(id)): State {
  if (p?.end) return "visto";
  if (p) return p.at >= STARTED_S ? "empezado" : null;
  return published && Date.now() - new Date(`${published}T00:00:00Z`).getTime() <= NEW_DAYS * 86_400_000 ? "nuevo" : null;
}

export function lastView(): View | null {
  try {
    const v = localStorage.getItem(VIEW);
    return v === "lista" || v === "cuadricula" ? v : null;
  } catch { return null; }
}

export function keepView(v: View) {
  try {
    localStorage.setItem(VIEW, v);
  } catch { /* storage blocked: the address still holds the view */ }
}
