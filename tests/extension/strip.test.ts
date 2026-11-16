// @vitest-environment jsdom
// The strip under the video: a mark per flag, the analysed part, and a jump to a flag.
import { describe, expect, it } from "vitest";
import { mountOverlay } from "../../src/extension/src/overlay";
import { mountPanel, TYPE_COLOR } from "../../src/extension/src/panel";

// S11 A1 · Every flag has a mark at its second on a strip under the video
//
// Story: On a page that mimics the YouTube player, a 100-second video has three flags at seconds 10, 50 and 90,
// one of them under the bar. The strip under the video shows three marks, at 10 %, 50 % and 90 % of its width,
// each with the color of its type.
//
// Setup: a jsdom page with a player element and a video element whose duration is 100 seconds; the overlay
// and the panel are mounted as the content script mounts them, with a fixed flag file of three flags: a fallacy
// at second 10, an inaccuracy under the bar at second 50 and a contradiction at second 90.
{
  const flag = (id: string, t: number, type: string, label: string, onPlayer: boolean) => ({
    id, t, speaker: "Invitado", quote: `frase ${t}`, type, label, reason: "Motivo.", confidence: 0.85,
    on_player: onPlayer, related: null, sources: [], note: null,
  });
  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [
      flag("fallacy-10.0", 10, "fallacy", "ad_hominem", true),
      flag("inaccuracy-50.0", 50, "inaccuracy", "false", false),
      flag("contradiction-90.0", 90, "contradiction", "self", true),
    ],
  } as any;

  function marks() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show);
    return [...player.querySelectorAll<HTMLElement>(".fc-strip .fc-mark")];
  }

  /** The color as the browser reports it, so "#f5a623" and "rgb(245, 166, 35)" compare equal. */
  function computed(color: string) {
    const probe = document.createElement("div");
    probe.style.backgroundColor = color;
    return probe.style.backgroundColor;
  }

  describe("S11 A1 · Every flag has a mark at its second on a strip under the video", () => {
    // Case 1 · three flags on a 100-second video → three marks at 10 %, 50 % and 90 % of the strip
    it("Case 1 · three flags on a 100-second video → three marks at 10 %, 50 % and 90 %", () => {
      const found = marks();
      expect(found.length).toBe(3);
      expect(found.map((m) => parseFloat(m.style.left)).sort((a, b) => a - b)).toEqual([10, 50, 90]);
    });

    // Case 2 · each mark → the color of its flag's type
    it("Case 2 · each mark → the color of its flag's type", () => {
      const byLeft = Object.fromEntries(marks().map((m) => [parseFloat(m.style.left), m.style.backgroundColor]));
      expect(new Set([byLeft[10], byLeft[50], byLeft[90]]).size).toBe(3);
      expect(byLeft[10]).not.toBe("");
      expect(byLeft[10]).toBe(computed(TYPE_COLOR.fallacy));
      expect(byLeft[50]).toBe(computed(TYPE_COLOR.inaccuracy));
      expect(byLeft[90]).toBe(computed(TYPE_COLOR.contradiction));
    });

    // Case 3 · the flag under the bar → a thinner mark than the shown flags
    it("Case 3 · the flag under the bar → a thinner mark than the shown flags", () => {
      const width = Object.fromEntries(marks().map((m) => [parseFloat(m.style.left), parseFloat(m.style.width)]));
      expect(width[50]).toBeLessThan(width[10]);
      expect(width[50]).toBeLessThan(width[90]);
    });
  });
}

// S11 A3 · A click on a mark or a row jumps to the flag
//
// Story: On the same page, the person clicks the mark at 50 %. The video jumps to second 50 and the card of
// that flag shows, also if the flag is under the bar. A click on the row of the flag at second 90 jumps there
// the same way.
//
// Setup: a jsdom page with a player element and a 100-second video at second 0; the overlay and the panel are
// mounted as the content script mounts them, with a fixed flag file of three flags: a fallacy at second 10, an
// inaccuracy under the bar at second 50 and a contradiction at second 90.
{
  const flag = (id: string, t: number, type: string, label: string, onPlayer: boolean) => ({
    id, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type, label, reason: "Motivo.", confidence: 0.85,
    on_player: onPlayer, related: null, sources: [], note: null,
  });
  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [
      flag("fallacy-10.0", 10, "fallacy", "ad_hominem", true),
      flag("inaccuracy-50.0", 50, "inaccuracy", "false", false),
      flag("contradiction-90.0", 90, "contradiction", "self", true),
    ],
  } as any;

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show);
    const cards = () => [...player.querySelectorAll<HTMLElement>(".fc-card")].map((c) => c.textContent!);
    return { player, video, cards };
  }

  describe("S11 A3 · A click on a mark or a row jumps to the flag", () => {
    // Case 1 · click on the mark at 50 % → the video is at second 50 and the card of the flag under the bar shows
    it("Case 1 · click on the mark at 50 % → second 50 and the card of the flag under the bar", () => {
      const { player, video, cards } = page();
      const mark = [...player.querySelectorAll<HTMLElement>(".fc-mark")].find((m) => parseFloat(m.style.left) === 50)!;
      mark.click();
      expect(video.currentTime).toBe(50);
      video.dispatchEvent(new Event("seeked"));
      video.dispatchEvent(new Event("timeupdate"));
      expect(cards().length).toBe(1);
      expect(cards()[0]).toContain("frase del segundo 50");
    });

    // Case 2 · click on the row of the flag at second 90 → the video is at second 90 and its card shows
    it("Case 2 · click on the row at second 90 → second 90 and its card", () => {
      const { player, video, cards } = page();
      player.querySelector<HTMLElement>(".fc-panel-tab")!.click();
      const row = [...player.querySelectorAll<HTMLElement>(".fc-row")].find((r) => r.textContent!.includes("1:30"))!;
      row.click();
      expect(video.currentTime).toBe(90);
      video.dispatchEvent(new Event("seeked"));
      video.dispatchEvent(new Event("timeupdate"));
      expect(cards().length).toBe(1);
      expect(cards()[0]).toContain("frase del segundo 90");
    });

    // Case 3 · normal playback reaches second 52 with no click → no card for the flag under the bar
    // (a regression guard: the bar rule of normal playback must survive the jump)
    it("Case 3 · playback reaches second 52 with no click → no card for the flag under the bar", () => {
      const { video, cards } = page();
      video.currentTime = 52;
      video.dispatchEvent(new Event("timeupdate"));
      expect(cards().length).toBe(0);
    });
  });
}

// S13 A2 · The strip shows the analysed part
//
// Story: On a page that mimics the YouTube player, a 100-second video has a flag file analysed until second 40
// and still running. The strip under the video shows the first 40 % as analysed and the rest as pending; when
// the file says done, the whole strip is analysed.
//
// Setup: a jsdom page with a player element and a video element whose duration is 100 seconds; the overlay and
// the panel are mounted as the content script mounts them, with a flag file of one flag at second 10 that the
// test changes between the cases, as the poll of the content script does.
{
  const running = () => ({
    video_id: "abc", published_at: "2026-11-10", status: "running", stop_reason: null, analysed_until: 40,
    flags: [{ id: "fallacy-10.0", t: 10, speaker: "Invitado", quote: "frase 10", type: "fallacy", label: "ad_hominem",
      reason: "Motivo.", confidence: 0.85, on_player: true, related: null, sources: [], note: null }],
  }) as any;

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    Object.defineProperty(video, "currentTime", { value: 0, writable: true, configurable: true });
    let flagFile = running();
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show);
    const strip = (cls: string) => player.querySelector<HTMLElement>(`.fc-strip .${cls}`);
    const poll = (change: object) => {
      flagFile = { ...flagFile, ...change };
      video.dispatchEvent(new Event("timeupdate"));
    };
    return { strip, poll };
  }

  describe("S13 A2 · The strip shows the analysed part", () => {
    // Case 1 · running, analysed until second 40 of 100 → the first 40 % analysed, the other 60 % pending
    it("Case 1 · running, analysed until second 40 of 100 → 40 % analysed, 60 % pending", () => {
      const { strip } = page();
      expect(parseFloat(strip("fc-analysed")!.style.width)).toBe(40);
      expect(parseFloat(strip("fc-pending")!.style.left)).toBe(40);
      expect(parseFloat(strip("fc-pending")!.style.width)).toBe(60);
    });

    // Case 2 · the next poll says analysed until second 70 → the analysed part grows to 70 %
    it("Case 2 · the next poll says analysed until second 70 → 70 % analysed", () => {
      const { strip, poll } = page();
      poll({ analysed_until: 70 });
      expect(parseFloat(strip("fc-analysed")!.style.width)).toBe(70);
    });

    // Case 3 · the file says done → the whole strip analysed, nothing pending
    it("Case 3 · the file says done → the whole strip analysed", () => {
      const { strip, poll } = page();
      poll({ status: "done" });
      expect(parseFloat(strip("fc-analysed")!.style.width)).toBe(100);
      expect(parseFloat(strip("fc-pending")?.style.width ?? "0")).toBe(0);
    });

    // Case 4 · the flag mark still sits on the strip, over the analysed part → one mark at 10 %
    it("Case 4 · the flag mark still sits on the strip → one mark at 10 %", () => {
      const { strip } = page();
      expect(parseFloat(strip("fc-mark")!.style.left)).toBe(10);
    });
  });
}

// The strip under the video holds only the marks, with a tip of minute and kind over a mark.
// A card's details pair each source link with the figures it backs.
describe("The strip under the video holds only the marks, with a tip of minute and kind over a mark.", () => {
  function page(flags: object[]) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    const file = { video_id: "abc", status: "done", flags } as any;
    const overlay = mountOverlay(player, video, () => file, () => {});
    mountPanel(overlay.layer, video, () => file, overlay.show);
    const playTo = (t: number) => {
      Object.defineProperty(video, "currentTime", { value: t, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));
    };
    return { player, playTo };
  }

  const fallacy = { id: "ad_hominem-30.0", t: 30, speaker: "Invitado", quote: "q", type: "fallacy", label: "ad_hominem",
    reason: "r", confidence: 0.9, on_player: true, related: null, sources: [], note: null };

  it("the strip draws no playback of its own: YouTube's red bar shows it", () => {
    const { player, playTo } = page([fallacy]);
    playTo(25);
    expect(player.querySelector(".fc-strip .fc-played, .fc-strip .fc-sun")).toBeNull();
    expect(player.querySelector(".fc-strip")!.classList.contains("fc-done")).toBe(true);
  });

  it("a mark under the mouse shows a tip with its minute and kind", () => {
    const { player } = page([fallacy]);
    player.querySelector(".fc-mark")!.dispatchEvent(new Event("pointerenter"));
    const tip = player.querySelector<HTMLElement>(".fc-tip")!;
    expect(tip.hidden).toBe(false);
    expect(tip.textContent).toContain("0:30");
    expect(tip.textContent).toContain("Ad hominem");
  });

  it("each figure carries the link of the outlet it names", () => {
    const { player, playTo } = page([{
      id: "misleading-10.0", t: 10, speaker: "Invitado", quote: "q", type: "inaccuracy", label: "misleading",
      reason: "r", confidence: 0.9, on_player: true, related: null, note: null,
      measures: [
        { name: "Titulares extranjeros", value: "16 %", source: "Seguridad Social vía Maldita.es, 2026", tier: 1, supports: false },
        { name: "Perceptores", value: "150.000", source: "Ministerio de Inclusión, junio 2026", tier: 1, supports: false },
      ],
      sources: [
        { publisher: "Maldita.es", url: "https://maldita.es/a", date: "2026-01-01" },
        { publisher: "Ministerio de Inclusión", url: "https://inclusion.gob.es/b", date: "2026-06-01" },
      ],
    }]);
    playTo(11);
    const refs = [...player.querySelectorAll(".fc-card .fc-ref")];
    expect(refs.length).toBe(2);
    expect(refs[0].querySelector("a")!.href).toBe("https://maldita.es/a");
    expect(refs[0].textContent).toContain("16 %");
    expect(refs[1].querySelector("a")!.href).toBe("https://inclusion.gob.es/b");
    expect(refs[1].textContent).toContain("150.000");
  });

  it("the strip lies exactly over YouTube's progress bar", () => {
    const { player, playTo } = page([fallacy]);
    const bar = document.createElement("div");
    bar.className = "ytp-progress-bar";
    player.append(bar);
    const rect = (left: number, top: number, width: number, height: number) =>
      ({ left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({}) }) as DOMRect;
    bar.getBoundingClientRect = () => rect(112, 640, 1056, 3);
    player.querySelector<HTMLElement>(".fc-layer")!.getBoundingClientRect = () => rect(100, 0, 1280, 720);
    playTo(10);
    const strip = player.querySelector<HTMLElement>(".fc-strip")!;
    expect(strip.style.left).toBe("12px");
    expect(strip.style.width).toBe("1056px");
    expect(strip.style.top).toBe(`${640 + 1.5 - 9}px`);
  });
});
