// @vitest-environment jsdom
// The tab says DeFacto (owner, 2026-11-22)
//
// Story: A reader keeps several tabs open. The home page's tab reads «DeFacto»; every other page names itself first,
// as «Cómo funciona · DeFacto», «Vídeos · DeFacto», or the video's title followed by « · DeFacto».
//
// Setup: the invented collector of the public API tests (tests/support/api_fakes.ts) answers the app's fetch; the web
// app is mounted through its `mount` export at each path.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "../../src/web/src/main";
import { apiCollector } from "../support/api_fakes";
import { FakePlayer } from "../support/youtube_fake";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

async function titleOf(path: string) {
  const { get } = await apiCollector();
  vi.stubGlobal("fetch", (url: string | URL) => get(String(url)));
  history.replaceState(null, "", path);
  document.body.innerHTML = '<div id="root"></div>';
  await act(async () => { await mount(document.getElementById("root")!, FakePlayer as any); });
  return document.title;
}

describe("The tab says DeFacto", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("home → «DeFacto»; other pages → «<page> · DeFacto»", async () => {
    expect(await titleOf("/es/")).toBe("DeFacto");
    expect(await titleOf("/es/videos")).toBe("Vídeos · DeFacto");
    expect(await titleOf("/es/como-funciona")).toBe("Cómo funciona · DeFacto");
    expect(await titleOf("/en/how-it-works")).toBe("How it works · DeFacto");
    expect(await titleOf("/es/v/debate01")).toBe("Debate inventado · DeFacto");
    expect(await titleOf("/es/nada")).toBe("Esta página no existe · DeFacto");
  });
});
