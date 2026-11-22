// f7 §19.10 §4: the solid tooltip. Any element with `data-tip` shows that text in one shared layer: after 300 ms
// under a mouse or on keyboard focus, at once on a tap; a second tap, or a tap elsewhere, closes it. A blank line in
// the text starts a new block, 8 px below (S6: the lead, then the facts). It opens above or below the element, on the
// side with room, so it never covers what opened it.
import { useEffect, useId, useRef, type KeyboardEvent as KeyEvent } from "react";

const OPEN_MS = 300;
const GAP = 8; // between the element and the tooltip, and from the window's edge

/** The props that give an element its tooltip; `focus` makes a non-control reachable by keyboard. */
export const tip = (text: string, focus = false) => ({ "data-tip": text, ...(focus ? { tabIndex: 0 } : {}) });

/** A lane of dense marks (f7 §19.10) is one tab stop, named by `label`: Left and Right, Home and End move between its
 * marks, each showing its tooltip; Enter follows the mark's link, or its `data-href`; Escape closes the tooltip. */
export const lane = (label: string) => ({ role: "group", "aria-label": label, onKeyDown: laneKeys });
/** A mark's place in its lane's one tab stop: the first mark holds it until the arrows move it. */
export const stop = (first: boolean) => ({ tabIndex: first ? 0 : -1 });

function laneKeys(e: KeyEvent<HTMLElement>) {
  const marks = [...e.currentTarget.querySelectorAll<HTMLElement>("[data-tip]")];
  const at = marks.indexOf(document.activeElement as HTMLElement);
  if (at < 0) return;
  const href = marks[at].dataset.href;
  if (e.key === "Enter" && href) return location.assign(href);
  const to = ({ ArrowLeft: at - 1, ArrowRight: at + 1, Home: 0, End: marks.length - 1 } as Record<string, number>)[e.key];
  if (to === undefined) return;
  e.preventDefault();
  const next = marks[Math.max(0, Math.min(marks.length - 1, to))];
  marks[at].tabIndex = -1;
  next.tabIndex = 0;
  next.focus();
}

export function Tips() {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const layer = box.current!;
    let on: HTMLElement | null = null;
    let timer = 0;
    const hide = () => {
      clearTimeout(timer);
      on?.removeAttribute("aria-describedby");
      on = null;
      layer.hidden = true;
    };
    const show = (el: HTMLElement) => {
      layer.replaceChildren(...el.dataset.tip!.split("\n\n").map((part) => Object.assign(document.createElement("p"), { textContent: part })));
      layer.hidden = false;
      const at = el.getBoundingClientRect();
      const { width, height } = layer.getBoundingClientRect();
      const above = at.top - GAP - height >= 0 || at.bottom + GAP + height > innerHeight;
      layer.style.top = `${above ? at.top - GAP - height : at.bottom + GAP}px`;
      layer.style.left = `${Math.min(Math.max(GAP, at.left + at.width / 2 - width / 2), innerWidth - width - GAP)}px`;
    };
    const open = (el: HTMLElement, wait: number) => {
      if (el === on) return;
      hide();
      on = el;
      el.setAttribute("aria-describedby", id);
      timer = window.setTimeout(() => show(el), wait);
    };
    const target = (e: Event) => (e.target as Element | null)?.closest?.<HTMLElement>("[data-tip]") ?? null;
    const over = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const el = target(e);
      if (el) open(el, OPEN_MS);
    };
    const out = (e: PointerEvent) => {
      if (on && !on.contains(e.relatedTarget as Node | null)) hide();
    };
    const tap = (e: PointerEvent) => {
      if (e.pointerType === "mouse") return;
      const el = target(e);
      if (el && el !== on) open(el, 0);
      else hide();
    };
    const focus = (e: FocusEvent) => {
      const el = target(e);
      if (el) open(el, OPEN_MS);
    };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") hide(); };
    document.addEventListener("pointerover", over);
    document.addEventListener("pointerout", out);
    document.addEventListener("pointerdown", tap);
    document.addEventListener("focusin", focus);
    document.addEventListener("focusout", hide);
    document.addEventListener("keydown", key);
    addEventListener("scroll", hide, { passive: true });
    return () => {
      hide();
      document.removeEventListener("pointerover", over);
      document.removeEventListener("pointerout", out);
      document.removeEventListener("pointerdown", tap);
      document.removeEventListener("focusin", focus);
      document.removeEventListener("focusout", hide);
      document.removeEventListener("keydown", key);
      removeEventListener("scroll", hide);
    };
  }, [id]);
  return <div ref={box} id={id} role="tooltip" hidden className="tooltip" />;
}
