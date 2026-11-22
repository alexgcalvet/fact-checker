// A bottom sheet on a phone (brand spec §19.7): it opens under the element `below` (the video and its "Ahora" strip),
// so they stay in sight, and ends on the keyboard while one is up. A drag down on its handle past 60 px, the ×, or Esc
// closes it.
import { useLayoutEffect, useRef, type ReactNode, type RefObject } from "react";

const SWIPE_PX = 60;

export function Sheet({ label, head, close, closeLabel, below, children }:
  { label: string; head: ReactNode; close: () => void; closeLabel: string; below: RefObject<HTMLElement | null>; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const from = useRef<number | null>(null);
  const shut = useRef(close);
  shut.current = close;

  useLayoutEffect(() => {
    const view = window.visualViewport;
    const place = () => {
      const s = box.current!.style;
      s.top = `${Math.max(0, below.current!.getBoundingClientRect().bottom)}px`;
      s.bottom = view ? `${Math.max(0, innerHeight - view.height - view.offsetTop)}px` : "0px";
    };
    // Esc in a text box closes only the box.
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape" && !(e.target instanceof HTMLTextAreaElement)) shut.current(); };
    place();
    addEventListener("scroll", place);
    addEventListener("keydown", esc);
    view?.addEventListener("resize", place);
    view?.addEventListener("scroll", place);
    return () => {
      removeEventListener("scroll", place);
      removeEventListener("keydown", esc);
      view?.removeEventListener("resize", place);
      view?.removeEventListener("scroll", place);
    };
  }, []);

  const drag = (y: number) => { box.current!.style.transform = `translateY(${Math.max(0, y - from.current!)}px)`; };
  const drop = (y: number | null) => {
    const far = y !== null && y - from.current! > SWIPE_PX;
    from.current = null;
    box.current!.style.transform = "";
    if (far) close();
  };

  return (
    <div ref={box} role="dialog" aria-label={label} className="bottom-sheet">
      <div aria-hidden="true" className="grab"
        onPointerDown={(e) => { from.current = e.clientY; e.currentTarget.setPointerCapture(e.pointerId); }}
        onPointerMove={(e) => { if (from.current !== null) drag(e.clientY); }}
        onPointerUp={(e) => drop(e.clientY)} onPointerCancel={() => drop(null)} />
      <div className="sheet-body">
        <div className="sheet-row">{head}
          <button type="button" aria-label={closeLabel} onClick={close} className="icon">×</button></div>
        {children}
      </div>
    </div>
  );
}
