# Workers static assets for many paths, and HTMLRewriter for share meta (2026-11-21)

Sources (Cloudflare docs, read 2026-11-21 through the Cloudflare docs search):
- [Static Assets, routing behavior](https://developers.cloudflare.com/workers/static-assets/#routing-behavior)
- [Configuration and bindings: `run_worker_first`, `fetch()`](https://developers.cloudflare.com/workers/static-assets/binding/)
- [Wrangler configuration, `assets`](https://developers.cloudflare.com/workers/wrangler/configuration/#assets)
- [Single Page Application, advanced routing control](https://developers.cloudflare.com/workers/static-assets/routing/single-page-application/#advanced-routing-control)
- [HTML handling](https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/)
- [Worker script first](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/)
- [SPA shell example, "Set meta tags"](https://developers.cloudflare.com/workers/examples/spa-shell/)
- [HTMLRewriter](https://developers.cloudflare.com/workers/runtime-apis/html-rewriter/)

## Conclusion

- The Worker serves the app for `/`, `/es/*` and `/en/*` by adding them to `run_worker_first`. The other paths keep their routes.
- For an app path, the Worker fetches the app's HTML through the `ASSETS` binding and rewrites its share meta with `HTMLRewriter`. Nothing else is needed: no server rendering and no SPA fallback.
- Fetch the HTML by its folder path (`/app/`), never by `/app/index.html`: the binding applies `html_handling`, and the default answers `/app/index.html` with a 307 redirect.

## Contract 1: one HTML for many paths

| Rule | Source |
|---|---|
| A request that matches an asset gets the file, without the Worker, unless a `run_worker_first` pattern matches it | Static Assets, routing behavior |
| `run_worker_first` takes `true` or a list of patterns: each starts with `/` or `!/`, `*` is a deep glob, a `!` pattern wins over a positive one, order does not matter, at most 100 entries | Configuration and bindings; Wrangler configuration |
| A list of patterns turns off the automatic `Sec-Fetch-Mode: navigate` routing; only the list decides when the Worker runs | SPA, advanced routing control |
| `env.ASSETS.fetch(request | URL | string)` uses only the pathname (any host works) and applies `html_handling` and `not_found_handling` | Configuration and bindings, `fetch()` |
| Default `html_handling` is `auto-trailing-slash`: `/folder/` gives `folder/index.html` with 200; `/folder` and `/folder/index.html` give a 307 to `/folder/` | HTML handling |
| `not_found_handling = "single-page-application"` answers a path with no asset with the root `/index.html` and 200 | Static Assets, routing behavior |

For this project:
- The app's build sits in `src/collector/web/app/` (ARCHITECTURE Repo layout), so its HTML is `/app/index.html` and its bundles are under `/app/`. Vite's `base` is `/app/`. The bundles are assets and skip the Worker.
- `run_worker_first` becomes `["/", "/es/*", "/en/*", "/admin*", "/api/*", "/try/*"]`. The Worker answers `/` with a redirect to `/es/` or `/en/`, and `/es/*`, `/en/*` with `ASSETS.fetch("/app/")` plus the rewrite.
- `not_found_handling` stays `none`: the root has no `index.html`, and an unknown path keeps its 404.

## Contract 2: share meta with HTMLRewriter

| Rule | Source |
|---|---|
| `new HTMLRewriter().on(selector, handler).transform(response)` streams a response and runs the handler on each matching element | HTMLRewriter |
| An element handler can read and set attributes (`getAttribute`, `setAttribute`) and insert content (`append`, `prepend`, `replace`, `setInnerContent`) | HTMLRewriter; Rewrite links example |
| Inserted content is text and is HTML-escaped unless `{ html: true }` is passed | HTMLRewriter, `ContentOptions` |
| Handlers may be `async`, so a handler can read D1 before it writes | HTMLRewriter, async handlers |
| Cloudflare's own example sets Open Graph tags on a SPA shell this way, "without a full server-side rendering framework" | SPA shell example, "Set meta tags" |

For this project:
- The app's `index.html` carries the share tags with neutral values: `<title>`, `og:title`, `og:image`, `og:url`, `twitter:card`. The Worker sets `content` with `setAttribute` and the title with `setInnerContent` (text, escaped).
- The title comes from the stored analysis of that video and language (the API already serves it, `docs/api-examples/debate.json`). The image is the YouTube thumbnail of the video id; its URL form is the YouTube embed research's to state, and S1 confirms it. A video that is not approved keeps the neutral tags.

## Not stated by the docs

- Whether `setAttribute` escapes quotes in the value. S1 tests a title with `"` and `<` through the Worker.
