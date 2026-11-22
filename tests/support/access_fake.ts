// Cloudflare Access for the collector tests: one RS256 key pair, its key set at <TEAM_DOMAIN>/cdn-cgi/access/certs,
// and tokens shaped like the `Cf-Access-Jwt-Assertion` header that Access adds after a login. Signed with Node's
// WebCrypto, so the tests do not depend on the Worker's JWT library. The team domain and AUD tag are invented.
import { webcrypto } from "node:crypto";

export const TEAM_DOMAIN = "https://team.example.cloudflareaccess.com";
export const POLICY_AUD = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
export const CERTS = `${TEAM_DOMAIN}/cdn-cgi/access/certs`;
export const HEADER = "Cf-Access-Jwt-Assertion";

const KID = "fake-access-key-1";
const ALGORITHM = { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" };
const pair = () => webcrypto.subtle.generateKey(ALGORITHM, true, ["sign", "verify"]) as Promise<webcrypto.CryptoKeyPair>;

// One key pair per test file: a Worker that caches the key set keeps working across the cases.
const team = pair();
// Another key under the same kid: a token signed by it must fail on its signature, not on a missing key.
const stranger = pair();

export async function keySet() {
  const { n, e } = await webcrypto.subtle.exportKey("jwk", (await team).publicKey);
  return { keys: [{ kid: KID, kty: "RSA", alg: "RS256", use: "sig", e, n }] };
}

const base64url = (data: string | Uint8Array) => Buffer.from(data).toString("base64url");

/** A token as Access issues it after the owner's login; `claims` overrides any claim, `signer: "stranger"` signs it
 * with a key outside the key set. */
export async function token(claims: Record<string, unknown> = {}, signer: "team" | "stranger" = "team") {
  const now = Math.floor(Date.now() / 1000);
  const header = base64url(JSON.stringify({ alg: "RS256", kid: KID, typ: "JWT" }));
  const payload = base64url(JSON.stringify({
    aud: [POLICY_AUD], email: "owner@example.com", exp: now + 3600, iat: now, nbf: now, iss: TEAM_DOMAIN,
    type: "app", identity_nonce: "nonce", sub: "00000000-0000-4000-8000-000000000000", country: "ES", ...claims,
  }));
  const key = (await (signer === "team" ? team : stranger)).privateKey;
  const signature = await webcrypto.subtle.sign(ALGORITHM.name, key, new TextEncoder().encode(`${header}.${payload}`));
  return `${header}.${payload}.${base64url(new Uint8Array(signature))}`;
}

/** A `fetch` that serves the key set at CERTS and 404 elsewhere; `urls` records every URL asked. */
export function certsFetch() {
  const urls: string[] = [];
  const fetch = async (input: string | URL | Request) => {
    const url = input instanceof Request ? input.url : String(input);
    urls.push(url);
    return url === CERTS
      ? new Response(JSON.stringify(await keySet()), { headers: { "Content-Type": "application/json" } })
      : new Response("not found", { status: 404 });
  };
  return { fetch, urls };
}
