// A guest's image is cut from the video's YouTube thumbnail (spec S11): the viewer's face, the 4:5 plate and the
// profile's cover read this one rule.
import { useState } from "react";

export type Half = "left" | "right";

/** A guest's half of the thumbnail: in a debate of two, the first guest is the left half and the second the right,
 * unless the owner swapped them in /admin; with one guest, or three or more, null (the whole thumbnail). */
export function half(guests: string[], name: string, swap?: boolean): Half | null {
  const i = guests.length === 2 ? guests.indexOf(name) : -1;
  return i < 0 ? null : (i === 0) !== Boolean(swap) ? "left" : "right";
}

// From YouTube's image host, which allows any origin, so a PNG can draw it: maxres, else hq. A missing maxres comes
// back as a 120 px placeholder, not an error.
const THUMBS = ["maxresdefault", "hqdefault"];

/** The thumbnail's address and the events that try the next size; `src` is null when none loads. */
export function useThumb(video: string) {
  const [tried, setTried] = useState(0);
  const next = () => setTried((n) => n + 1);
  return {
    src: tried < THUMBS.length ? `https://i.ytimg.com/vi/${encodeURIComponent(video)}/${THUMBS[tried]}.jpg` : null,
    onError: next,
    onLoad: (e: { currentTarget: HTMLImageElement }) => { if (e.currentTarget.naturalWidth <= 120) next(); },
  };
}
