// Inline 2026-11-22 · The DeFacto mark turns like a lighthouse (owner; logo-spec.md §2, board «DeFacto · El faro»)
//
// Story: The F's arms turn in two smooth half turns with a short hold at 180°, where the mark reads «DE FACTO». Every
// other layer follows the angle: the beam shows on the way out and dies before it would cross ACTO, the halo flashes
// when the light faces the reader (90°), the arms dim while they come back foreshortened, and ACTO steps right while
// the F faces it. The large mark takes 4.5 s with a 0.5 s hold; the header 3.0 s with a 0.3 s hold.
//
// Setup: the pure functions of src/web/src/turn.ts.
import { describe, expect, it } from "vitest";
import { angle, arms, beam, glow, keyframes, LARGE, SMALL, shift } from "../../src/web/src/turn";

describe("The DeFacto mark turns like a lighthouse", () => {
  it("two sine half turns with a hold at 180°", () => {
    for (const timing of [LARGE, SMALL]) {
      const half = (1 - timing.hold / timing.dur) / 2;
      expect(angle(timing, 0)).toBe(0);
      expect(angle(timing, half / 2)).toBeCloseTo(90, 5);
      expect(angle(timing, half + 0.001)).toBe(180);
      expect(angle(timing, 1)).toBeCloseTo(360, 5);
    }
    expect([LARGE.dur, LARGE.hold, SMALL.dur, SMALL.hold]).toEqual([4.5, 0.5, 3.0, 0.3]);
  });

  it("each layer follows the angle", () => {
    expect(beam(0)).toBeCloseTo(0, 5);
    expect(beam(90)).toBeGreaterThan(0.3);
    expect(beam(180)).toBe(0);
    expect(beam(320)).toBeCloseTo(0.18, 5);
    expect(glow(90).opacity).toBeCloseTo(0.9, 5);
    expect(glow(90).scale).toBe(1.45);
    expect(glow(0).opacity).toBeCloseTo(0.4, 5);
    expect(arms(325)).toBeCloseTo(0.35, 5);
    expect(arms(100)).toBe(1);
    expect(shift(180)).toBe(1);
    expect(shift(0)).toBe(0);
    expect(shift(360)).toBeCloseTo(0, 5);
  });

  it("keyframes sample the turn in about 90 linear steps", () => {
    const css = keyframes("df-spin-l", LARGE, (a) => `transform:rotateY(${a.toFixed(2)}deg)`);
    expect(css.startsWith("@keyframes df-spin-l{0.00%{transform:rotateY(0.00deg)}")).toBe(true);
    expect(css.match(/%\{/g)).toHaveLength(91);
    expect(css).toContain("100.00%{transform:rotateY(360.00deg)}");
  });
});
