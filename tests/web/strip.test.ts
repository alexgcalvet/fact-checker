// Inline 2026-11-22 · The strip of the home card draws one tick per reviewed line (owner, board A7)
//
// Story: A video has 22 reviewed lines, 12 of them with a mark. The strip draws 22 evenly spaced ticks, 12 of them
// amber, in the order of the video: a mark at the start lands near the start, one at the end near the end. Two marks
// that would share a tick take neighbours, so the count of amber ticks always matches the stat.
//
// Setup: the pure function of src/web/src/strip.ts.
import { describe, expect, it } from "vitest";
import { ticks } from "../../src/web/src/strip";

describe("The strip draws one tick per reviewed line", () => {
  it("22 lines, 12 marked → 22 ticks, 12 amber, in time order", () => {
    const marked = [45, 75, 210, 300, 420, 630, 860, 980, 1100, 1210, 1500, 1720];
    const row = ticks(22, marked, 3600);
    expect(row).toHaveLength(22);
    expect(row.filter(Boolean)).toHaveLength(12);
    expect(row[0]).toBe(true);
    expect(row[21]).toBe(false);
  });

  it("marks that crowd one moment still give one amber tick each; never more ticks than lines", () => {
    const row = ticks(5, [100, 100, 100, 100], 1000);
    expect(row.filter(Boolean)).toHaveLength(4);
    expect(ticks(3, [10, 20, 30, 40], 100).filter(Boolean)).toHaveLength(3);
  });
});
