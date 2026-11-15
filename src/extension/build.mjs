// Builds the loadable extension into the helper package, which ships it to people with no Node.js.
import { build } from "esbuild";
import { cpSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const here = (path) => fileURLToPath(new URL(path, import.meta.url));
export const OUT = here("../helper/fact_checker/extension/");
export const COPIED = ["manifest.json", "_locales", "icons", "fonts"];
export const options = {
  absWorkingDir: here("."),
  entryPoints: ["src/content.ts", "src/sw.ts", "src/guard.ts"],
  bundle: true,
  outdir: `${OUT}dist`,
  target: "chrome120",
};

export const bundle = () => build({ ...options, write: false });

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  rmSync(OUT, { recursive: true, force: true });
  await build(options);
  for (const name of COPIED) cpSync(here(name), OUT + name, { recursive: true });
}
