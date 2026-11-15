// Colour sits only on the verdict: one disc and hue per verdict, grouped in the families of the panel filters.
// The card, the strip marks and the panel rows share it.
import { expect, it } from "vitest";
import { look } from "../../src/extension/src/flags";
import { TEXTS } from "../../src/extension/src/texts";

const FALLACIES = ["ad_hominem", "tu_quoque", "false_dilemma", "straw_man", "false_cause", "hasty_generalization",
  "vague_authority", "insinuation", "double_standard", "cherry_picking", "appeal_to_fear"];
const GROUPS: [string, string[]][] = [
  ["inaccuracy", ["false"]],
  ["inaccuracy", ["misleading", "definition_swap", "plan_as_fact"]],
  ["inaccuracy", ["disputed"]],
  ["fallacy", FALLACIES],
  ["question", ["dodged", "partial"]],
  ["contradiction", ["self", "record", "promise"]],
  ["context", ["person", "case", "event"]],
];
const of = (type: string, label: string) => look({ type, label });

it("labels of one group share their whole look", () => {
  for (const [type, labels] of GROUPS) for (const label of labels) expect(of(type, label)).toEqual(of(type, labels[0]));
});

it("each verdict has its hue: red for false, amber for misleading, magenta for rhetoric, blue for context", () => {
  const hue = (type: string, label: string) => of(type, label).color;
  expect(hue("inaccuracy", "misleading")).toBe(hue("inaccuracy", "disputed"));
  expect(new Set([hue("fallacy", "ad_hominem"), hue("question", "dodged"), hue("contradiction", "self")]).size).toBe(1);
  expect(new Set([hue("inaccuracy", "false"), hue("inaccuracy", "misleading"), hue("fallacy", "ad_hominem"),
    hue("context", "person")]).size).toBe(4);
});

it("misleading and disputed stay in the false family; disputed keeps its word in the text colour", () => {
  expect(of("inaccuracy", "misleading").family).toBe(of("inaccuracy", "false").family);
  expect(of("inaccuracy", "disputed").dot).toBe(of("inaccuracy", "misleading").dot);
  expect(of("inaccuracy", "disputed").word).not.toBe(of("inaccuracy", "misleading").word);
});

it("a nitpick is neutral, whatever its type", () => {
  const nitpick = look({ type: "inaccuracy", label: "false", judge: { verdict: "nitpick", reason: "" } });
  expect(nitpick.family).toBe("Puntualizaciones");
  expect(nitpick.color).not.toBe(of("inaccuracy", "false").color);
});

it("every fallacy has a Spanish name", () => {
  for (const label of FALLACIES) for (const words of Object.values(TEXTS)) expect(words.labels[label]).toBeTruthy();
});
