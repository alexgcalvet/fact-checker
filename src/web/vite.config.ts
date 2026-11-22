// The app is served from the collector's static assets under /app/ (docs/research/workers-spa-and-rewriter.md).
import { defineConfig } from "vite";

export default defineConfig({
  base: "/app/",
  build: { outDir: "../collector/web/app", emptyOutDir: true },
});
