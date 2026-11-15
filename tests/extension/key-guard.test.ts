// @vitest-environment jsdom
// YouTube listens to keys at the window in the capture phase. The guard registers first (document_start),
// so keys typed in a card's field stop there; keys typed anywhere else still reach YouTube.
import { expect, it } from "vitest";
import "../../src/extension/src/guard";

it("keys in a card field never reach later window listeners; other keys do", () => {
  document.body.innerHTML =
    '<div id="movie_player"><div class="fc-layer"><div class="fc-card"><input id="reason"></div></div><input id="search"></div>';
  const reached: string[] = [];
  window.addEventListener("keydown", (e) => reached.push((e.target as HTMLElement).id), true);
  const press = (id: string) =>
    document.getElementById(id)!.dispatchEvent(new KeyboardEvent("keydown", { key: "k", bubbles: true }));

  press("reason");
  expect(reached).toEqual([]);
  press("search");
  expect(reached).toEqual(["search"]);
});
