// The public web app. The Worker serves this page for every /es/* and /en/* path; the path picks the screen.
import "./style.css";
import { createRoot, type Root } from "react-dom/client";
import type { ReactNode } from "react";
import { inOrder } from "../../shared/panel";
import type { Flag } from "./marks";
import type { Section } from "./Footer";
import { TEXTS, type Lang } from "./texts";
import { List, Loading, type Listed } from "./List";
import { Compare } from "./Compare";
import { Profile } from "./Profile";
import { How } from "./How";
import { Home } from "./Home";
import { Back, COMPARE, Lost, Page, State, Viewer, type Meta, type PlayerClass } from "./Viewer";

/** Fills `el` with the screen of the address: `/<lang>/` is the home page, `/<lang>/videos` the video list, `/<lang>/v/<video_id>` the viewer of that video,
 * `/<lang>/v/<video_id>/<guest>` the profile of one of its guests, `/<lang>/v/<video_id>/comparar` (or `compare`) the
 * comparison of its guests, and `/es/como-funciona` (`/en/how-it-works`) the page on the method. */
/** The tab's title: the page's name, then the site; the home page is the site alone (owner, 2026-11-22). */
const tab = (page?: string) => { document.title = page ? `${page.replace(/\.$/, "")} · DeFacto` : "DeFacto"; };

export async function mount(el: HTMLElement, Player: PlayerClass | Promise<PlayerClass>): Promise<void> {
  const lang = location.pathname.split("/")[1] as Lang;
  const root = createRoot(el);
  try {
    await screen(root, Player);
  } catch (error) {
    // The data failed to load: the error page, and the error stays in the console.
    tab(TEXTS[lang].broken);
    root.render(<Page lang={lang} nav="other"><Lost lang={lang} line={TEXTS[lang].broken} /></Page>);
    throw error;
  }
}

async function screen(root: Root, Player: PlayerClass | Promise<PlayerClass>): Promise<void> {
  // An old link to a sorted list (`/<lang>/?orden=…`, before S12) keeps its order at the list's own address.
  if (/^\/(es|en)\/$/.test(location.pathname) && new URLSearchParams(location.search).has("orden")) {
    history.replaceState(history.state, "", `${location.pathname}videos${location.search}${location.hash}`);
  }
  const [, lang, page, id, guest] = location.pathname.split("/") as [string, Lang, string?, string?, string?];
  const t = TEXTS[lang];
  document.documentElement.lang = lang;
  // A reading page names its section, so its header carries the site's pill bar; the viewer and the loading state don't.
  const show = (screen: ReactNode, nav?: Section) => root.render(<Page lang={lang} nav={nav}>{screen}</Page>);
  const videos = async () => {
    const list = await fetch("/api/videos");
    if (!list.ok) throw new Error(`GET /api/videos: ${list.status}`);
    // The reader sees the display title everywhere: the owner's own, else the clean one (the collector's).
    return ((await list.json()).videos as Listed[]).map((v) => ({ ...v, title: v.display_title ?? v.title }));
  };
  if (!page) {
    tab();
    show(<Home lang={lang} videos={null} />, "home");
    return show(<Home lang={lang} videos={await videos()} />, "home");
  }
  if (page === "videos" && !id) {
    tab(t.footer.videos);
    show(<Loading lang={lang} />, "videos");
    return show(<List lang={lang} videos={await videos()} />, "videos");
  }
  if (page === t.list.howPath && !id) return tab(t.list.how), show(<How lang={lang} />, "how");
  if (page !== "v" || !id) return tab(t.notFound), show(<Lost lang={lang} line={t.notFound} />, "other");

  show(<State><div className="loading" /><p className="dim">{t.loading}</p></State>);
  // The flags are asked in the page's language at once; only a video served in the other language asks again.
  const flagsIn = (l: string) => fetch(`/api/videos/${encodeURIComponent(id)}/flags?lang=${l}`);
  const [res, asked] = await Promise.all([fetch(`/api/videos/${encodeURIComponent(id)}?lang=${lang}`), flagsIn(lang)]);
  if (res.status === 404) {
    return tab(t.none), show(<State lang={lang}><p className="none">{t.none}</p><Back lang={lang} /></State>, "other");
  }
  if (!res.ok) throw new Error(`GET /api/videos/${id}: ${res.status}`);
  const raw = await res.json() as Meta;
  const meta = { ...raw, title: raw.display_title ?? raw.title };
  const answer = meta.lang === lang ? asked : await flagsIn(meta.lang);
  if (!answer.ok) throw new Error(`GET /api/videos/${id}/flags: ${answer.status}`);
  // A flag the judge dropped does not stand: the web never shows it.
  const flags = inOrder(((await answer.json()).flags as Flag[]).filter((f) => f.judge?.verdict !== "drop"));
  tab(guest && !Object.values(COMPARE).includes(guest) ? decodeURIComponent(guest) : meta.title);
  show(guest && Object.values(COMPARE).includes(guest)
    ? <Compare lang={lang} meta={meta} flags={flags} />
    : guest
    ? <Profile lang={lang} meta={meta} flags={flags} guest={decodeURIComponent(guest)} />
    : <Viewer lang={lang} meta={meta} flags={flags} Player={await Player} />, guest ? "other" : undefined);
}

// The page itself: fill <div id="app"> at once while the IFrame Player API loads; only the viewer waits for it. A test
// imports `mount` with no #app.
const el = document.getElementById("app");
if (el) {
  const page = window as unknown as { onYouTubeIframeAPIReady: () => void; YT: { Player: PlayerClass } };
  const player = new Promise<PlayerClass>((done) => { page.onYouTubeIframeAPIReady = () => done(page.YT.Player); });
  document.head.append(Object.assign(document.createElement("script"), { src: "https://www.youtube.com/iframe_api" }));
  mount(el, player);
}
