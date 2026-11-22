// The list's filters (S8) and view (S9): read from and written to the address, the match of each video, and the count of each option
// with the other filters kept. The browser filters the list it already loads; `GET /api/videos` does not change.
import type { Lang } from "./texts";
import { short, slug } from "./Viewer";
import type { View } from "./watched";

/** The facets in the order of the address and the no-results ways; one value each. There is no filter by kind of aviso
 * (owner, 2026-11-22): an old `tipo` is ignored. */
export const FACETS = ["idioma", "canal", "invitado"] as const;
export type Facet = (typeof FACETS)[number];
export type Filters = { q: string } & Record<Facet, string | null>;

/** A video as the filters read it: the fields of `GET /api/videos` they match. */
interface Filtered {
  title: string;
  channel: string;
  guests: string[];
  langs: Lang[];
}

export const NONE: Filters = { q: "", idioma: null, canal: null, invitado: null };

export function read(search: string): Filters {
  const p = new URLSearchParams(search);
  return {
    q: p.get("q") ?? "",
    idioma: p.get("idioma") === "es" || p.get("idioma") === "en" ? p.get("idioma") : null,
    canal: p.get("canal") || null,
    invitado: p.get("invitado") || null,
  };
}

/** The list's view in the address (S9): the grid only with `vista=cuadricula`, else null. */
export const viewOf = (search: string): View | null => {
  const v = new URLSearchParams(search).get("vista");
  return v === "lista" || v === "cuadricula" ? v : null;
};

/** The address's query for these filters, sort and view, defaults left out; "" when nothing is set. */
export function write(f: Filters, sort: string, defaultSort: string, view: View = "lista"): string {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  for (const k of FACETS) if (f[k]) p.set(k, f[k]!);
  if (sort !== defaultSort) p.set("orden", sort);
  if (view !== "lista") p.set("vista", view);
  const s = p.toString();
  return s && `?${s}`;
}

/** Lower case, no accents: "PRESUPUÉSTO" and "presupuesto" read the same. */
export const fold = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

export const active = (f: Filters) => FACETS.filter((k) => f[k]);
export const any = (f: Filters) => !!f.q.trim() || active(f).length > 0;

export function matches(v: Filtered, f: Filters): boolean {
  const q = fold(f.q.trim());
  return (!q || [v.title, v.channel, ...v.guests.map(short)].some((s) => fold(s).includes(q)))
    && (!f.idioma || v.langs.includes(f.idioma as Lang))
    && (!f.canal || slug(v.channel) === f.canal)
    && (!f.invitado || v.guests.some((g) => slug(g) === f.invitado));
}

/** How many videos `f` leaves with `facet` set to `value` (null clears it): the number an option shows. */
export const count = (videos: Filtered[], f: Filters, facet: Facet | "q", value: string | null) =>
  videos.filter((v) => matches(v, { ...f, [facet]: value ?? (facet === "q" ? "" : null) })).length;

/** The channels or the guests of the archive, each once by its slug, by name. */
export function people(videos: Filtered[], facet: "canal" | "invitado"): { slug: string; name: string }[] {
  const seen = new Map<string, string>();
  for (const v of videos) {
    for (const name of facet === "canal" ? [v.channel] : v.guests.map(short)) if (!seen.has(slug(name))) seen.set(slug(name), name);
  }
  return [...seen].map(([s, name]) => ({ slug: s, name })).sort((a, b) => a.name.localeCompare(b.name));
}
