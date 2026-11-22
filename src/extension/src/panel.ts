import { FAMILIES, look, title, TYPE_LOOK, verdict, type Flag, type FlagFile } from "./flags";
import { button, confidence, div, dot, fault, icon, lang, minute, onPlayer, setSettings, settings, shows, span, SHOWN_TYPES, words, ZOOM,
  type Settings } from "./overlay";
import { stopKind, TEXTS } from "./texts";
import { inOrder, litAt } from "../../shared/panel";

const HEADS_UP = 2;
const STRIP_MIDDLE = 9; // px from the top of the strip to its track's middle

/** The helper's switch that shares each new mark with the author: read it, or set it. null when the helper is down. */
export type Sharing = {
  get: () => Promise<boolean | null>;
  set: (on: boolean) => Promise<boolean | null>;
};

export const TYPE_COLOR = Object.fromEntries(Object.entries(TYPE_LOOK).map(([type, l]) => [type, l.mark]));

/**
 * Draws a mark per flag on a strip over YouTube's progress bar, and a side panel, the feed, that lists every flag,
 * the ones under the bar too. A click on a mark or a row seeks the video there and calls `show`.
 * Under the marks, the strip shows the analysed part and the part still pending.
 * A mark glows for the 2 seconds before its card shows. The feed lights the row at the playhead, with its reason,
 * sources and confidence, and dims the past. It scrolls with the playhead until the person scrolls it; then
 * "Ir al directo" brings it back.
 * Its header holds a filter per family, a button that exports the shareable summary of the video, and a ⚙.
 * Under the filters, once the voices are told apart, each speaker with its role; a click on the role switches it
 * between host and guest and calls `setRole`, so the summary follows.
 * With `sharing`, its foot says whether each mark is shared with the project's author, and the ⚙ box switches it;
 * the helper is asked again each time the panel opens. The ⚙ box's keys button calls `openKeys`: the helper's own page
 * takes the API keys, so a key never passes through YouTube's page.
 */
export function mountPanel(
  layer: HTMLElement,
  video: HTMLVideoElement,
  getFlags: () => FlagFile | null,
  show: (flag: Flag) => void,
  exportSummary: () => void = () => {},
  sharing?: Sharing,
  setRole: (name: string, role: "host" | "guest") => void = () => {},
  openKeys: () => void = () => {},
): () => void {
  const strip = div("fc-strip");
  const tip = div("fc-tip fc-s");
  tip.hidden = true;
  const tab = document.createElement("button");
  tab.className = "fc-panel-tab fc-s fc-tog";
  tab.style.cssText = "position:absolute;right:12px;bottom:72px";
  const panel = div("fc-panel fc-s");
  panel.style.display = "none";
  const stopped = div("fc-stopped fc-s");
  stopped.style.cssText = "position:absolute;left:12px;top:56px;max-width:380px;padding:10px 12px;border-radius:10px;" +
    "font-size:12.5px;line-height:1.5;color:var(--t1);pointer-events:auto";
  // The open panel covers the right of the player, so the cards make way for it (see the overlay's draw).
  // The foot line says whether marks are shared; it hides while the helper does not answer.
  const share = div("fc-share fc-m");
  share.style.cssText = "padding:10px 16px;font-size:12px;border-top:.5px solid rgba(255,255,255,.08)";
  let shared: boolean | null = null;
  const shown = (on: boolean | null) => {
    shared = on;
    share.hidden = on === null;
    share.textContent = on === null ? "" : on ? words().sharing.on : words().sharing.off;
    if (box.style.display !== "none") drawBox();
  };
  const ask = async () => shown((await sharing?.get()) ?? null);
  const setOpen = (open: boolean) => {
    if (open) ask();
    panel.style.display = open ? "" : "none";
    layer.classList.toggle("fc-panel-open", open);
    layer.dispatchEvent(new Event("fc-settings"));
  };
  tab.addEventListener("click", () => setOpen(panel.style.display === "none"));
  // Before the cards, so a card stays on top of the open panel.
  layer.prepend(strip, panel, tab);
  const size = () => { panel.style.zoom = ZOOM[settings.size]; };
  layer.addEventListener("fc-settings", size);
  size();

  const jump = (flag: Flag) => {
    video.currentTime = flag.t;
    show(flag);
  };

  // The ⚙ box: text size, card side, quiet mode, language and the keys page.
  const box = div("fc-settings");
  box.style.display = "none";
  const drawBox = () => {
    const w = words();
    const choice = (label: string, key: "size" | "side" | "lang", options: [string, string][]) => {
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
      button(w.keys, openKeys),
    );
    if (sharing && shared !== null) {
      const line = document.createElement("label");
      const on = Object.assign(document.createElement("input"), { type: "checkbox", checked: shared });
      on.addEventListener("change", async () => shown((await sharing.set(on.checked)) ?? shared));
      line.append(on, ` ${w.sharing.toggle}`);
      box.append(line);
    }
  };
  const change = (c: Partial<Settings>) => {
    setSettings(c, layer);
    drawBox();
  };

  // The list outlives a redraw, so its scroll stays while flags arrive.
  const list = div("fc-list");
  const feed = div("fc-feed");
  feed.style.cssText = "position:relative;flex:1;min-height:0;display:flex;flex-direction:column";
  let following = true;
  const live = button("", () => { following = true; live.hidden = true; scrollToNow(); }, "fc-jump fc-s");
  live.hidden = true;
  for (const type of ["wheel", "touchmove"]) {
    list.addEventListener(type, () => { following = false; live.hidden = false; }, { passive: true });
  }
  feed.append(list, live);

  let only: string | null = null;
  let marks: [Flag, HTMLElement][] = [];
  let rows: [Flag, HTMLElement][] = [];
  let drawn = "";
  let seen = new Set<string>();
  // The flag at the playhead and the parts its row shows only while lit.
  let lit: Flag | undefined;
  let litParts: HTMLElement[] = [];
  const scrollToNow = () => {
    const row = rows.find(([f]) => f === lit)?.[1];
    if (row) list.scrollTop = row.offsetTop - list.clientHeight / 3;
  };
  const render = () => {
    const file = getFlags();
    const flags = inOrder((file?.flags ?? []).filter((f) => SHOWN_TYPES.includes(f.type)));
    const analysed = file?.status === "done" ? 100 : Math.min(100, ((file?.analysed_until ?? 0) / video.duration) * 100);
    // Until the first part is read, the tab says so instead of a silent 0.
    const preparing = file?.status === "running" && file.first_flags_s === undefined;
    const stop = file?.status === "stopped" ? file.stop_reason : undefined;
    const people = Object.entries(file?.people ?? {});
    const key = `${lang()}|${video.duration}|${analysed}|${only}|${preparing}|${stop}|${flags.map((f) => f.id).join("|")}|` +
      people.map(([name, p]) => `${name}:${p.role}`).join("|");
    if (key === drawn) return;
    drawn = key;
    // The counts hold what stands: a flag the judge dropped waits folded at the end of the feed.
    const w = words();
    const standing = flags.filter((f) => verdict(f) !== "drop");
    if (preparing) tab.replaceChildren(w.preparing);
    else tab.replaceChildren(`${w.panel} `, span("fc-n", `(${standing.length})`));
    // A stopped analysis says why, in one line on the player.
    if (stop === undefined) stopped.remove();
    else {
      stopped.textContent = w.stoppedLine(w.stopped[stopKind(stop)]);
      layer.append(stopped);
    }
    marks = video.duration > 0 ? flags.map((f) => {
      const mark = div("fc-mark");
      mark.addEventListener("pointerenter", () => {
        tip.replaceChildren(dot(look(f)), span("fc-m fc-num", minute(f.t)), title(f, lang()));
        tip.style.left = mark.style.left;
        tip.hidden = false;
      });
      mark.addEventListener("pointerleave", () => { tip.hidden = true; });
      mark.style.left = `${(f.t / video.duration) * 100}%`;
      // A flag that reaches the player gets its verdict disc; one under the bar, a small plain dot.
      const full = onPlayer(f) && verdict(f) !== "drop";
      mark.style.width = mark.style.height = full ? "12px" : "6px";
      mark.style.backgroundColor = look(f).mark;
      if (full) mark.style.backgroundImage = look(f).dot;
      mark.addEventListener("click", () => jump(f));
      return [f, mark];
    }) : [];
    const part = (className: string, left: number, width: number) => {
      const el = div(className);
      el.style.left = `${left}%`;
      el.style.width = `${width}%`;
      return el;
    };
    const parts = video.duration > 0 ? [part("fc-analysed", 0, analysed), part("fc-pending", analysed, 100 - analysed)] : [];
    strip.replaceChildren(...parts, ...marks.map(([, mark]) => mark), tip);
    // YouTube's red bar already shows playback: once the analysis is done, the strip shows only the marks.
    strip.classList.toggle("fc-done", analysed >= 100);

    const head = div("fc-t");
    const gear = button("⚙", () => {
      box.style.display = box.style.display === "none" ? "" : "none";
      drawBox();
    }, "fc-ib");
    gear.title = w.settings;
    const close = button("", () => setOpen(false), "fc-ib");
    close.append(icon("x"));
    close.title = w.close;
    head.append(w.panel, span("fc-cnt fc-num", String(standing.length)), button(w.export, exportSummary), gear, close);
    // "Todos · Falsos 4 · Retórica 7": a click shows only that family, a second click shows all again.
    const filters = div("fc-flt");
    const filter = (family: string | null, ...content: (Node | string)[]) => {
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
      const list = div("fc-people");
      for (const [name, p] of people) {
        const line = div("");
        line.append(span("", p.person), " · ", button(w.roles[p.role], () => {
          p.role = p.role === "host" ? "guest" : "host";
          p.set_by = "person";
          setRole(name, p.role);
          render();
        }, ""));
        list.append(line);
      }
      top.append(list);
    }

    rows = flags.filter((f) => !only || look(f).family === only).map((f) => {
      const l = look(f);
      const row = div("fc-row");
      // A new flag enters from below; the first draw does not animate.
      if (seen.size && !seen.has(f.id)) row.classList.add("fc-enter");
      const dropped = verdict(f) === "drop";
      if (!onPlayer(f) || dropped) row.style.opacity = "0.5";
      let struck: HTMLElement[];
      if (f.type === "context") {
        // A context entity: dot, minute and the name, on one line; the reason shows on hover.
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
        const quote = div("fc-rq", `«${f.quote}»`);
        row.append(line, quote);
        struck = [line, quote];
      }
      if (dropped) {
        for (const el of struck) el.style.textDecoration = "line-through";
        row.append(div("fc-why", `${w.dropped}: ${f.judge!.reason}`));
      }
      row.addEventListener("click", () => {
        following = true;
        live.hidden = true;
        jump(f);
      });
      return [f, row];
    });
    seen = new Set(flags.map((f) => f.id));
    lit = undefined;
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
    panel.replaceChildren(top, fault(), feed, signals, ...(sharing ? [share] : []));
  };

  // The strip lies over YouTube's own progress bar, so a mark and the playhead sit where YouTube puts that second.
  // The bar moves with the player's size (theatre, fullscreen), so it is measured again on every update.
  const place = () => {
    const bar = layer.parentElement?.querySelector(".ytp-progress-bar")?.getBoundingClientRect();
    if (!bar?.width) return;
    const box = layer.getBoundingClientRect();
    Object.assign(strip.style, {
      left: `${bar.left - box.left}px`, width: `${bar.width}px`, right: "auto",
      top: `${bar.top - box.top + bar.height / 2 - STRIP_MIDDLE}px`, bottom: "auto",
    });
  };
  const follow = () => {
    place();
    const now = video.currentTime;
    for (const [f, mark] of marks) {
      const soon = shows(f) && f.t - HEADS_UP <= now && now < f.t;
      mark.style.filter = soon ? "brightness(1.6)" : "";
      mark.style.boxShadow = soon ? `0 0 0 1.5px rgba(10,14,21,.7),0 0 8px 2px ${look(f).mark}` : "";
    }
    // The row at the playhead is the last one already said; the rows before it are past.
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
  // The lit row of a claim adds "Ahora", the reason, a link to its first source and the confidence.
  const nowParts = (f: Flag): HTMLElement[] => {
    const row = rows.find(([r]) => r === f)?.[1];
    if (!row || f.type === "context") return [];
    const w = words();
    const l = look(f);
    const tag = span("fc-nowtag");
    tag.append(span("fc-live"), w.now);
    row.querySelector(".fc-rh")!.append(tag);
    const why = div("fc-x", verdict(f) === "nitpick" ? f.judge!.reason : f.reason);
    const foot = div("fc-rft");
    const source = f.sources[0];
    if (source) {
      const link = Object.assign(document.createElement("a"), { href: source.url, target: "_blank", rel: "noopener" });
      link.append(w.sources(f.sources.length), icon("arrow"));
      link.addEventListener("click", (e) => e.stopPropagation());
      foot.append(link);
    }
    foot.append(confidence(f, l));
    row.querySelector(".fc-rq")!.after(why, foot);
    return [tag, why, foot];
  };
  const update = () => { render(); follow(); };

  update();
  // A new language redraws the panel with its texts.
  layer.addEventListener("fc-settings", () => { shown(shared); update(); });
  // The flag file grows while the helper analyses, and the duration arrives with the metadata.
  layer.addEventListener("fc-flags", update);
  for (const type of ["timeupdate", "durationchange"]) video.addEventListener(type, update);
  return () => {
    for (const type of ["timeupdate", "durationchange"]) video.removeEventListener(type, update);
  };
}
