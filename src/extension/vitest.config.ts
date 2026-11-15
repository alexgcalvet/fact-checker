import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    root: "../..",
    include: ["tests/acceptance/*.test.ts", "tests/extension/*.test.ts"],
    setupFiles: ["tests/extension/setup-es.ts"],
  },
});
