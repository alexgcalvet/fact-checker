// The panel logic that the extension and the web app share, with no DOM.

/** The flags in the order the video says them. */
export const inOrder = <T extends { t: number }>(flags: T[]): T[] => [...flags].sort((a, b) => a.t - b.t);

/** The flag lit at second `now`: the last one already said. `flags` are in order. */
export const litAt = <T extends { t: number }>(flags: T[], now: number): T | undefined =>
  flags.filter((f) => f.t <= now).pop();
