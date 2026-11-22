// @vitest-environment jsdom
// S6 A3 · A reader sends a general correction
//
// Story: A reader follows "Ayúdanos" in the footer and lands on the form at `#feedback`. They pick the step their
// comment is about, write a comment and send it with the bone button; the page says it was sent and reads "Anónimo:
// sin tu nombre, tu correo ni tu IP.". The owner sees it in `/admin`. With no step picked, the button stays disabled.
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers every request of the
// app's fetch; the same stub serves the fake Cloudflare Access key set (tests/support/access_fake.ts). Its newest
// approved video, debate01, names the prompts version of docs/api-examples/prompts.json. Browser storage starts
// empty. The web app is mounted at /es/como-funciona. The form is the element with id "feedback"; the step is picked
// in its one select "¿Sobre qué paso?", whose options are named by the step, and the send button is "Enviar".
// Whenever the question "Compartir tus marcas" shows, the reader answers "Sí". The owner reads /admin/feedback with
// an Access token.
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { HEADER, POLICY_AUD, TEAM_DOMAIN, certsFetch, token } from "../support/access_fake";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";
import PROMPTS from "../../docs/api-examples/prompts.json";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const TEXT = "El paso de juzgar rebaja demasiados avisos";
const settle = () => new Promise((done) => setTimeout(done, 20));

async function collector() {
  const { send, env } = await apiCollector();
  Object.assign(env, { TEAM_DOMAIN, POLICY_AUD });
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
  return root;
}

const question = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Compartir tus marcas"]');
const named = (box: ParentNode, text: string) =>
  [...box.querySelectorAll<HTMLElement>("button")].find((b) => b.textContent!.trim() === text)!;
async function tap(el: HTMLElement) {
  await act(async () => { el.click(); await settle(); });
  const box = question();
  if (box) await act(async () => { named(box, "Sí").click(); await settle(); });
}
async function write(form: HTMLElement, text: string) {
  const box = form.querySelector("textarea")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, text);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("S6 A3 · A reader sends a general correction", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  // Case 1 · the footer's "Ayúdanos" → it links to this page's #feedback, where the form is
  it('Case 1 · the footer\'s "Ayúdanos" → it links to this page\'s #feedback, where the form is', async () => {
    await collector();
    const root = await open();
    const link = [...root.querySelectorAll<HTMLAnchorElement>("footer a")].find((a) => a.textContent === "Ayúdanos")!;
    expect(link.getAttribute("href")).toBe("/es/como-funciona#feedback");
    const form = root.querySelector<HTMLElement>("#feedback")!;
    expect(form.querySelector("textarea")).not.toBeNull();
    expect(form.textContent).toContain("Anónimo: sin tu nombre, tu correo ni tu IP.");
  });

  // Case 2 · a comment with no step picked → "Enviar" stays disabled
  it('Case 2 · a comment with no step picked → "Enviar" stays disabled', async () => {
    await collector();
    const form = (await open()).querySelector<HTMLElement>("#feedback")!;
    await write(form, TEXT);
    expect(form.querySelector("textarea")!.value, "the comment is written").toBe(TEXT);
    expect(named(form, "Enviar")).toHaveProperty("disabled", true);
  });

  // Case 3 · step "Juzgar" picked, a comment sent → the page says it was sent, and /admin lists a prompt comment on judge with the text
  it('Case 3 · step "Juzgar" picked, a comment sent → the page says it was sent, and /admin lists a prompt comment on judge with the text', async () => {
    const { owner } = await collector();
    const form = (await open()).querySelector<HTMLElement>("#feedback")!;
    const step = form.querySelector<HTMLSelectElement>('select[aria-label="¿Sobre qué paso?"]')!;
    expect(step.value, "no step picked at first").toBe("");
    const judge = [...step.options].find((o) => o.textContent === "Juzgar")!;
    await act(async () => {
      step.value = judge.value;
      step.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await write(form, TEXT);
    const send = named(form, "Enviar");
    expect(send.disabled).toBe(false);
    expect(send.classList.contains("bone-button")).toBe(true);
    await tap(send);
    expect(form.textContent).toContain("Enviado");
    expect(form.textContent).toContain("Anónimo: sin tu nombre, tu correo ni tu IP.");
    const rows = await owner("/admin/feedback");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ kind: "prompt", version: PROMPTS.version, component: "judge", rule: null, quote: null, text: TEXT });
  });
});
