// S25 FR-001 · The extension that the helper package ships is a fresh `npm run build` of src/extension.
// If this fails, run `npm run build` in src/extension and commit the result.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
// @ts-expect-error: a plain ES module with no types
import { bundle, COPIED, OUT } from "../../src/extension/build.mjs";

const SOURCE = join(__dirname, "../../src/extension");
const files = (root: string, name: string): string[] =>
  statSync(join(root, name)).isDirectory()
    ? readdirSync(join(root, name)).flatMap((child) => files(root, join(name, child)))
    : [name];

describe("the packaged extension", () => {
  it("holds the scripts of a fresh build", async () => {
    const result = await bundle();
    for (const file of result.outputFiles) expect(readFileSync(file.path, "utf8"), file.path).toBe(file.text);
  });

  it("holds the manifest, icons and fonts of src/extension", () => {
    for (const name of COPIED.flatMap((n: string) => files(SOURCE, n)))
      expect(readFileSync(join(OUT, name)).equals(readFileSync(join(SOURCE, name))), name).toBe(true);
  });
});
