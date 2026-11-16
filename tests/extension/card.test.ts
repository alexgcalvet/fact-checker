// @vitest-environment jsdom
// The card on the player: what each kind of flag shows, the mark buttons, and how long a card stays.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { look } from "../../src/extension/src/flags";
import { mountOverlay, settings } from "../../src/extension/src/overlay";
import { mountPanel } from "../../src/extension/src/panel";
import { TEXTS } from "../../src/extension/src/texts";

// S1 A4 · A card shows on the player at the flag's second
//
// Story: On a page that mimics the YouTube player, with a flag file that holds one flag at second 42
// with confidence 0.9 and one at second 50 with confidence 0.6, the person plays to second 42 and sees
// one card with the name, the words and "90%"; no card appears for the 0.6 flag.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file; playback is moved by setting the video time and firing "timeupdate".
{
  const flagFile = {
    video_id: "abc",
    published_at: "2026-11-10",
    status: "done",
    stop_reason: null,
    flags: [
      { id: "f1", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad para hablar", type: "fallacy",
        label: "ad_hominem", reason: "Attacks the critic.", confidence: 0.9, related: null, sources: [], note: null },
      { id: "f2", t: 50, speaker: "guest", quote: "o esto o el caos", type: "fallacy",
        label: "false_dilemma", reason: "Two options only.", confidence: 0.6, related: null, sources: [], note: null },
    ],
  };

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile);
    const playTo = (t: number) => {
      Object.defineProperty(video, "currentTime", { value: t, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));
    };
    return { player, playTo };
  }

  describe("S1 A4 · A card shows on the player at the flag's second", () => {
    it("Case 1 · before second 42 → no card", () => {
      const { player, playTo } = page();
      playTo(41);
      expect(player.querySelectorAll(".fc-card").length).toBe(0);
    });

    it("Case 2 · at second 42 → one card with the name, the words and 90%", () => {
      const { player, playTo } = page();
      playTo(42);
      const cards = player.querySelectorAll(".fc-card");
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Ad hominem");
      expect(cards[0].textContent).toContain("la oposición no tiene autoridad para hablar");
      expect(cards[0].textContent).toContain("90%");
    });

    it("Case 3 · at second 50, the 0.6 flag → no card for it", () => {
      const { player, playTo } = page();
      playTo(50);
      expect(player.textContent).not.toContain("o esto o el caos");
    });
  });
}

// S2 A4 · An inaccuracy card shows the source and the date
//
// Story: On a page that mimics the YouTube player, with an inaccuracy flag at second 30 with confidence
// 0.9, rated "false", sourced to INE on 2025-10-28, the person plays to second 30 and sees a card with
// "Dato falso", the words, "INE · 2025-10-28" and "90%". When the flag has a note that the figure changed
// after the video was published, the card also shows "Dato actualizado:" with the note.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file; playback is moved by setting the video time and firing "timeupdate".
{
  function flagFile(note: string | null) {
    return {
      video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
      flags: [{
        id: "false-30.0", t: 30, speaker: "guest", quote: "el paro bajó al ocho por ciento", type: "inaccuracy",
        label: "false", reason: "La EPA dio un 10,45 %.", confidence: 0.9, related: null,
        sources: [{ publisher: "INE", url: "https://www.ine.es/epa", date: "2025-10-28" }], note,
      }],
    } as any;
  }

  function page(note: string | null) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile(note));
    Object.defineProperty(video, "currentTime", { value: 30, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    return player;
  }

  describe("S2 A4 · An inaccuracy card shows the source and the date", () => {
    it("Case 1 · at second 30 → one card with Dato falso, the words, the source, the date and 90%", () => {
      const cards = page(null).querySelectorAll(".fc-card");
      expect(cards.length).toBe(1);
      const text = cards[0].textContent!;
      expect(text).toContain("Dato falso");
      expect(text).toContain("el paro bajó al ocho por ciento");
      expect(text).toContain("INE · 2025-10-28");
      expect(text).toContain("90%");
      expect(text).not.toContain("Dato actualizado");
    });

    it("Case 2 · the flag has a note → the card also shows Dato actualizado with the note", () => {
      const text = page("Hoy es del 10,1 %.").querySelector(".fc-card")!.textContent!;
      expect(text).toContain("Dato actualizado: Hoy es del 10,1 %.");
    });
  });
}

// S3 A4 (extension part) · Only flags above their type's bar reach the player
//
// Story: On the mimic player page, a 0.55 fallacy that the helper marked for the player shows its card,
// and a 0.85 inaccuracy that it did not mark shows none. The helper part is in
// tests/helper/test_server.py (S3 A4).
//
// Setup: a jsdom page with a player and a video, the overlay mounted with a fixed flag file whose two
// flags start at second 20; playback is moved to second 21.
{
  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [
      { id: "a", t: 20, speaker: "guest", quote: "eso es lo que dicen los datos", type: "fallacy", label: "vague_authority",
        reason: "Vago.", confidence: 0.55, on_player: true, related: null, sources: [], note: null },
      { id: "b", t: 20, speaker: "guest", quote: "el paro juvenil se duplicó", type: "inaccuracy", label: "false",
        reason: "No.", confidence: 0.85, on_player: false, related: null,
        sources: [{ publisher: "INE", url: "https://www.ine.es/x", date: "2025-10-28" }], note: null },
    ],
  } as any;

  describe("S3 A4 · Only flags above their type's bar reach the player", () => {
    it("Case 1 · marked 0.55 fallacy → its card shows; unmarked 0.85 inaccuracy → no card", () => {
      document.body.innerHTML = '<div id="movie_player"><video></video></div>';
      const player = document.getElementById("movie_player")!;
      const video = player.querySelector("video")!;
      mountOverlay(player, video, () => flagFile);
      Object.defineProperty(video, "currentTime", { value: 21, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));
      const cards = player.querySelectorAll(".fc-card");
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("eso es lo que dicen los datos");
      expect(player.textContent).not.toContain("el paro juvenil se duplicó");
    });
  });
}

// S4 A1 (extension part) · Marking a card keeps the mark on the laptop
//
// Story: On the mimic player, the person clicks "✗ No" on an ad hominem card, types "es una pregunta,
// no un ataque" and saves; the mark goes out with the flag, "unfair" and the reason. "✓ De acuerdo" sends
// "correct" at once. The helper part is in tests/helper/test_server.py (S4 A1).
//
// Setup: a jsdom page with a player and a video, the overlay mounted with one flag at second 42 and a
// mark callback that records what it gets; playback is moved to second 43.
{
  const flagFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
      label: "ad_hominem", reason: "Ataca.", confidence: 0.55, on_player: true, related: null, sources: [], note: null }],
  } as any;

  function page() {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    const sent: [string, string, string][] = [];
    mountOverlay(player, video, () => flagFile, (flag, verdict, reason) => { sent.push([flag.id, verdict, reason]); });
    Object.defineProperty(video, "currentTime", { value: 43, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    const button = (text: string) =>
      [...player.querySelectorAll("button")].find((b) => b.textContent!.includes(text)) as HTMLButtonElement;
    return { player, sent, button };
  }

  describe("S4 A1 · Marking a card keeps the mark on the laptop", () => {
    it("Case 1 · ✗ No, a reason, Guardar → the mark goes out as unfair with the reason", () => {
      const { player, sent, button } = page();
      button("✗ No").click();
      const input = player.querySelector(".fc-card input") as HTMLInputElement;
      expect(input).not.toBeNull();
      input.value = "es una pregunta, no un ataque";
      button("Guardar").click();
      expect(sent).toEqual([["ad_hominem-42.0", "unfair", "es una pregunta, no un ataque"]]);
    });

    it("Case 2 · ✓ De acuerdo → the mark goes out at once as correct, with no reason", () => {
      const { sent, button } = page();
      button("De acuerdo").click();
      expect(sent).toEqual([["ad_hominem-42.0", "correct", ""]]);
    });
  });
}

// S4 A2 · A card under the mouse stays until the person is done
//
// Story: On the mimic player, a card shows at second 42. The person moves the mouse over it at second 49
// and starts typing a reason; at second 55 the card is still there. When the mouse leaves, the card goes.
//
// Setup: a jsdom page with a player and a video, the overlay mounted with one flag at second 42 and a mark
// callback; playback is moved by setting the video time and firing "timeupdate".
{
  const flagFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
      label: "ad_hominem", reason: "Ataca.", confidence: 0.55, on_player: true, related: null, sources: [], note: null }],
  } as any;

  describe("S4 A2 · A card under the mouse stays until the person is done", () => {
    it("Case 1 · mouse over the card at 49 → still there at 55; mouse out → gone", () => {
      document.body.innerHTML = '<div id="movie_player"><video></video></div>';
      const player = document.getElementById("movie_player")!;
      const video = player.querySelector("video")!;
      mountOverlay(player, video, () => flagFile, () => {});
      const playTo = (t: number) => {
        Object.defineProperty(video, "currentTime", { value: t, configurable: true });
        video.dispatchEvent(new Event("timeupdate"));
      };

      playTo(49);
      const card = player.querySelector(".fc-card")!;
      expect(card).not.toBeNull();
      card.dispatchEvent(new Event("pointerenter", { bubbles: true }));
      playTo(55);
      expect(player.querySelectorAll(".fc-card").length).toBe(1);

      card.dispatchEvent(new Event("pointerleave", { bubbles: true }));
      playTo(55.5);
      expect(player.querySelectorAll(".fc-card").length).toBe(0);
    });
  });
}

// S6 A2 · A disputed card shows each measure and the controversy
//
// Story: On a page that mimics the YouTube player, a disputed flag shows at its second. The card reads
// "Dato discutido", lists each measure as "name: value (source)", and shows the controversy line under them.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds one disputed flag at second 30 with the three unemployment measures of
// tests/golden/empleo.json and a controversy line; playback is moved by setting the video time and firing
// "timeupdate".
{
  const CONTROVERSY = "El paro registrado no cuenta a los fijos discontinuos inactivos, unos 0,9 millones (SEPE).";
  const LINES = [
    "paro registrado (SEPE): 2.443.766 (SEPE, octubre 2025)",
    "paro registrado + demandantes con relación laboral: unos 3,3 millones (SEPE, octubre 2025)",
    "parados EPA: 2.613.200 (INE, EPA 3T 2025)",
  ];

  const flagFile = {
    video_id: "abc", published_at: "2025-11-10", status: "done", stop_reason: null,
    flags: [{
      id: "disputed-30.0", t: 30, speaker: "guest", quote: "tenemos casi tres millones y medio de parados registrados",
      type: "inaccuracy", label: "disputed", reason: "Depende de la medida.", confidence: 0.9, related: null,
      sources: [{ publisher: "SEPE", url: "https://www.sepe.es/paro", date: "2025-11-04" }], note: null,
      measures: [
        { name: "paro registrado (SEPE)", value: "2.443.766", source: "SEPE, octubre 2025", tier: 2, supports: false },
        { name: "paro registrado + demandantes con relación laboral", value: "unos 3,3 millones",
          source: "SEPE, octubre 2025", tier: 2, supports: true },
        { name: "parados EPA", value: "2.613.200", source: "INE, EPA 3T 2025", tier: 1, supports: false },
      ],
      controversy: CONTROVERSY,
    }],
  } as any;

  describe("S6 A2 · A disputed card shows each measure and the controversy", () => {
    it("Case 1 · at second 30 → a Dato discutido card with each measure, then the controversy line", () => {
      document.body.innerHTML = '<div id="movie_player"><video></video></div>';
      const player = document.getElementById("movie_player")!;
      const video = player.querySelector("video")!;
      mountOverlay(player, video, () => flagFile);
      Object.defineProperty(video, "currentTime", { value: 30, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));

      const cards = player.querySelectorAll(".fc-card");
      expect(cards.length).toBe(1);
      const text = cards[0].textContent!;
      expect(text).toContain("Dato discutido");
      for (const line of LINES) expect(text).toContain(line);
      expect(text).toContain(CONTROVERSY);
      expect(text.indexOf(CONTROVERSY)).toBeGreaterThan(text.indexOf(LINES[2]));
    });
  });
}

// S7 A2 · A dodged-question card shows the question
//
// Story: On a page that mimics the YouTube player, a dodged-question flag shows at its second. The card
// reads "Pregunta esquivada", quotes the host's question, and gives the reason.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds one dodged-question flag at second 40 (the end of the answer), marked for the
// player, whose related utterance is the host's question at second 2; playback is moved by setting the
// video time and firing "timeupdate".
{
  const QUESTION = "¿Cuántas viviendas se han entregado?";
  const REASON = "Se preguntó por viviendas entregadas y la respuesta habla de la ley de vivienda.";

  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{
      id: "dodged-40.0", t: 40, speaker: "Invitado", quote: "la primera ley de vivienda de la democracia",
      type: "question", label: "dodged", answer: "dodged", reason: REASON, confidence: 0.9, on_player: true,
      related: { t: 2, quote: QUESTION }, sources: [], note: null,
    }],
  } as any;

  function at(second: number) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile);
    Object.defineProperty(video, "currentTime", { value: second, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    return player.querySelectorAll(".fc-card");
  }

  describe("S7 A2 · A dodged-question card shows the question", () => {
    it("Case 1 · at second 40 → a Pregunta esquivada card with the host's question and the reason", () => {
      const cards = at(40);
      expect(cards.length).toBe(1);
      const text = cards[0].textContent!;
      expect(text).toContain("Pregunta esquivada");
      expect(text).toContain(QUESTION);
      expect(text).toContain(REASON);
    });

    it("Case 2 · at second 39, before the answer ends → no card", () => {
      expect(at(39).length).toBe(0);
    });
  });
}

// S8 A2 · A contradiction card shows both statements
//
// Story: On a page that mimics the YouTube player, a contradiction flag shows at its second. The card
// reads "Contradicción", quotes the earlier statement with its minute, then the new one, and gives the
// reason.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds one contradiction flag at second 252.5 (the second statement), marked for the
// player, whose related utterance is the first statement at second 9; playback is moved by setting the
// video time and firing "timeupdate".
{
  const EARLIER = "no vamos a subir el IVA";
  const NOW = "subiremos el IVA de la luz el año que viene";
  const REASON = "Antes dijo que no subiría el IVA y ahora anuncia una subida del IVA de la luz.";

  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{
      id: "self-252.5", t: 252.5, speaker: "Invitado", quote: NOW, type: "contradiction", label: "self",
      reason: REASON, confidence: 0.9, on_player: true, related: { t: 9, quote: EARLIER }, sources: [], note: null,
    }],
  } as any;

  function at(second: number) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile);
    Object.defineProperty(video, "currentTime", { value: second, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    return player.querySelectorAll(".fc-card");
  }

  describe("S8 A2 · A contradiction card shows both statements", () => {
    it("Case 1 · at second 253 → a Contradicción card with the earlier statement and its minute, then the new one, and the reason", () => {
      const cards = at(253);
      expect(cards.length).toBe(1);
      const text = cards[0].textContent!;
      expect(text).toContain("Contradicción");
      expect(text).toContain("0:09");
      expect(text).toContain(EARLIER);
      expect(text).toContain(NOW);
      expect(text.indexOf(EARLIER)).toBeLessThan(text.indexOf(NOW));
      expect(text).toContain(REASON);
    });

    it("Case 2 · at second 252, before the second statement → no card", () => {
      expect(at(252).length).toBe(0);
    });
  });
}

// S9 A3 · The card shows the earlier statement or the promise
//
// Story: On a page that mimics the YouTube player, a record flag shows the earlier statement with its date
// and its source as a link; a promise flag shows "Prometido en abril de 2023: 184.000 viviendas para 2026 ·
// Estado: no cumplida".
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a fixed
// flag file that holds two contradiction flags marked for the player: a "record" flag at second 10 whose
// related utterance is an earlier public statement (no second, a date and a source), and a "promise" flag at
// second 40 with its promise; playback is moved by setting the video time and firing "timeupdate".
{
  const NOW = "yo nunca dije que no pactaría con ese partido";
  const EARLIER = "no pactaré con ese partido";
  const URL = "https://example.org/el-diario/entrevista-2023-07-02";
  const HOMES = "hemos cumplido lo que prometimos en vivienda";

  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [
      {
        id: "record-10.0", t: 10, speaker: "Invitado", quote: NOW, type: "contradiction", label: "record",
        reason: "En julio de 2023 dijo que no pactaría con ese partido.", confidence: 0.9, on_player: true,
        related: { t: null, quote: EARLIER, date: "2023-07-02", source: { publisher: "El Diario", url: URL } },
        sources: [{ publisher: "El Diario", url: URL, date: "2023-07-02" }], note: null,
      },
      {
        id: "promise-40.0", t: 40, speaker: "Invitado", quote: HOMES, type: "contradiction", label: "promise",
        reason: "Se entregaron muchas menos viviendas de las prometidas.", confidence: 0.9, on_player: true,
        related: null, note: null,
        promise: { made: "2023-04", figure: "184.000 viviendas", deadline: "2026", status: "not met" },
        sources: [{ publisher: "El País", url: "https://example.org/el-pais/viviendas-2025", date: "2025-09-15" }],
      },
    ],
  } as any;

  function at(second: number) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile);
    Object.defineProperty(video, "currentTime", { value: second, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    return player.querySelectorAll(".fc-card");
  }

  describe("S9 A3 · The card shows the earlier statement or the promise", () => {
    it("Case 1 · at second 11, a record flag → the earlier statement with its date, its source as a link, then the new words", () => {
      const cards = at(11);
      expect(cards.length).toBe(1);
      const text = cards[0].textContent!;
      expect(text).toContain(NOW);
      expect(text.indexOf(EARLIER)).toBeLessThan(text.indexOf(NOW));
      const earlier = [...cards[0].children].find((el) => el.textContent!.includes(EARLIER))!;
      expect(earlier).toBeDefined();
      expect(earlier.textContent).toContain("2023-07-02");
      const link = earlier.querySelector(`a[href="${URL}"]`);
      expect(link).not.toBeNull();
      expect(link!.textContent).toContain("El Diario");
    });

    it("Case 2 · at second 41, a promise flag → the date, figure, deadline and status of the promise", () => {
      const cards = at(41);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Prometido en abril de 2023: 184.000 viviendas para 2026 · Estado: no cumplida");
    });
  });
}

// S10 A2 · A context card shows who or what was named
//
// Story: On a page that mimics the YouTube player, a context flag shows at its second. The card reads
// "Contexto", names "Marta Gil" and gives the sentence, with no buttons to mark it unfair as a claim.
//
// Setup: a jsdom page with a player element and a video element, the overlay mounted on it with a mark
// callback and a fixed flag file that holds one context flag at second 182 (label "person", the name as
// quote, the sentence as reason), marked for the player; playback is moved by setting the video time and
// firing "timeupdate".
{
  const NAME = "Marta Gil";
  const SENTENCE = "Ministro de Transportes del Gobierno de España desde noviembre de 2023.";

  const flagFile = {
    video_id: "abc", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{
      id: "person-182.0", t: 182, speaker: "Invitado", quote: NAME, type: "context", label: "person",
      reason: SENTENCE, confidence: 0.95, on_player: true, related: null, sources: [], note: null,
    }],
  } as any;

  function at(second: number) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => flagFile, () => {});
    Object.defineProperty(video, "currentTime", { value: second, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    return player.querySelectorAll(".fc-card");
  }

  describe("S10 A2 · A context card shows who or what was named", () => {
    it("Case 1 · at second 183 → a Contexto card with the name and the sentence", () => {
      const cards = at(183);
      expect(cards.length).toBe(1);
      const text = cards[0].textContent!;
      expect(text).toContain("Contexto");
      expect(text).toContain(NAME);
      expect(text).toContain(SENTENCE);
    });

    it("Case 2 · the person can mark cards → the context card has no mark buttons", () => {
      const cards = at(183);
      expect(cards[0].querySelectorAll("button").length).toBe(0);
    });

    it("Case 3 · at second 181, before the mention → no card", () => {
      expect(at(181).length).toBe(0);
    });
  });
}

// S13 A4 · A card already marked shows the mark instead of the buttons
//
// Story: On the mimic player, a card marked "unfair" shows at its second. It reads "Marcaste: ✗ No" with a
// "cambiar" link instead of the two buttons; the link brings the buttons back.
//
// Setup: a jsdom page with a player and a video, the overlay mounted with one flag at second 42 that carries a
// past mark, and a mark callback that records what it gets; playback is moved to second 43.
{
  const flagFile = (mark: string) => ({
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
      label: "ad_hominem", reason: "Ataca.", confidence: 0.85, on_player: true, related: null, sources: [], note: null,
      mark }],
  }) as any;

  function page(mark: string) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    const sent: string[] = [];
    const file = flagFile(mark);
    mountOverlay(player, video, () => file, (flag, verdict) => { sent.push(verdict); });
    Object.defineProperty(video, "currentTime", { value: 43, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    const card = () => player.querySelector<HTMLElement>(".fc-card")!;
    const buttons = () => [...card().querySelectorAll("button")].map((b) => b.textContent!);
    const change = () => [...card().querySelectorAll<HTMLElement>("a, button")].find((b) => b.textContent === "cambiar");
    return { card, buttons, change, sent };
  }

  describe("S13 A4 · A card already marked shows the mark instead of the buttons", () => {
    // Case 1 · a card marked unfair → "Marcaste: ✗ No" and a "cambiar" link, no mark buttons
    it("Case 1 · a card marked unfair → \"Marcaste: ✗ No\" and \"cambiar\", no mark buttons", () => {
      const { card, buttons, change } = page("unfair");
      expect(card().textContent).toContain("Marcaste: ✗ No");
      expect(change()).toBeDefined();
      expect(buttons()).not.toContain("✓ De acuerdo");
      expect(buttons()).not.toContain("✗ No");
    });

    // Case 2 · a click on "cambiar" → the two mark buttons come back, and nothing is sent yet
    it("Case 2 · a click on \"cambiar\" → the two mark buttons come back", () => {
      const { buttons, change, sent } = page("unfair");
      change()!.click();
      expect(buttons()).toContain("✓ De acuerdo");
      expect(buttons()).toContain("✗ No");
      expect(sent).toEqual([]);
    });

    // Case 3 · a card marked correct → "Marcaste: ✓ De acuerdo"
    it("Case 3 · a card marked correct → \"Marcaste: ✓ De acuerdo\"", () => {
      const { card } = page("correct");
      expect(card().textContent).toContain("Marcaste: ✓ De acuerdo");
    });
  });
}

// S27 A4 · Each card asks the question with two large buttons
//
// Story: A person with a Spanish browser sees a fallacy card: its foot reads "¿Es justo este aviso?" with the buttons
// "✓ De acuerdo" and "✗ No", taller than the card's other text buttons. In English they read "Is this flag fair?",
// "✓ Agree", "✗ Disagree". A click on "✓ De acuerdo" marks the flag correct as today, and a marked card says
// "Marcaste: ✓ De acuerdo" with "cambiar".
//
// Setup: a jsdom page with a player and a video at second 43, the browser language set per case (navigator.language),
// and the overlay mounted with one fallacy flag at second 42 and a mark callback that records what it gets. The sizes
// come from the overlay's own style sheet through getComputedStyle.
describe("S27 A4 · Each card asks the question with two large buttons", () => {
  const flagFile = (mark?: string) => ({
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [{ id: "ad_hominem-42.0", t: 42, speaker: "guest", quote: "la oposición no tiene autoridad", type: "fallacy",
      label: "ad_hominem", reason: "Ataca.", confidence: 0.85, on_player: true, related: null, sources: [], note: null,
      ...(mark ? { mark } : {}) }],
  }) as any;

  async function page(language: string, mark?: string) {
    Object.defineProperty(navigator, "language", { value: language, configurable: true });
    vi.resetModules();
    const { mountOverlay } = await import("../../src/extension/src/overlay");
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    const sent: [string, string, string][] = [];
    const file = flagFile(mark);
    mountOverlay(player, video, () => file, (flag, verdict, reason) => { sent.push([flag.id, verdict, reason]); });
    Object.defineProperty(video, "currentTime", { value: 43, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    const card = () => player.querySelector<HTMLElement>(".fc-card")!;
    const button = (text: string) =>
      [...card().querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent!.trim() === text);
    const height = (el: Element) => parseFloat(getComputedStyle(el).height);
    return { card, button, height, sent };
  }

  afterEach(() => { Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true }); });

  describe("S27 A4 · Each card asks the question with two large buttons", () => {
    // Case 1 · a Spanish browser → "¿Es justo este aviso?" with "✓ De acuerdo" and "✗ No"
    it("Case 1 · Spanish browser → the question and the two buttons in Spanish", async () => {
      const { card, button } = await page("es-ES");
      expect(card().textContent).toContain("¿Es justo este aviso?");
      expect(button("✓ De acuerdo")).toBeDefined();
      expect(button("✗ No")).toBeDefined();
    });

    // Case 2 · the two buttons → taller than the card's text buttons (Guardar, Cancelar)
    it("Case 2 · the vote buttons are at least 1.25 times as tall as the card's text buttons", async () => {
      const { button, height } = await page("es-ES");
      const agree = height(button("✓ De acuerdo")!);
      const disagree = height(button("✗ No")!);
      button("✗ No")!.click();
      const save = height(button("Guardar")!);
      expect(save).toBeGreaterThan(0);
      expect(agree).toBeGreaterThanOrEqual(save * 1.25);
      expect(disagree).toBe(agree);
    });

    // Case 3 · an English browser → "Is this flag fair?" with "✓ Agree" and "✗ Disagree"
    it("Case 3 · English browser → the question and the two buttons in English, no Spanish", async () => {
      const { card, button } = await page("en-US");
      expect(card().textContent).toContain("Is this flag fair?");
      expect(button("✓ Agree")).toBeDefined();
      expect(button("✗ Disagree")).toBeDefined();
      expect(card().textContent).not.toContain("¿Es justo");
    });

    // Case 4 · a click on "✓ De acuerdo" → the flag is marked correct at once, with no reason
    it("Case 4 · ✓ De acuerdo → marked correct, the buttons give way to the mark", async () => {
      const { card, button, sent } = await page("es-ES");
      button("✓ De acuerdo")!.click();
      expect(sent).toEqual([["ad_hominem-42.0", "correct", ""]]);
      expect(card().textContent).toContain("Marcado: correcto");
      expect(button("✓ De acuerdo")).toBeUndefined();
    });

    // Case 5 · a card marked before → "Marcaste: ✓ De acuerdo" and "cambiar", which brings the question back
    it("Case 5 · a marked card → \"Marcaste: ✓ De acuerdo\" and \"cambiar\"; cambiar asks again", async () => {
      const { card, button } = await page("es-ES", "correct");
      expect(card().textContent).toContain("Marcaste: ✓ De acuerdo");
      expect(card().textContent).not.toContain("¿Es justo este aviso?");
      button("cambiar")!.click();
      expect(card().textContent).toContain("¿Es justo este aviso?");
      expect(button("✓ De acuerdo")).toBeDefined();
    });
  });
});

// S34 A2 · A serious card says "grave" in its title
//
// Story: The person plays a video whose file holds a serious false figure, a moderate misleading one and a
// puntualización. The first card reads "Falso · grave" ("False · serious" in English), the second reads "Engañoso",
// and the puntualización stays grey with no severity word. The side panel rows read the same.
//
// Setup: a jsdom page with a player and a 100-second video; the overlay and the panel mounted as the content script
// mounts them, with a judged flag file of three flags on the player: a false figure at second 10 (keep, serious), a
// misleading figure at second 30 (keep, moderate) and a false figure at second 50 (nitpick). The interface speaks
// Spanish unless a case picks English in the settings. Playback moves to one second after each flag.
describe("S34 A2 · A serious card says \"grave\" in its title", () => {
  const flag = (id: string, t: number, label: string, judge: object) => ({
    id, t, speaker: "Invitado", quote: `frase del segundo ${t}`, type: "inaccuracy", label,
    reason: `Motivo del segundo ${t}.`, confidence: 0.9, on_player: true, related: null, sources: [], note: null, judge,
  });
  const flagFile = {
    video_id: "abcdefgh", published_at: "2026-11-10", status: "done", stop_reason: null,
    flags: [
      flag("false-10.0", 10, "false", { verdict: "keep", reason: "Bajó del 12 % al 11 %.", severity: "serious" }),
      flag("misleading-30.0", 30, "misleading", { verdict: "keep", reason: "Cuenta solo un año.", severity: "moderate" }),
      flag("false-50.0", 50, "false", { verdict: "nitpick", reason: "Se aprobó en abril de 2019" }),
    ],
  } as any;

  function page(lang: "es" | "en" = "es") {
    settings.lang = lang;
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    Object.defineProperty(video, "duration", { value: 100, configurable: true });
    let now = 0;
    Object.defineProperty(video, "currentTime", { get: () => now, set: (t) => { now = t; }, configurable: true });
    const overlay = mountOverlay(player, video, () => flagFile, () => {});
    mountPanel(overlay.layer, video, () => flagFile, overlay.show);
    const at = (t: number) => {
      now = t;
      video.dispatchEvent(new Event("timeupdate"));
      return [...player.querySelectorAll<HTMLElement>(".fc-card")];
    };
    const row = (t: number) => [...player.querySelectorAll<HTMLElement>(".fc-row")]
      .find((r) => r.textContent!.includes(`frase del segundo ${t}`))!;
    return { at, row };
  }

  /** True when the colour is a grey: its red, green and blue are within 24 of each other. */
  function grey(css: string): boolean {
    const hex = css.match(/#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i);
    const dec = css.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    const rgb = hex ? hex.slice(1).map((h) => parseInt(h, 16)) : dec ? dec.slice(1).map(Number) : null;
    if (!rgb) return false;
    return Math.max(...rgb) - Math.min(...rgb) <= 24;
  }

  afterEach(() => { settings.lang = null; });

  describe("S34 A2 · A serious card says \"grave\" in its title", () => {
    // Case 1 · the serious false figure → its card and its panel row read "Dato falso · grave"
    it("Case 1 · the serious false figure → \"Dato falso · grave\" on the card and the row", () => {
      const { at, row } = page();
      const cards = at(11);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Dato falso · grave");
      expect(row(10).textContent).toContain("Dato falso · grave");
    });

    // Case 2 · the moderate misleading figure → "Dato engañoso" with no severity word, on the card and the row
    it("Case 2 · the moderate misleading figure → \"Dato engañoso\", no severity word", () => {
      const { at, row } = page();
      const cards = at(31);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Dato engañoso");
      expect(cards[0].textContent).not.toMatch(/grave|moderad/);
      expect(row(30).textContent).toContain("Dato engañoso");
      expect(row(30).textContent).not.toMatch(/grave|moderad/);
    });

    // Case 3 · the puntualización → a grey card titled "Puntualización", no severity word, on the card and the row
    it("Case 3 · the puntualización → grey, \"Puntualización\", no severity word", () => {
      const { at, row } = page();
      const cards = at(51);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("Puntualización");
      expect(cards[0].textContent).not.toContain("grave");
      expect(grey(cards[0].style.borderLeft || cards[0].style.borderColor)).toBe(true);
      expect(row(50).textContent).toContain("Puntualización");
      expect(row(50).textContent).not.toContain("grave");
    });

    // Case 4 · the serious false figure in English → "False claim · serious" on the card and the row
    it("Case 4 · the serious false figure in English → \"False claim · serious\"", () => {
      const { at, row } = page("en");
      const cards = at(11);
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain("False claim · serious");
      expect(row(10).textContent).toContain("False claim · serious");
      expect(at(31)[0].textContent).not.toContain("serious");
    });
  });
});

// Typing a reason must not reach YouTube's keyboard shortcuts (k pauses, f goes full screen, digits seek).
describe("Typing a reason must not reach YouTube's keyboard shortcuts (k pauses, f goes full screen, digits seek).", () => {
  it("keys typed in the reason field do not reach the player", () => {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    const reached: string[] = [];
    for (const type of ["keydown", "keypress", "keyup"]) player.addEventListener(type, (e) => reached.push(e.type));
    const flags = { flags: [{ id: "a", t: 1, type: "fallacy", label: "ad_hominem", quote: "q", reason: "r",
      confidence: 0.9, on_player: true, sources: [], note: null }] } as any;
    mountOverlay(player, video, () => flags, () => {});
    Object.defineProperty(video, "currentTime", { value: 2, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    [...player.querySelectorAll("button")].find((b) => b.textContent!.includes("✗ No"))!.click();
    const input = player.querySelector(".fc-card input")!;
    for (const type of ["keydown", "keypress", "keyup"]) input.dispatchEvent(new KeyboardEvent(type, { key: "k", bubbles: true }));
    expect(reached).toEqual([]);
  });
});

// A context chip stays long enough to read it and waits for the mouse; a card's sources come first in its details.
describe("A context chip stays long enough to read it and waits for the mouse; a card's sources come first in its details.", () => {
  const context = (reason: string) => ({
    id: "person-100.0", t: 100, speaker: "Invitado", quote: "Ana Pérez", type: "context", label: "person",
    reason, confidence: 0.95, on_player: true, related: null, sources: [], note: null,
  });

  function page(flags: object[]) {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    mountOverlay(player, video, () => ({ video_id: "abc", status: "done", flags }) as any, () => {});
    const playTo = (t: number) => {
      Object.defineProperty(video, "currentTime", { value: t, configurable: true });
      video.dispatchEvent(new Event("timeupdate"));
    };
    return { player, playTo, chips: () => player.querySelectorAll(".fc-chip") };
  }

  it("a long context chip stays past 8 seconds; a short one leaves at 8", () => {
    const long = page([context("x".repeat(240))]);
    long.playTo(112);
    expect(long.chips().length).toBe(1);
    const short = page([context("Economista.")]);
    short.playTo(109);
    expect(short.chips().length).toBe(0);
  });

  it("a chip under the mouse stays, and 3 seconds more after the mouse leaves", () => {
    const { playTo, chips } = page([context("Economista.")]);
    playTo(101);
    chips()[0].dispatchEvent(new Event("pointerenter", { bubbles: true }));
    playTo(120);
    expect(chips().length).toBe(1);
    chips()[0].dispatchEvent(new Event("pointerleave", { bubbles: true }));
    playTo(122);
    expect(chips().length).toBe(1);
    playTo(124);
    expect(chips().length).toBe(0);
  });

  it("a source that no line names gets a line of its own, after the figures", () => {
    const { player, playTo } = page([{
      id: "false-10.0", t: 10, speaker: "Invitado", quote: "medio millón", type: "inaccuracy", label: "misleading",
      reason: "No.", confidence: 0.9, on_player: true, related: null, note: null,
      measures: [{ name: "Titulares", value: "16 %", source: "SS", tier: 1, supports: false }],
      sources: [{ publisher: "Maldita", url: "https://maldita.es/x", date: "2026-01-01" }],
    }]);
    playTo(11);
    const lines = [...player.querySelectorAll(".fc-card details > div")];
    expect(lines[0].querySelector("a")).toBeNull();
    expect(lines.at(-1)!.querySelector("a")?.href).toBe("https://maldita.es/x");
  });
});

// Every source of a card is a link that opens in a new tab.
describe("Every source of a card is a link that opens in a new tab.", () => {
  it("each source is a link to its page", () => {
    document.body.innerHTML = '<div id="movie_player"><video></video></div>';
    const player = document.getElementById("movie_player")!;
    const video = player.querySelector("video")!;
    const file = { video_id: "abc", published_at: null, status: "done", stop_reason: null, flags: [{
      id: "false-10.0", t: 10, speaker: "Invitado", quote: "el paro está en el 14 %", type: "inaccuracy", label: "false",
      reason: "Es el 10,45 %.", confidence: 0.9, related: null, note: null,
      sources: [{ publisher: "INE", url: "https://www.ine.es/epa", date: "2025-10-28" },
                { publisher: "Newtral", url: "https://www.newtral.es/paro", date: "2025-10-29" }],
    }] } as any;
    mountOverlay(player, video, () => file, () => {});
    Object.defineProperty(video, "currentTime", { value: 11, configurable: true });
    video.dispatchEvent(new Event("timeupdate"));
    const links = [...player.querySelectorAll<HTMLAnchorElement>(".fc-card a")];
    expect(links.map((a) => [a.textContent, a.href, a.target])).toEqual([
      ["INE", "https://www.ine.es/epa", "_blank"],
      ["Newtral", "https://www.newtral.es/paro", "_blank"],
    ]);
  });
});

// Colour sits only on the verdict: one disc and hue per verdict, grouped in the families of the panel filters.
// The card, the strip marks and the panel rows share it.
describe("Colour sits only on the verdict: one disc and hue per verdict, grouped in the families of the panel filters.", () => {
  const FALLACIES = ["ad_hominem", "tu_quoque", "false_dilemma", "straw_man", "false_cause", "hasty_generalization",
    "vague_authority", "insinuation", "double_standard", "cherry_picking", "appeal_to_fear"];
  const GROUPS: [string, string[]][] = [
    ["inaccuracy", ["false"]],
    ["inaccuracy", ["misleading", "definition_swap", "plan_as_fact"]],
    ["inaccuracy", ["disputed"]],
    ["fallacy", FALLACIES],
    ["question", ["dodged", "partial"]],
    ["contradiction", ["self", "record", "promise"]],
    ["context", ["person", "case", "event"]],
  ];
  const of = (type: string, label: string) => look({ type, label });

  it("labels of one group share their whole look", () => {
    for (const [type, labels] of GROUPS) for (const label of labels) expect(of(type, label)).toEqual(of(type, labels[0]));
  });

  it("each verdict has its hue: red for false, amber for misleading, magenta for rhetoric, blue for context", () => {
    const hue = (type: string, label: string) => of(type, label).color;
    expect(hue("inaccuracy", "misleading")).toBe(hue("inaccuracy", "disputed"));
    expect(new Set([hue("fallacy", "ad_hominem"), hue("question", "dodged"), hue("contradiction", "self")]).size).toBe(1);
    expect(new Set([hue("inaccuracy", "false"), hue("inaccuracy", "misleading"), hue("fallacy", "ad_hominem"),
      hue("context", "person")]).size).toBe(4);
  });

  it("misleading and disputed stay in the false family; disputed keeps its word in the text colour", () => {
    expect(of("inaccuracy", "misleading").family).toBe(of("inaccuracy", "false").family);
    expect(of("inaccuracy", "disputed").dot).toBe(of("inaccuracy", "misleading").dot);
    expect(of("inaccuracy", "disputed").word).not.toBe(of("inaccuracy", "misleading").word);
  });

  it("a nitpick is neutral, whatever its type", () => {
    const nitpick = look({ type: "inaccuracy", label: "false", judge: { verdict: "nitpick", reason: "" } });
    expect(nitpick.family).toBe("Puntualizaciones");
    expect(nitpick.color).not.toBe(of("inaccuracy", "false").color);
  });

  it("every fallacy has a Spanish name", () => {
    for (const label of FALLACIES) for (const words of Object.values(TEXTS)) expect(words.labels[label]).toBeTruthy();
  });
});

// YouTube listens to keys at the window in the capture phase. The guard registers first (document_start),
// so keys typed in a card's field stop there; keys typed anywhere else still reach YouTube.
describe("The guard stops the keys typed in a card field before YouTube sees them.", () => {
  // Loaded here, not at the top of the file, so the other tests of this file run without the guard.
  beforeAll(async () => {
    await import("../../src/extension/src/guard");
  });

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
});
