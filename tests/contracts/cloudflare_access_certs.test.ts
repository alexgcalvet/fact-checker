// Contract · Cloudflare Access · the team key set (<TEAM_DOMAIN>/cdn-cgi/access/certs)
//
// The fake key set of tests/support/access_fake.ts must keep the field names and types of the real one, so the
// Worker's check that passes on the fake also passes on Access. Compares names and types only, never values.
//
// Setup: TEAM_DOMAIN from the person's own terminal (the Worker setting, https://<team>.cloudflareaccess.com).
// Access has no sandbox; the key set is public and read-only. Without TEAM_DOMAIN, or with no answer, it skips.
import { describe, expect, it } from "vitest";
import { keySet } from "../support/access_fake";

const shape = (v: unknown): unknown =>
  Array.isArray(v) ? v.slice(0, 1).map(shape) : v && typeof v === "object"
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, shape(x)])) : typeof v;

// Every field of the fake, with its type, as found in the real answer; extra real fields are fine.
function missing(fake: unknown, real: unknown, path = ""): string[] {
  if (Array.isArray(fake)) return Array.isArray(real) ? missing(fake[0], real[0], `${path}[0]`) : [path];
  if (fake && typeof fake === "object") {
    if (!real || typeof real !== "object") return [path];
    return Object.entries(fake).flatMap(([k, v]) => missing(v, (real as any)[k], path ? `${path}.${k}` : k));
  }
  return fake === real ? [] : [path];
}

describe("contract cloudflare-access · certs", () => {
  it("the real key set has every field of the fake, with the same type", async () => {
    const team = process.env.TEAM_DOMAIN;
    let real: unknown;
    try {
      if (!team) throw new Error("TEAM_DOMAIN not set");
      const res = await fetch(`${team.replace(/\/$/, "")}/cdn-cgi/access/certs`);
      if (!res.ok) throw new Error(String(res.status));
      real = await res.json();
    } catch {
      console.log("SKIP contract cloudflare-access: sandbox not reachable");
      return;
    }
    const bad = missing(shape(await keySet()), shape(real));
    for (const field of bad) console.log(`FAIL contract cloudflare-access: ${field}`);
    expect(bad).toEqual([]);
  });
});
