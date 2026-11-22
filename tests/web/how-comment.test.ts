// @vitest-environment jsdom
// How it works: commenting is easy to find (owner, 2026-11-21)
//
// Story: On /es/como-funciona every rule of the instructions shows a "Comentar" button; pressing it opens the comment
// box for that rule, with no quote, and the owner sees the comment with its rule and no quote. A quiet "Ayúdanos ↓"
// under the lede and the loop's "Tú das feedback" box both lead to the form at #feedback. The prompt text reads as prose:
// a rule written on two lines is one paragraph, and a block shows "N reglas" only when it has rules.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts), with debate02 uploaded under a
// prompts version whose judge component carries three invented rules, one of them on two lines; the same stub serves
// the fake Cloudflare Access key set. Browser storage starts empty; the consent question is answered "Sí".
import { createHash } from "node:crypto";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector, debateEs } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";
import PROMPTS from "../../docs/api-examples/prompts.json";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const RULES = [
  { id: "keep_doubt", text: "- When in doubt, keep the flag." },
  { id: "materiality", text: "- If the substance of a figure holds and the error is small, rule nitpick." },
  { id: "scope", text: "- Read the whole sentence and the ones around it\n  before you decide." }, // a rule on two lines
];
const COMPONENTS = PROMPTS.components.map((c) => c.id !== "judge" ? c
  : { ...c, text: `${c.text}\n\n${RULES.map((r) => r.text).join("\n")}`, rules: RULES });
const VERSION = `0.2.0+${createHash("sha256").update(JSON.stringify(COMPONENTS)).digest("hex").slice(0, 12)}`;
const TEXT = "Esta regla sobra";
const settle = () => new Promise((done) => setTimeout(done, 20));

async function open() {
  const { send, env } = await apiCollector();
  Object.assign(env, { TEAM_DOMAIN, POLICY_AUD });
  const analysis = { ...debateEs, video_id: "debate02", published_at: "2026-11-15", helper_version: VERSION };
  await send("/analyses/debate02?lang=es", {
    method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer admin-secret" },
    body: JSON.stringify({ install_id: "00000000-0000-4000-8000-000000000000", analysis, prompts: { version: VERSION, components: COMPONENTS } }),
  });
  const keys = certsFetch();
  vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) =>
    String(url).startsWith(TEAM_DOMAIN) ? keys.fetch(String(url)) : send(String(url), init));
  history.replaceState(null, "", "/es/como-funciona");
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(async () => { await mount(root, FakePlayer as any); await settle(); });
  const owner = async () => (await (await send("/admin/feedback", { headers: { [HEADER]: await token() } })).json()).rows;
  return { root, owner };
}
const named = (box: ParentNode, text: string) =>
  [...box.querySelectorAll<HTMLElement>("button")].filter((b) => b.textContent!.trim() === text);
async function tap(el: HTMLElement) {
  await act(async () => { el.click(); await settle(); });
  const box = document.querySelector<HTMLElement>('[role="dialog"][aria-label="Compartir tus marcas"]');
  if (box) await act(async () => { named(box, "Sí")[0].click(); await settle(); });
}

describe("How it works: commenting is easy to find", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the judge's three rules → one "Comentar" each; one pressed and sent → a prompt comment on that rule, no quote
  it("Case 1 · «Comentar» on the materiality rule, sent → /admin lists a prompt comment on that rule with no quote", async () => {
    const { root, owner } = await open();
    const judge = root.querySelector<HTMLElement>('details[data-component="judge"]')!;
    expect(named(judge, "Comentar")).toHaveLength(RULES.length);
    const rule = judge.querySelector<HTMLElement>('[data-rule="materiality"]')!;
    await act(async () => { named(rule, "Comentar")[0].click(); });
    const box = judge.querySelector("textarea")!;
    expect(judge.textContent).not.toContain("«");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, TEXT);
      box.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await tap(named(judge, "Enviar")[0]);
    const rows = await owner();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ kind: "prompt", version: VERSION, component: "judge", rule: "materiality", quote: null, text: TEXT });
  });

  // Case 2 · the hero and the loop → «Ayúdanos ↓» and «Tú das feedback» link to #feedback, and the form is there
  it("Case 2 · «Ayúdanos ↓» under the lede and the «Tú das feedback» box → both link to #feedback", async () => {
    const { root } = await open();
    const links = [...root.querySelectorAll<HTMLAnchorElement>('a[href="#feedback"]')].map((a) => a.textContent!.trim());
    expect(links).toContain("Ayúdanos ↓");
    expect(links.some((l) => l.includes("Tú das feedback"))).toBe(true);
    expect(root.querySelector("#feedback textarea")).not.toBeNull();
    expect(root.querySelectorAll(".how .bone-button")).toHaveLength(1);
  });

  // Case 3 · the prompt text → prose: a rule on two lines reads as one paragraph; a block with no rules shows no count
  it("Case 3 · a rule on two lines → one paragraph; «N reglas» only where N > 0, never «0 reglas»", async () => {
    const { root } = await open();
    const scope = root.querySelector<HTMLElement>('[data-rule="scope"]')!;
    expect([...scope.querySelectorAll("p")].map((p) => p.textContent))
      .toEqual(["- Read the whole sentence and the ones around it before you decide."]);
    const counts = [...root.querySelectorAll("summary")].map((s) => s.textContent!);
    expect(counts.find((c) => c.includes("judge"))).toContain("3 reglas");
    expect(counts.join(" ")).not.toContain("0 reglas");
  });
});
