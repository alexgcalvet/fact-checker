import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const web = (name: string) => fileURLToPath(new URL(`../web/node_modules/${name}`, import.meta.url));

export default defineConfig({
  // A jsdom test runs in Vite's client environment, which refuses Node built-ins. The web app's tests reach the
  // collector, whose D1 fake needs node:sqlite: the client environment loads modules as the server does.
  environments: { client: { consumer: "server" } },
  // The web app's tests import React from tests/, which has no node_modules: one React, the web app's.
  resolve: { alias: { react: web("react"), "react-dom": web("react-dom") } },
  test: {
    root: "../..",
    include: ["tests/acceptance/*.test.ts", "tests/extension/*.test.ts", "tests/collector/*.test.ts", "tests/contracts/*.test.ts",
      "tests/web/*.test.ts"],
    setupFiles: ["tests/support/setup-es.ts"],
  },
});
