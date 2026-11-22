# Workers Caching for the public API (2026-11-20)

Sources, read 2026-11-20 through the Cloudflare docs search:
- [Workers Cache](https://developers.cloudflare.com/workers/cache/)
- [Configuration](https://developers.cloudflare.com/workers/cache/configuration/), [Cache keys](https://developers.cloudflare.com/workers/cache/cache-keys/), [Limitations](https://developers.cloudflare.com/workers/cache/limitations/), [Debugging](https://developers.cloudflare.com/workers/cache/debugging/), [Examples](https://developers.cloudflare.com/workers/cache/examples/)
- [Cache API](https://developers.cloudflare.com/workers/runtime-apis/cache/)

## Conclusion

- Cache the public API with **Workers Caching** on its own entrypoint. Keep caching off on the default entrypoint, which serves `/admin*`, `/marks` and `/analyses*`.
- Do not use the Cache API (`caches.default`) on this Worker.

## Workers Caching

| Item | Contract |
|---|---|
| What | Cloudflare returns a cached response without running the Worker. The cache belongs to the Worker, not to a zone, so it works on `workers.dev` |
| Turn on | `[cache] enabled = true` in wrangler (Wrangler ≥ 4.69.0). It can be turned off per entrypoint: `[exports.default.cache] enabled = false` |
| Per entrypoint | The documented pattern is a default entrypoint with cache off that forwards to a named `WorkerEntrypoint` with cache on, through `ctx.exports.<Name>.fetch(request)` |
| Freshness | The Worker's `Cache-Control` header, per RFC 9111. Example: `public, max-age=60` |
| No header | **A 200 response is still cached, for 2 hours, and a 404 for 3 minutes.** Leaving out `Cache-Control` does not opt out. Use `no-store` or `private` to opt out |
| Bypass | The response has `Set-Cookie`; the request has `Authorization`, unless the response says `public`, `must-revalidate` or `s-maxage`; the response says `private` or `no-store` |
| Methods | Only `GET` and `HEAD`. Every other method runs the Worker |
| Key | The path and query, the entrypoint, `ctx.props`, and the Worker version by default, not the host. A deploy starts a fresh cache |
| Purge | `ctx.cache.purge()`, `ctx.cache.invalidate()`, the `Cache-Tag` header |
| Check | `Cf-Cache-Status` on the response. Two requests to the same URL give `MISS`, then `HIT` |
| Local tests | Vitest does not exercise the cache. Check it on a deployed Worker |

## Cache API (`caches.default`), rejected

- It works on Workers with custom domains. It is not available for Workers fronted by Cloudflare Access.
- It caches only what the Worker `put()`s. Every request still runs the Worker.
- It is local to one data center and has no tiered cache.
