# Cloudflare Access and Workers static assets (2026-11-20)

Sources, read 2026-11-20 through the Cloudflare docs search:
- [Workers › Cloudflare Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/)
- [Validate JWTs](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)
- [Application paths](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/)
- [Self-hosted public application](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)
- [workers.dev](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/)
- [Static assets](https://developers.cloudflare.com/workers/static-assets/), [Assets binding](https://developers.cloudflare.com/workers/static-assets/binding/), [Wrangler configuration › assets](https://developers.cloudflare.com/workers/wrangler/configuration/)

## Conclusion

- Protect `/admin` with a **path-based self-hosted Access application**, not the one-click Worker switch: the switch protects every route of the Worker, and the helpers would lose `/marks` and `/analyses`.
- The Worker checks the **`Cf-Access-Jwt-Assertion` header** itself (signature, issuer, audience). It cannot rely on `ctx.access` once the Worker has static assets.
- Serve the test page as **static assets** of the same Worker, with `run_worker_first` on the API routes.

## Access: what to protect

| Option | Covers | Fit |
|---|---|---|
| Worker-level Access (Worker › Access, or Domains › Enable Cloudflare Access) | every route, Custom Domain, `workers.dev` hostname and preview of the Worker | no: blocks the helpers' routes |
| Hostname or path-based self-hosted application | "only that exact URL", for example "`my-worker.example.workers.dev` … or a single path such as `example.com/login`" | yes: `/admin` and `/admin/*` only |

- A more specific rule wins: a path application applies before a Worker-level one.
- **Observed 2026-11-20 (S0 T004):** the dashboard accepts a `workers.dev` host with a path through **Switch to custom input** (`<worker>.<subdomain>.workers.dev/admin` and `/admin/*`). `/admin` and `/admin/x` answer 302 to the team login; `/analyses` answers the Worker's own 401 with no login. The formatted input asks for a zone of the account and does not list `workers.dev`.
- The login page offers every identity provider of the account, including sign-in with the Cloudflare account; the policy still checks the email.
- Paths take one `*` wildcard between slashes. Query strings and ports are not matched.
- Policies are deny by default: an Allow rule with the owner's email is the only way in.
- Zero Trust must be turned on for the account (free plan).

## Access: what the Worker receives and checks

| Item | Contract |
|---|---|
| Header | `Cf-Access-Jwt-Assertion: <JWT>` on each request that passed Access; a browser also gets the `CF_Authorization` cookie. Validate the header, not the cookie |
| Keys | `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs` (JWKS, RS256) |
| Checks | signature against those keys; `iss` equals `https://<team>.cloudflareaccess.com`; `aud` contains the application's AUD tag; `exp` and `nbf` valid. Never trust a key URL taken from the token |
| Settings | `TEAM_DOMAIN` and `POLICY_AUD` (the AUD tag, under Access › Applications › Edit › Additional settings; it changes only if the application is recreated) |
| Library | `jose`: `createRemoteJWKSet` + `jwtVerify(token, jwks, {issuer, audience})` |
| `ctx.access` | `ctx.access.getIdentity()` gives the email with no JWT code, **but** a Worker with static assets runs behind a router that does not pass `ctx.access`. Use the header |
| Local tests | `[access.dev]` in wrangler fakes `ctx.access` only; the header check needs its own fake JWT and key set (`tests/support/`) |

## Static assets beside the Worker routes

| Item | Contract |
|---|---|
| Config | `[assets] directory = "<dir>"`, `binding = "ASSETS"` (optional, gives `env.ASSETS.fetch(request)`) |
| Default routing | a path that matches a file is served **without running the Worker**; any other path runs the Worker |
| `run_worker_first` | `true` runs the Worker for every request; or a list of patterns such as `["/api/*", "/admin*"]`, with `!` for exceptions; at most 100 entries |
| `not_found_handling` | `"none"` (default), `"404-page"` or `"single-page-application"` |
| Count | one assets folder per Worker |
| Cost | static asset requests are free and unlimited (checked earlier in the RFC research) |

## Consequences for the specs

- S1: `/admin` HTML and its API calls run in the Worker after the JWT check; the owner's helper keeps `ADMIN_TOKEN` for the CLI routes.
- S3: `/try/<id>` is one static file plus a Worker route or `html_handling`; keep `/api/*`, `/marks`, `/analyses*` and `/admin*` in `run_worker_first`, so a file never shadows a route.
