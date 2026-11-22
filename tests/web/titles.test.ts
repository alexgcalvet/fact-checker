// Inline 2026-11-22 · A video's title reads clean, in Spanish sentence case (owner)
//
// Story: YouTube titles often open with a live tag and shout in capitals. The reader sees them without the leading tag
// («DIRECTO |», «EN DIRECTO:», «LIVE |», a red dot) and in sentence case: shouted words go lower case, the first word
// of the title and of each part after « | », « - » or «: » takes a capital, and a shouted word that is a known proper
// name from our own data (a guest, a channel or outlet) takes that name's own case, matched without case or accents,
// a name of several words as a whole. Acronyms (PSOE, RTVE…) and short ones (PP, CIS, 23J) never change. Words the
// title did not shout keep their case. The raw title stays in the data.
//
// Setup: invented titles and names; the pure function of src/shared/titles.ts.
import { describe, expect, it } from "vitest";
import { cleanTitle } from "../../src/shared/titles";

const NAMES = ["Lucía Pardo", "Mateo Ruiz", "Lucía", "Pardo", "Mateo", "Ruiz", "La Tertulia", "El Diario", "Canal Norte"];

describe("A video's title reads clean, in Spanish sentence case", () => {
  it.each([
    ["🔴 DIRECTO | DEBATE ELECTORAL en RTVE", "Debate electoral en RTVE"],
    ["EN DIRECTO: Entrevista al líder del PSOE", "Entrevista al líder del PSOE"],
    ["LIVE | The FINAL debate", "The final debate"],
    ["El PP y la UE según el CIS", "El PP y la UE según el CIS"],
    ["Sin etiquetas, sin mayúsculas", "Sin etiquetas, sin mayúsculas"],
    ["DIRECTO | Debate CARA A CARA entre PARDO y RUIZ", "Debate cara a cara entre Pardo y Ruiz"],
    ["LUCÍA PARDO en LA TERTULIA - ENTREVISTA COMPLETA", "Lucía Pardo en La Tertulia - Entrevista completa"],
    ["DEBATE 23J | Los mejores momentos | EL DIARIO", "Debate 23J | Los mejores momentos | El Diario"],
    ["LUCIA PARDO habla del país", "Lucía Pardo habla del país"],
    ["Mateo Ruiz: EL PAÍS QUE QUEREMOS", "Mateo Ruiz: El país que queremos"],
  ])("%s → %s", (raw, clean) => {
    expect(cleanTitle(raw, NAMES)).toBe(clean);
  });

  // A name that our data itself keeps in capitals (a channel «EL CANAL DEL NORTE») takes a capital on each word but its
  // small ones, and a short word that is not a small one stays an acronym: its own case is unknown.
  it("a shouted name of our data → «El Canal del Norte», «Radio NTR»", () => {
    expect(cleanTitle("Entrevista | EL CANAL DEL NORTE", ["EL CANAL DEL NORTE"])).toBe("Entrevista | El Canal del Norte");
    expect(cleanTitle("ENTREVISTA EN CADENA NORTE", ["CADENA NORTE", "RADIO NTR"])).toBe("Entrevista en Cadena Norte");
    expect(cleanTitle("Tertulia | RADIO NTR", ["RADIO NTR"])).toBe("Tertulia | Radio NTR");
  });
});
