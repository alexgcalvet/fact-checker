import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    root: "../..",
    include: ["tests/acceptance/*.test.ts", "tests/extension/*.test.ts", "tests/collector/*.test.ts"],
    setupFiles: ["tests/support/setup-es.ts"],
  },
});
