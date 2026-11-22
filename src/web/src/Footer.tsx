// f7 §19.10 §5: the language toggle, and the footer that every reading page shares (the viewer has none).
import { Fragment } from "react";
import calvet from "../brand/calvet-quilla-nav14.svg";
import xLogo from "../brand/x-logo.svg";
import { TEXTS, type Lang } from "./texts";

// Each language named in itself.
const NAMES = { es: "Español", en: "English" };

/** The language toggle of the header and the footer: plain text, since a language is not a country, so no flag. */
export function Langs({ lang }: { lang: Lang }) {
  const other = (l: Lang) => location.pathname.replace(/^\/(es|en)/, `/${l}`);
  return (
    <nav aria-label={TEXTS[lang].nav} className="langs">
      {(["es", "en"] as Lang[]).map((l, i) => <Fragment key={l}>
        {i > 0 && <span aria-hidden="true" className="sep-dot">·</span>}
        {l === lang
          ? <span aria-current="true" lang={l} aria-label={NAMES[l]}>{l.toUpperCase()}</span>
          : <a href={other(l)} hrefLang={l} lang={l} aria-label={NAMES[l]}>{l.toUpperCase()}</a>}
      </Fragment>)}
    </nav>
  );
}

/** Where a reading page sits in the site: the home page, the video list, "Cómo funciona", or another page (no section
 * lit). */
export type Section = "home" | "videos" | "how" | "other";

/** The owner's X profile: the footer's CALVET + X logo link goes to it (owner, 2026-11-22). */
export const X_PROFILE = "https://x.com/alexgcalvet";

/** The props of a link to X: a new tab, named as such (f7 §19.10). */
export const xLink = (lang: Lang) =>
  ({ href: X_PROFILE, target: "_blank", rel: "noopener", "aria-label": TEXTS[lang].x.label, title: TEXTS[lang].x.title });

/** The header's pill bar of a reading page: Inicio · Vídeos · Cómo funciona | ES · EN, the current section lit. A phone
 * drops the language, which its footer holds (f7 §19.10, Phone navigation). */
export function SiteBar({ lang, at }: { lang: Lang; at: Section }) {
  const t = TEXTS[lang];
  return (
    <div className="site-bar">
      <nav aria-label={t.footer.site} className="site-nav">
        <a href={`/${lang}/`} aria-current={at === "home" ? "page" : undefined}>{t.footer.home}</a>
        <a href={`/${lang}/videos`} aria-current={at === "videos" ? "page" : undefined}>{t.footer.videos}</a>
        <a href={`/${lang}/${t.list.howPath}`} aria-current={at === "how" ? "page" : undefined}>{t.list.how}</a>
      </nav>
      <span aria-hidden="true" className="site-sep" />
      <Langs lang={lang} />
    </div>
  );
}

/** One row: CALVET on X, the disclosure, the links, then the language with the prompts version, which shows only on a page of one
 * video (owner review 2026-11-21: no cookies line). The link to the current page is plain text. */
export function Footer({ lang, prompts }: { lang: Lang; prompts?: string | null }) {
  const t = TEXTS[lang];
  const how = `/${lang}/${t.list.howPath}`;
  const links: [string, string][] = [[`/${lang}/`, t.footer.home], [`/${lang}/videos`, t.footer.videos], [how, t.list.how],
    [`${how}#feedback`, t.footer.correct]];
  const [release, hash] = prompts?.split("+") ?? [];
  return (
    <footer aria-label={t.footer.label} className="footer">
      {/* CALVET on X opens the footer, at its far left (owner, 2026-11-22). CALVET and the X logo are one link, never a
          bare letter "X"; both drawn as masks so their colour is a token. */}
      <a {...xLink(lang)} className="footer-by">
        <span aria-hidden="true" className="footer-calvet" style={{ maskImage: `url("${calvet}")`, WebkitMaskImage: `url("${calvet}")` }} />
        <span aria-hidden="true" className="footer-x" style={{ maskImage: `url("${xLogo}")`, WebkitMaskImage: `url("${xLogo}")` }} />
      </a>
      <p className="footer-ai">{t.ai}</p>
      <ul className="footer-links">
        {links.map(([href, label]) => <li key={href}>
          {href === location.pathname ? <span aria-current="page">{label}</span> : <a href={href}>{label}</a>}
        </li>)}
      </ul>
      <div className="footer-meta">
        <Langs lang={lang} />
        {prompts && <span className="footer-version"><span className="footer-word">{t.footer.version}</span> {release}{hash && <span className="footer-hash">+{hash}</span>}</span>}
      </div>
    </footer>
  );
}
