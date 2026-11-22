// The strip of the home card (board A7, owner 2026-11-22): one tick per reviewed line, evenly spaced, amber where the
// line has a mark. The collector keeps the second of each marked line but not of the lines checked with no mark, so a
// marked tick sits where its second falls in the video, and the others fill the rest.

/** `lines` ticks, true where marked: each mark at its place in the video (seconds `marked` of `duration`), or the
 * nearest free tick, so the amber count always equals the marks shown (at most `lines`). */
export function ticks(lines: number, marked: number[], duration: number): boolean[] {
  const row: boolean[] = Array(lines).fill(false);
  for (const t of [...marked].sort((a, b) => a - b).slice(0, lines)) {
    const at = Math.min(lines - 1, Math.floor((t / duration) * lines));
    let i = at;
    while (i < lines && row[i]) i++;
    if (i === lines) for (i = at; row[i]; i--);
    row[i] = true;
  }
  return row;
}
