// @vitest-environment jsdom
// S6 A2 · A reader comments on a rule of the instructions
//
// Story: In "Las instrucciones" the reader sees the version of the newest approved analysis's prompts and one closed
// block per component. They open "judge", select words of one of its rules, press "Comentar esta frase", accept the
// consent once, write "Esta regla es demasiado estricta" and send it. The owner sees in /admin a prompt comment with
// that version, component, rule, the selected words and the text.
// Owner review 2026-11-21: "Comentar esta frase" is now a small "Comentar" beside the selection ("Comentar la selección").
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch; the same stub serves the fake Cloudflare Access key set (tests/support/access_fake.ts). The fake
// prompts file has no judge rules, so the owner also approves a newer invented debate, debate02 (2026-11-15), whose
// prompts file (version 0.2.0+<hash of its components>) gives "judge" two rules: "keep_doubt" and "materiality".
// Browser storage starts empty. The web app is mounted at /es/como-funciona. The instructions are the page's
// "#instrucciones" section, one <details> per component, named by its id in the <summary>. Whenever the question
// "Compartir tus marcas" shows, the reader answers "Sí". The owner reads /admin/feedback with an Access token.
import { createHash } from "node:crypto";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector, debateEs } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";
import PROMPTS from "../../docs/api-examples/prompts.json";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const TEXT = "Esta regla es demasiado estricta";
const WORDS = "the substance of a figure holds";
const RULES = [
  { id: "keep_doubt", text: "- When in doubt, keep the flag." },
  { id: "materiality", text: "- If the substance of a figure holds and the error is small, rule nitpick." },
];
const COMPONENTS = PROMPTS.components.map((c) => c.id !== "judge" ? c
  : { ...c, text: `${c.text}\n\n${RULES.map((r) => r.text).join("\n")}`, rules: RULES });
const VERSION = `0.2.0+${createHash("sha256").update(JSON.stringify(COMPONENTS)).digest("hex").slice(0, 12)}`;
const settle = () => new Promise((done) => setTimeout(done, 20));

async function collector() {
  const { send, env } = await apiCollector();
  Object.assign(env, { TEAM_DOMAIN, POLICY_AUD });
  const analysis = { ...debateEs, video_id: "debate02", published_at: "2026-11-15", helper_version: VERSION };
  const put = await send(`/analyses/debate02?lang=es`, {
    method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer admin-secret" },
    body: JSON.stringify({ install_id: "00000000-0000-4000-8000-000000000000", analysis, prompts: { version: VERSION, components: COMPONENTS } }),
  });
  expect([200, 201]).toContain(put.status);
  const keys = certsFetch();
  vi.stubGlobal("fetch", (url: string | URL, init?: RequestInit) =>
    String(url).startsWith(TEAM_DOMAIN) ? keys.fetch(String(url)) : send(String(url), init));
  const owner = async (path: string) => {
    const res = await send(path, { headers: { [HEADER]: await token() } });
    expect(res.status).toBe(200);
    return (await res.json()).rows as Record<string, unknown>[];
  };
  return { owner };
}

async function open() {
  history.replaceState(null, "", "/es/como-funciona");
  document.body.innerHTML = '<div id="app"></div>';
  const root = document.getElementById("app")!;
  await act(async () => { await mount(root, FakePlayer as any); await settle(); });
  return root.querySelector<HTMLElement>("#instrucciones")!;
}

const question = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Compartir tus marcas"]');
const named = (box: ParentNode, text: string) =>
  [...box.querySelectorAll<HTMLElement>("button")].find((b) => b.textContent!.trim() === text);
const blocks = (section: HTMLElement) => [...section.querySelectorAll<HTMLDetailsElement>("details")];
const block = (section: HTMLElement, id: string) =>
  blocks(section).find((d) => d.querySelector("summary")!.textContent!.includes(id))!;
let asked = 0;
async function tap(el: HTMLElement) {
  await act(async () => { el.click(); await settle(); });
  const box = question();
  if (box) {
    asked += 1;
    await act(async () => { named(box, "Sí")!.click(); await settle(); });
  }
}
// Selects `words` inside the element of the judge block that holds them, as a reader's drag does.
async function select(judge: HTMLElement, words: string) {
  const el = [...judge.querySelectorAll<HTMLElement>("*")].find((e) => e.children.length === 0 && e.textContent!.includes(words))!;
  const node = el.firstChild!;
  const at = node.textContent!.indexOf(words);
  const range = document.createRange();
  range.setStart(node, at);
  range.setEnd(node, at + words.length);
  await act(async () => {
    getSelection()!.removeAllRanges();
    getSelection()!.addRange(range);
    document.dispatchEvent(new Event("selectionchange"));
    el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await settle();
  });
}
async function write(section: HTMLElement, text: string) {
  const box = section.querySelector("textarea")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, text);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function comment(section: HTMLElement, words: string, text: string) {
  const judge = block(section, "judge");
  if (!judge.open) await act(async () => { judge.querySelector("summary")!.click(); });
  await select(judge, words);
  await tap(section.querySelector<HTMLElement>('[aria-label="Comentar la selección"]')!);
  await write(section, text);
  await tap(named(section, "Enviar")!);
}

describe("S6 A2 · A reader comments on a rule of the instructions", () => {
  beforeEach(() => {
    localStorage.clear();
    asked = 0;
  });
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the instructions → the newest approved version, and one closed block per component
  it("Case 1 · the instructions → the newest approved version, and one closed block per component", async () => {
    await collector();
    const section = await open();
    expect(section.textContent).toContain(VERSION);
    const all = blocks(section);
    expect(all.map((d) => d.querySelector("summary")!.textContent)).toEqual(
      COMPONENTS.map((c) => expect.stringContaining(c.id)));
    expect(all.every((d) => !d.open)).toBe(true);
    expect(section.querySelector('[aria-label="Comentar la selección"]')).toBeNull();
  });

  // Case 2 · words of a judge rule selected, commented and sent → /admin lists one prompt comment with version, component, rule, quote and text
  it("Case 2 · words of a judge rule selected, commented and sent → /admin lists one prompt comment with version, component, rule, quote and text", async () => {
    const { owner } = await collector();
    await comment(await open(), WORDS, TEXT);
    const rows = await owner("/admin/feedback");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ kind: "prompt", version: VERSION, component: "judge", rule: "materiality", quote: WORDS, text: TEXT });
  });

  // Case 3 · two comments → the consent is asked once, and both reach /admin
  it("Case 3 · two comments → the consent is asked once, and both reach /admin", async () => {
    const { owner } = await collector();
    const section = await open();
    await comment(section, WORDS, TEXT);
    await comment(section, "keep the flag", "Otra");
    expect(asked).toBe(1);
    const rows = await owner("/admin/feedback");
    expect(rows.map((r) => [r.rule, r.quote])).toEqual(expect.arrayContaining([["materiality", WORDS], ["keep_doubt", "keep the flag"]]));
  });
});
