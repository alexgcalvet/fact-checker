"""The fact check: which figures are checked, the published checks and the search, and the verdict with its dated source."""
import json
import os
import re
import stat
import sys
from pathlib import Path

from fact_checker import cli, server
from fact_checker.adapters.youtube import parse_json3
from fact_checker.core import scheduler
from fact_checker.core.flags import PublishedCheck, Segment, Transcript
from fact_checker.server import run_analysis
from screen_fakes import fake_clis, fake_video, FakeMessagesAPI, FALSE, jsonl


# S2 A2 · A published fact-check is used first, with its own date
#
# Story: In an invented dialogue a guest says youth unemployment doubled last year. A published fact-check
# by Newtral, rated "Falso" on 12 May 2025, matches it. The check step receives that fact-check, and the
# flag cites Newtral with the date 2025-05-12, even if the web search gives no date.
#
# Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake Fact Check Tools API
# that returns the Newtral check for any query about "paro juvenil"; a fake Claude that lists the four
# claims of the dialogue in the chunk call, and in the check call says the youth claim is false, citing
# the Newtral link with no date; a temporary helper home.

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-claims.json3"
NEWTRAL_URL = "https://www.newtral.es/paro-juvenil-duplicado/"

CLAIMS = [
    {"quote": "El paro juvenil se duplicó el año pasado", "queries": ["paro juvenil duplicado"]},
    {"quote": "España tiene cuarenta y ocho millones de habitantes", "queries": ["población España"]},
    {"quote": "la inflación de septiembre fue del cinco por ciento", "queries": ["IPC septiembre"]},
    {"quote": "el paro bajó al ocho por ciento en el tercer trimestre", "queries": ["EPA tercer trimestre paro"]},
]


class FakeTranscript:
    def fetch(self, video_id):
        return parse_json3(json.loads(FAKE.read_text()), published_at="2026-11-10")


class FakeGoogle:
    def search(self, query, language):
        if "paro juvenil" in query:
            return [PublishedCheck(claim="El paro juvenil se ha duplicado en un año", claimant="Varios",
                                   publisher="Newtral", site="newtral.es", url=NEWTRAL_URL,
                                   rating="Falso", review_date="2025-05-12")]
        return []


class FakeClaude:
    def __init__(self):
        self.check_prompts = []

    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            self.check_prompts.append(prompt)
            return {"verdicts": [
                {"quote": "El paro juvenil se duplicó el año pasado", "verdict": "false",
                 "reason": "Newtral lo desmintió.", "confidence": 0.9,
                 "sources": [{"publisher": "Newtral", "url": NEWTRAL_URL, "date": None}], "note": None},
            ]}
        return {"flags": [], "claims": [dict(c) for c in CLAIMS]}


def test_published_check_first(tmp_path):
    claude = FakeClaude()
    run_analysis("claims", 0, transcript=FakeTranscript(), llm=claude, factcheck=FakeGoogle(), home=tmp_path)
    data = json.loads((tmp_path / "videos" / "claims.json").read_text())
    youth = [f for f in data["flags"] if f["type"] == "inaccuracy" and "paro juvenil" in f["quote"]]

    # Case 1 · a published check matches → the check step receives it, with its rating
    assert any("Newtral" in p and "Falso" in p for p in claude.check_prompts)

    # Case 2 · the claim is judged false → one inaccuracy flag on the caption words, at second 10
    assert len(youth) == 1
    assert youth[0]["quote"] == "el paro juvenil se duplicó el año pasado"
    assert abs(youth[0]["t"] - 10.0) < 0.01
    assert youth[0]["label"] == "false"

    # Case 3 · the web search gave no date → the source takes the date of the published check
    assert youth[0]["sources"] == [{"publisher": "Newtral", "url": NEWTRAL_URL, "date": "2025-05-12"}]
    print("PASS S2 A2 · A published fact-check is used first, with its own date")


# S2 A3 · A claim is flagged only when a dated source contradicts it
#
# Story: In the same dialogue three claims are checked: one the sources confirm, one they contradict but
# with no date anywhere, and one the INE contradicts in a release dated 2025-10-28. Only the third becomes
# a flag, citing INE and that date.
#
# Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake Fact Check Tools API
# that finds nothing; a fake Claude that lists the three claims in the chunk call and, in the check call,
# confirms the population, contradicts the inflation with an undated source, and contradicts the
# unemployment figure with an INE release dated 2025-10-28; a temporary helper home.

INE_URL = "https://www.ine.es/daco/daco42/daco4211/epa0325.pdf"

CLAIMS_s2a3 = [
    {"quote": "España tiene cuarenta y ocho millones de habitantes", "queries": ["población España"]},
    {"quote": "la inflación de septiembre fue del cinco por ciento", "queries": ["IPC septiembre"]},
    {"quote": "el paro bajó al ocho por ciento en el tercer trimestre", "queries": ["EPA tercer trimestre paro"]},
]

VERDICTS = [
    {"quote": "España tiene cuarenta y ocho millones de habitantes", "verdict": "true", "reason": "Cierto.",
     "confidence": 0.9, "sources": [{"publisher": "INE", "url": "https://www.ine.es/pob", "date": "2026-01-01"}],
     "note": None},
    {"quote": "la inflación de septiembre fue del cinco por ciento", "verdict": "false", "reason": "Fue menor.",
     "confidence": 0.9, "sources": [{"publisher": "Blog", "url": "https://example.org/ipc", "date": None}],
     "note": None},
    {"quote": "el paro bajó al ocho por ciento en el tercer trimestre", "verdict": "false",
     "reason": "La EPA dio un 10,45 %.", "confidence": 0.85,
     "sources": [{"publisher": "INE", "url": INE_URL, "date": "2025-10-28"}], "note": None},
]


class NoPublishedChecks:
    def search(self, query, language):
        return []


class FakeClaude_s2a3:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [dict(v) for v in VERDICTS]}
        return {"flags": [], "claims": [dict(c) for c in CLAIMS_s2a3]}


def test_flag_needs_dated_source(tmp_path):
    run_analysis("claims", 0, transcript=FakeTranscript(), llm=FakeClaude_s2a3(), factcheck=NoPublishedChecks(),
                 home=tmp_path)
    data = json.loads((tmp_path / "videos" / "claims.json").read_text())
    quotes = {f["quote"]: f for f in data["flags"] if f["type"] == "inaccuracy"}

    # Case 1 · the sources confirm the claim → no flag
    assert "españa tiene cuarenta y ocho millones de habitantes" not in quotes

    # Case 2 · contradicted, but no source has a date → no flag
    assert "la inflación de septiembre fue del cinco por ciento" not in quotes

    # Case 3 · contradicted by a dated INE release → one flag citing INE and 2025-10-28
    flag = quotes["el paro bajó al ocho por ciento en el tercer trimestre"]
    assert flag["label"] == "false"
    assert flag["sources"] == [{"publisher": "INE", "url": INE_URL, "date": "2025-10-28"}]
    assert abs(flag["t"] - 100.0) < 0.01
    print("PASS S2 A3 · A claim is flagged only when a dated source contradicts it")


# S5 A3 · A published fact-check about another event does not count
#
# Story: A guest says 80,000 people crossed into Ceuta in two days. A published fact-check about a different
# crossing says "hundreds" and is rated false. The check step says it is another event, so it gives no
# source and no date, and no card is made from it.
#
# Setup: invented captions with two claims, the Ceuta crossing and youth unemployment; a fake Fact Check
# Tools API that returns a Maldita check about another Ceuta crossing (rated "Falso", 2021-05-20) and a
# Newtral check about the same youth unemployment claim (rated "Falso", 2025-05-12); a fake Claude that
# lists both claims, judges both false citing the published check with no date, and says the Maldita check
# is about another event and the Newtral check about the same one; a temporary helper home.

CEUTA = "más de ochenta mil personas entraron en Ceuta en dos días"
YOUTH = "el paro juvenil se duplicó el año pasado"
MALDITA_URL = "https://maldita.es/bulo-ceuta-cientos/"


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript_s5a3:
    def fetch(self, video_id):
        return Transcript(segments=words(0, CEUTA) + words(10, YOUTH), published_at="2026-11-10")


class FakeGoogle_s5a3:
    def search(self, query, language):
        if "Ceuta" in query:
            return [PublishedCheck(claim="Cientos de personas cruzaron a nado la frontera de Ceuta", claimant="Redes",
                                   publisher="Maldita", site="maldita.es", url=MALDITA_URL, rating="Falso",
                                   review_date="2021-05-20")]
        return [PublishedCheck(claim="El paro juvenil se ha duplicado en un año", claimant="Varios",
                               publisher="Newtral", site="newtral.es", url=NEWTRAL_URL, rating="Falso",
                               review_date="2025-05-12")]


def verdict(quote, publisher, url, same_event):
    return {"quote": quote, "verdict": "false", "reason": "Un verificador lo desmintió.", "confidence": 0.9,
            "sources": [{"publisher": publisher, "url": url, "date": None}], "note": None,
            "published": [{"url": url, "same_event": same_event}]}


class FakeClaude_s5a3:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [verdict(CEUTA, "Maldita", MALDITA_URL, False),
                                 verdict(YOUTH, "Newtral", NEWTRAL_URL, True)]}
        return {"flags": [], "claims": [{"quote": CEUTA, "speaker": "Invitado", "queries": ["Ceuta entrada"]},
                                        {"quote": YOUTH, "speaker": "Invitado", "queries": ["paro juvenil"]}]}


def test_other_event_ignored(tmp_path):
    run_analysis("events", 0, transcript=FakeTranscript_s5a3(), llm=FakeClaude_s5a3(), factcheck=FakeGoogle_s5a3(), home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "events.json").read_text())["flags"]

    # Case 1 · the only source is a check about another event → no source, no date, no card
    assert not [f for f in flags if "Ceuta" in f["quote"]], flags

    # Case 2 · a check about the same event → the card cites it with its own date
    youth = [f for f in flags if f["quote"] == YOUTH]
    assert len(youth) == 1, flags
    assert youth[0]["sources"] == [{"publisher": "Newtral", "url": NEWTRAL_URL, "date": "2025-05-12"}]
    print("PASS S5 A3 · A published fact-check about another event does not count")


# S6 A1 · A figure that a credible measure supports is disputed, not false
#
# Story: A guest says "tenemos casi tres millones y medio de parados registrados". The check finds three
# measures: SEPE registered unemployment (2.4 million, against), registered unemployment plus inactive fijos
# discontinuos (about 3.3 million, for) and the EPA (2.6 million, against). The flag file gets a "disputed"
# flag with the three measures and a note on the fijos discontinuos controversy, not a "false" flag.
# Edge case: when the only measure that contradicts a claim comes from a think tank or a newspaper, no
# "false" flag is made.
#
# Setup: invented captions with three claims; a fake Fact Check Tools API that finds nothing; a fake Claude
# that lists the three claims and judges all three "false" with a dated source: the unemployment claim with
# the three measures of tests/golden/empleo.json (SEPE and SEPE-based measures tier 2, EPA tier 1) and a
# controversy line; the rent claim with one newspaper measure (tier 5) against it; the EPA rate claim with
# one INE measure (tier 1) against it; a temporary helper home.

PARO = "tenemos casi tres millones y medio de parados registrados"
ALQUILER = "el alquiler subió un cuarenta por ciento el último año"
EPA = "el paro bajó al ocho por ciento en el tercer trimestre"
CONTROVERSY = ("El paro registrado no cuenta a los fijos discontinuos inactivos, unos 0,9 millones "
               "(SEPE, BBVA Research).")
PARO_MEASURES = [
    {"name": "paro registrado (SEPE)", "value": "2.443.766", "source": "SEPE, octubre 2025", "tier": 2,
     "supports": False},
    {"name": "paro registrado + demandantes con relación laboral", "value": "unos 3,3 millones",
     "source": "SEPE, octubre 2025", "tier": 2, "supports": True},
    {"name": "parados EPA", "value": "2.613.200", "source": "INE, EPA 3T 2025", "tier": 1, "supports": False},
]


class FakeTranscript_s6a1:
    def fetch(self, video_id):
        return Transcript(segments=words(0, PARO) + words(10, ALQUILER) + words(20, EPA), published_at="2025-11-10")


def verdict_s6a1(quote, publisher, url, measures, controversy=None):
    return {"quote": quote, "verdict": "false", "reason": "Las fuentes dan otra cifra.", "confidence": 0.9,
            "sources": [{"publisher": publisher, "url": url, "date": "2025-11-04"}], "note": None,
            "published": [], "measures": measures, "controversy": controversy}


class FakeClaude_s6a1:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                verdict_s6a1(PARO, "SEPE", "https://www.sepe.es/paro-octubre-2025", PARO_MEASURES, CONTROVERSY),
                verdict_s6a1(ALQUILER, "El Diario Económico", "https://example.org/alquiler",
                        [{"name": "precio del alquiler", "value": "+11 %", "source": "El Diario Económico",
                          "tier": 5, "supports": False}]),
                verdict_s6a1(EPA, "INE", "https://www.ine.es/epa",
                        [{"name": "tasa de paro EPA", "value": "10,45 %", "source": "INE, EPA 3T 2025", "tier": 1,
                          "supports": False}]),
            ]}
        return {"flags": [], "claims": [{"quote": q, "speaker": "Invitado", "queries": [q]}
                                        for q in (PARO, ALQUILER, EPA)]}


def test_disputed_not_false(tmp_path):
    run_analysis("disputed", 0, transcript=FakeTranscript_s6a1(), llm=FakeClaude_s6a1(), factcheck=NoPublishedChecks(),
                 home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "disputed.json").read_text())["flags"]
    by_quote = {f["quote"]: f for f in flags if f["type"] == "inaccuracy"}

    # Case 1 · one credible measure supports the figure, two contradict it → one disputed flag with the three
    # measures and the controversy line, not false
    paro = by_quote[PARO]
    assert paro["label"] == "disputed", paro
    assert paro["measures"] == PARO_MEASURES
    assert paro["controversy"] == CONTROVERSY

    # Case 2 · the only measure against the claim comes from a newspaper → no false flag
    assert by_quote.get(ALQUILER, {}).get("label") != "false", by_quote[ALQUILER]

    # Case 3 · every credible measure contradicts the claim → false
    assert by_quote[EPA]["label"] == "false"
    print("PASS S6 A1 · A figure that a credible measure supports is disputed, not false")


# S9 A1 · A claim about one's own earlier words that the record contradicts is flagged with the earlier statement
#
# Story: In an invented interview, the guest says "yo nunca dije que no pactaría con ese partido". The check
# finds a dated interview in a newspaper where the guest said "no pactaré con ese partido". The flag file has
# a contradiction flag with the label "record", quoting the guest, with the earlier statement, its date and
# its link.
# Edge case: when the earlier statement has no date that a source confirms, no flag is made.
#
# Setup: invented word-by-word captions with two claims of the guest about their own earlier words: the pact
# (at 0 s) and taxes (at 10 s); a fake Fact Check Tools API that finds nothing; a fake Claude whose part
# call lists both claims as "own_words", and whose check call judges both "false" with an earlier
# statement: the pact one dated 2023-07-02 in El Diario with its link, the taxes one with no date and an
# undated source; a temporary helper home.

PACT = "yo nunca dije que no pactaría con ese partido"
TAXES = "nunca he dicho que bajaría los impuestos"
EARLIER = "no pactaré con ese partido"
URL = "https://example.org/el-diario/entrevista-2023-07-02"
REASON = "En julio de 2023 dijo en una entrevista que no pactaría con ese partido."


class FakeTranscript_s9a1:
    def fetch(self, video_id):
        return Transcript(segments=words(0, PACT) + words(10, TAXES), published_at="2026-11-10")


def verdict_s9a1(quote, earlier, sources):
    return {"quote": quote, "verdict": "false", "reason": REASON, "confidence": 0.9, "sources": sources,
            "note": None, "measures": [], "controversy": None, "published": [], "earlier": earlier,
            "promise": None}


class FakeClaude_s9a1:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, schema, tools=()):
        self.prompts.append(prompt)
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                verdict_s9a1(PACT, {"quote": EARLIER, "date": "2023-07-02", "publisher": "El Diario", "url": URL},
                        [{"publisher": "El Diario", "url": URL, "date": "2023-07-02"}]),
                verdict_s9a1(TAXES, {"quote": "bajaremos los impuestos", "date": None, "publisher": "Un blog",
                                "url": "https://example.org/blog"},
                        [{"publisher": "Un blog", "url": "https://example.org/blog", "date": None}]),
            ]}
        return {"flags": [], "questions": [], "contradictions": [],
                "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "own_words"}
                           for q in (PACT, TAXES)]}


def test_record_contradiction(tmp_path):
    claude = FakeClaude_s9a1()
    run_analysis("record", 0, transcript=FakeTranscript_s9a1(), llm=claude, factcheck=NoPublishedChecks(), home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "record.json").read_text())["flags"]
    by_quote = {f["quote"]: f for f in flags}

    # Case 1 · a dated newspaper interview contradicts the guest's claim about their own words → a
    # contradiction flag "record" quoting the guest, with the earlier statement, its date and its link
    flag = by_quote.get(PACT)
    assert flag, flags
    assert flag["type"] == "contradiction"
    assert flag["label"] == "record"
    assert flag["t"] == 0
    assert flag["speaker"] == "Invitado"
    assert flag["related"]["quote"] == EARLIER
    assert flag["related"]["date"] == "2023-07-02"
    assert flag["related"]["source"] == {"publisher": "El Diario", "url": URL}
    assert {"publisher": "El Diario", "url": URL, "date": "2023-07-02"} in flag["sources"]
    assert flag["reason"] == REASON

    # Case 2 · the earlier statement has no date that a source confirms → no flag
    assert TAXES not in by_quote, by_quote[TAXES]

    # Case 3 · the record is checked in the check tool call of the part, which knows the claim is about
    # the speaker's own words → two Claude tool calls in all
    assert len(claude.prompts) == 2
    assert "own_words" in next(line for line in claude.prompts[1].splitlines() if PACT in line)
    print("PASS S9 A1 · A claim about one's own earlier words that the record contradicts is flagged with the "
          "earlier statement")


# S9 A2 · A promise shows when it was made, its figure, its deadline and its status
#
# Story: In an invented interview, the guest says "hemos cumplido lo que prometimos en vivienda". The check
# finds the promise of 184,000 homes made in April 2023 for 2026, and that far fewer are delivered. The flag
# file has a contradiction flag with the label "promise" that holds the date of the promise, the figure, the
# deadline, the status "not met" and a dated source.
# Edge cases: a promise that the check finds met or still in progress makes no flag; a promise that is
# partly met makes a flag; a promise whose only source has no date makes no flag.
#
# Setup: invented word-by-word captions with five claims of the guest about promises: homes (0 s), teachers
# (10 s), trains (20 s), hospitals (30 s) and roads (40 s); a fake Fact Check Tools API that finds nothing; a
# fake Claude whose part call lists the five claims as "promise", and whose check call judges them: homes
# "false", status "not met", dated source; teachers "true", status "met", dated source; trains "false",
# status "not met", undated source; hospitals "misleading", status "partly met", dated source; roads
# "misleading", status "in progress", dated source; a temporary helper home.

HOMES = "hemos cumplido lo que prometimos en vivienda"
TEACHERS = "contratamos a los profesores que prometimos"
TRAINS = "terminamos la línea de tren que prometimos"
HOSPITALS = "abrimos todos los hospitales que prometimos"
ROADS = "las carreteras que prometimos ya están hechas"
HOMES_PROMISE = {"made": "2023-04", "figure": "184.000 viviendas", "deadline": "2026", "status": "not met"}
SOURCE = {"publisher": "El País", "url": "https://example.org/el-pais/viviendas-2025", "date": "2025-09-15"}


class FakeTranscript_s9a2:
    def fetch(self, video_id):
        return Transcript(segments=words(0, HOMES) + words(10, TEACHERS) + words(20, TRAINS)
                          + words(30, HOSPITALS) + words(40, ROADS), published_at="2026-11-10")


def verdict_s9a2(quote, answer, promise, source):
    return {"quote": quote, "verdict": answer, "reason": "Se entregaron muchas menos viviendas de las prometidas.",
            "confidence": 0.9, "sources": [source], "note": None, "measures": [], "controversy": None,
            "published": [], "earlier": None, "promise": promise}


class FakeClaude_s9a2:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                verdict_s9a2(HOMES, "false", HOMES_PROMISE, SOURCE),
                verdict_s9a2(TEACHERS, "true",
                        {"made": "2022-01", "figure": "5.000 profesores", "deadline": "2024", "status": "met"},
                        SOURCE | {"url": "https://example.org/profesores"}),
                verdict_s9a2(TRAINS, "false",
                        {"made": "2021-03", "figure": "una línea", "deadline": "2025", "status": "not met"},
                        {"publisher": "Un blog", "url": "https://example.org/blog", "date": None}),
                verdict_s9a2(HOSPITALS, "misleading",
                        {"made": "2022-05", "figure": "10 hospitales", "deadline": "2025", "status": "partly met"},
                        SOURCE | {"url": "https://example.org/hospitales"}),
                verdict_s9a2(ROADS, "misleading",
                        {"made": "2024-02", "figure": "300 km", "deadline": "2027", "status": "in progress"},
                        SOURCE | {"url": "https://example.org/carreteras"}),
            ]}
        return {"flags": [], "questions": [], "contradictions": [],
                "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "promise"}
                           for q in (HOMES, TEACHERS, TRAINS, HOSPITALS, ROADS)]}


def test_promise_status(tmp_path):
    run_analysis("promise", 0, transcript=FakeTranscript_s9a2(), llm=FakeClaude_s9a2(), factcheck=NoPublishedChecks(),
                 home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "promise.json").read_text())["flags"]
    by_quote = {f["quote"]: f for f in flags}

    # Case 1 · the guest says the homes promise was kept, the check finds it not met → a contradiction flag
    # "promise" with the date it was made, the figure, the deadline, the status and a dated source
    flag = by_quote.get(HOMES)
    assert flag, flags
    assert flag["type"] == "contradiction"
    assert flag["label"] == "promise"
    assert flag["speaker"] == "Invitado"
    assert flag["promise"] == HOMES_PROMISE
    assert flag["sources"] == [SOURCE]

    # Case 2 · the teachers promise is met → no flag
    assert TEACHERS not in by_quote, by_quote[TEACHERS]

    # Case 3 · the trains promise is not met, but its only source has no date → no flag
    assert TRAINS not in by_quote, by_quote[TRAINS]

    # Case 4 · the hospitals promise is partly met → a promise flag with the status "partly met"
    assert by_quote.get(HOSPITALS, {}).get("label") == "promise", flags
    assert by_quote[HOSPITALS]["promise"]["status"] == "partly met"

    # Case 5 · the roads promise is still in progress → no promise flag
    assert by_quote.get(ROADS, {}).get("label") != "promise", by_quote[ROADS]
    print("PASS S9 A2 · A promise shows when it was made, its figure, its deadline and its status")


# S16 A3 · Every extracted figure is logged with what happened to it
#
# Story: A part of an invented video yields three figures: one becomes a "Dato falso" flag, one checks out as right,
# and one is cut by the budget. The claims log of the video has three lines with their second, speaker and outcome:
# `flagged`, `ok` and `unchecked`.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
# gives three figures in its only part (0-30 s). A fake Fact Check Tools API that finds nothing. A fake Claude whose
# part tool call lists the three figures as claims, and whose fact-check tool call (the one with web tools) gives a
# false verdict with a dated source and a tier-1 measure against for the first figure, a true verdict for the second,
# and no verdict for the third, as when the check runs out of its budget. A second run gives the run a budget of one
# Claude tool call (scheduler.CALLS_PER_HOUR = 1), so the budget refuses the fact-check tool call of the part. A
# temporary helper home per run.

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FALSE_s16a3 = "el paro bajó a la mitad en un año"
TRUE = "la inflación cerró el año en el dos por ciento"
CUT = "hay tres millones de viviendas vacías"
LINES = [
    (0, GUEST, f"Mire {FALSE_s16a3} y además {TRUE} y le digo más {CUT} en España"),
    (20, HOST, "Muchas gracias por venir y buenas noches"),
]
WORDS = LINES[0][2].split()
SECONDS = {q: next(i * 0.5 for i in range(len(WORDS)) if WORDS[i:i + len(q.split())] == q.split())
           for q in (FALSE_s16a3, TRUE, CUT)}


class FakeTranscript_s16a3:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


def verdict_s16a3(quote, value, measures):
    return {"quote": quote, "verdict": value, "reason": "Razón inventada.", "confidence": 0.9,
            "sources": [{"publisher": "INE", "url": f"https://www.ine.es/{len(quote)}", "date": "2026-10-01"}],
            "note": None, "measures": measures, "controversy": None, "published": [], "earlier": None,
            "promise": None}


class FakeClaude_s16a3:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            against = {"name": "Paro EPA", "value": "1", "source": "INE", "tier": 1, "supports": False}
            return {"verdicts": [verdict_s16a3(FALSE_s16a3, "false", [against]), verdict_s16a3(TRUE, "true", [])]}
        part = prompt.split("PART:")[-1]
        return {"flags": [], "questions": [], "contradictions": [], "context": [],
                "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "fact"}
                           for q in (FALSE_s16a3, TRUE, CUT) if q in part]}


def analyse(home):
    run_analysis("cifras", 0, transcript=FakeTranscript_s16a3(), llm=FakeClaude_s16a3(), factcheck=NoPublishedChecks(), home=home)
    data = json.loads((home / "videos" / "cifras.json").read_text())
    log = home / "claims.jsonl"
    rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return data, rows


def test_claims_log(tmp_path, monkeypatch):
    data, rows = analyse(tmp_path / "checked")

    # Case 1 · a part yields three figures: one false, one right and one without a verdict → three lines in the
    # claims log, each with the video, the second of the figure, its speaker and its outcome
    assert sorted((r["t"], r["outcome"]) for r in rows) == [
        (SECONDS[FALSE_s16a3], "flagged"), (SECONDS[TRUE], "ok"), (SECONDS[CUT], "unchecked")], rows
    for r in rows:
        assert r["video_id"] == "cifras" and r["speaker"] == "Invitado", r

    # Case 2 · the flagged figure → a "Dato falso" flag in the flag file at the same second
    assert [(f["t"], f["label"]) for f in data["flags"] if f["type"] == "inaccuracy"] == [(SECONDS[FALSE_s16a3], "false")]

    # Case 3 · the claims log holds no transcript → no quote and no words of a figure in any line
    for r in rows:
        assert set(r) == {"video_id", "t", "speaker", "outcome"}, r
        for quote in (FALSE_s16a3, TRUE, CUT):
            assert quote not in json.dumps(r, ensure_ascii=False), r

    # Case 4 · the budget refuses the fact-check tool call of the part → its three figures are logged `unchecked`
    monkeypatch.setattr(scheduler, "CALLS_PER_HOUR", 1)
    data, rows = analyse(tmp_path / "budget")
    assert data["stop_reason"] == "budget", data["stop_reason"]
    assert sorted((r["t"], r["outcome"]) for r in rows) == [
        (SECONDS[FALSE_s16a3], "unchecked"), (SECONDS[TRUE], "unchecked"), (SECONDS[CUT], "unchecked")], rows
    print("PASS S16 A3 · Every extracted figure is logged with what happened to it")


# S17 A2 · Only central figures are checked, each once per video
#
# Story: Parts of an invented video yield five figures: one said in passing, one that carries the guest's argument,
# and the same central figure said again ten minutes later in other words, plus two more central ones. Three are
# checked; the passing one is logged `skipped`, and the repeated one `repeated`, pointing to the first.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 12-minute interview. In the part 0:00-0:30 the
# guest ("Invitado") gives a figure in passing and two central figures; in the part that holds minute 11 he says the
# first central figure again in other words, and one more central figure. A fake Fact Check Tools API that finds
# nothing. A fake Claude: its part tool call lists the figures of the PART, marks the passing one as not central, and
# marks the repeated one as a repeat of the line of the already checked figures that holds the first central figure;
# its fact-check tool call finds every figure it gets right. The parts run one at a time (scheduler.PARALLEL = 1), so
# the part of minute 11 runs after the first part. A temporary helper home.

PASSING = "hace dos años había veinte mil autobuses"
FIRST = "el paro bajó a la mitad en un año"
SECOND_ONE = "la inflación cerró el año en el dos por ciento"
REPEAT = "el desempleo se redujo a la mitad en doce meses"
THIRD = "hay tres millones de viviendas vacías"
LINES_s17a2 = [
    (0, GUEST, f"Como {PASSING} le digo que {FIRST} y que {SECOND_ONE} en España"),
    (20, HOST, "Muchas gracias y sigamos con la vivienda"),
    (660, GUEST, f"Insisto en que {REPEAT} y además {THIRD} en este país"),
    (680, HOST, "Muchas gracias por venir y buenas noches"),
]
CENTRAL = (FIRST, SECOND_ONE, REPEAT, THIRD)


def second(quote):
    for start, _, text in LINES_s17a2:
        words = text.split()
        for i in range(len(words)):
            if words[i:i + len(quote.split())] == quote.split():
                return start + i * 0.5


class FakeTranscript_s17a2:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES_s17a2 for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class FakeClaude_s17a2:
    def __init__(self):
        self.part_prompts = []
        self.check_prompts = []

    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            self.check_prompts.append(prompt)
            return {"verdicts": [
                {"quote": q, "verdict": "true", "reason": "Correcto.", "confidence": 0.9,
                 "sources": [{"publisher": "INE", "url": "https://www.ine.es/x", "date": "2026-10-01"}],
                 "note": None, "measures": [], "controversy": None, "published": [], "earlier": None, "promise": None}
                for q in (PASSING, *CENTRAL) if q in prompt]}
        self.part_prompts.append(prompt)
        head, _, part = prompt.rpartition("PART:")
        listed = next((line for line in head.splitlines() if FIRST in line and re.match(r"\s*\d+\.", line)), None)
        claims = []
        for q in (PASSING, *CENTRAL):
            if q in part:
                repeats = int(re.match(r"\s*(\d+)\.", listed)[1]) if q == REPEAT and listed else None
                claims.append({"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "fact",
                               "central": q != PASSING, "repeats": repeats})
        return {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [], "claims": claims}


def test_claim_triage(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    claude = FakeClaude_s17a2()
    run_analysis("triaje", 0, transcript=FakeTranscript_s17a2(), llm=claude, factcheck=NoPublishedChecks(), home=tmp_path)
    data = json.loads((tmp_path / "videos" / "triaje.json").read_text())
    rows = [json.loads(line) for line in (tmp_path / "claims.jsonl").read_text().splitlines()]
    assert data["status"] == "done", data

    # Case 1 · the part of minute 11 → its prompt lists the central figure already checked in the first part
    later = next(p for p in claude.part_prompts if REPEAT in p.rpartition("PART:")[2])
    assert any(FIRST in line and re.match(r"\s*\d+\.", line) for line in later.rpartition("PART:")[0].splitlines()), \
        "the first central figure is not listed as already checked"

    # Case 2 · five figures → only the three distinct central ones reach a fact-check tool call
    checked = "\n".join(claude.check_prompts)
    assert all(q in checked for q in (FIRST, SECOND_ONE, THIRD)), checked
    assert PASSING not in checked and REPEAT not in checked, checked

    # Case 3 · the claims log → the passing figure `skipped`, the repeated one `repeated` with the second of the first
    # one, the three checked ones `ok`
    outcomes = {r["t"]: r for r in rows}
    assert len(rows) == 5, rows
    assert outcomes[second(PASSING)]["outcome"] == "skipped", rows
    assert outcomes[second(REPEAT)]["outcome"] == "repeated", rows
    assert outcomes[second(REPEAT)]["repeats"] == second(FIRST), rows
    for q in (FIRST, SECOND_ONE, THIRD):
        assert outcomes[second(q)]["outcome"] == "ok", (q, rows)

    # Case 4 · the claims log still holds no transcript → no quote of a figure in any line
    for r in rows:
        assert r["video_id"] == "triaje" and r["speaker"] == "Invitado", r
        for q in (PASSING, *CENTRAL):
            assert q not in json.dumps(r, ensure_ascii=False), r
    print("PASS S17 A2 · Only central figures are checked, each once per video")


# S17 A3 · A cheaper model searches, Opus judges
#
# Story: For a part with two central figures, one reading by Haiku (S29) with web search returns the evidence with its
# sources, and one reading by Opus with no tools turns that evidence into verdicts. A false figure still shows as
# "Dato falso" with the same sources.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 30-second interview in which SPEAKER_01 ("Invitado")
# gives two figures that carry his argument: one false, one right. The helper runs as it does for the person
# (Helper._run), with a fake YouTube that returns these captions, a fake Fact Check Tools API that finds nothing and no
# voices. The `claude` command is a fake on PATH: it writes the model, tools and prompt of each reading to a log, and
# answers by the JSON schema it gets. The search answer gives one dated source for each figure. The verdict answer calls
# the first figure false, citing the search's source and one more link that the search never found, and the second
# figure true. A temporary helper home.

LINES_s17a3 = [
    (0, GUEST, f"Mire {FALSE_s16a3} y además {TRUE} y eso lo cambia todo"),
    (20, HOST, "Muchas gracias por venir y buenas noches"),
]
WORDS_s17a3 = LINES_s17a3[0][2].split()
SECOND = WORDS_s17a3.index(FALSE_s16a3.split()[0]) * 0.5
INE = {"publisher": "INE", "url": "https://www.ine.es/paro", "date": "2026-10-01"}
EUROSTAT = {"publisher": "Eurostat", "url": "https://ec.europa.eu/eurostat/ipc", "date": "2026-10-15"}
UNSEEN = {"publisher": "Un blog", "url": "https://example.org/inventado", "date": "2026-09-01"}


def verdict_s17a3(quote, value, sources, measures):
    return {"quote": quote, "verdict": value, "reason": "Razón inventada.", "confidence": 0.9, "sources": sources,
            "note": None, "controversy": None, "published": [], "earlier": None, "promise": None, "measures": measures}


ANSWERS = {
    "flags": {"flags": [], "questions": [], "contradictions": [], "positions": [], "context": [],
              "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "fact",
                          "central": True, "repeats": None} for q in (FALSE_s16a3, TRUE)]},
    "evidence": {"evidence": [
        {"quote": FALSE_s16a3, "findings": [INE | {"says": "La tasa de paro bajó del 12 % al 11 %."}]},
        {"quote": TRUE, "findings": [EUROSTAT | {"says": "El IPC armonizado cerró en el 2,0 %."}]}]},
    "verdicts": {"verdicts": [
        verdict_s17a3(FALSE_s16a3, "false", [INE, UNSEEN],
                [{"name": "Paro EPA", "value": "11 %", "source": "INE", "tier": 1, "supports": False}]),
        verdict_s17a3(TRUE, "true", [EUROSTAT],
                [{"name": "IPCA", "value": "2,0 %", "source": "Eurostat", "tier": 1, "supports": True}])]},
    "rulings": {"rulings": []},
}

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
schema = json.loads(opt("--json-schema"))
answers = json.load(open(os.environ["FAKE_CLAUDE_ANSWERS"]))
key = next(k for k in answers if k in schema["properties"])
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({"answer": key, "model": opt("--model"), "tools": opt("--tools"), "prompt": opt("-p")}) + "\\n")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "num_turns": 1, "duration_ms": 1000, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 3, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0,
                            "output_tokens": 10}, "result": json.dumps(answers[key]),
                  "structured_output": answers[key]}))
"""


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES_s17a3 for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class NoPublishedChecks_s17a3:
    def __init__(self, key):
        pass

    def search(self, query, language):
        return []


def test_search_then_judge(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "answers.json").write_text(json.dumps(ANSWERS))
    log = tmp_path / "readings.jsonl"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_ANSWERS", str(tmp_path / "answers.json"))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FACT_CHECK_API_KEY", "invented")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "GoogleFactCheck", NoPublishedChecks_s17a3)
    home = tmp_path / "home"
    home.mkdir()

    server.Helper(home)._run("dos", 0)
    data = json.loads((home / "videos" / "dos.json").read_text())
    readings = [json.loads(x) for x in log.read_text().splitlines()]
    assert data["status"] == "done", data

    # Case 1 · a part with two central figures → one search reading, by Haiku with web search, for both figures
    search = [r for r in readings if r["answer"] == "evidence"]
    assert len(search) == 1, [r["answer"] for r in readings]
    assert search[0]["model"] == "haiku", search[0]["model"]
    assert set(search[0]["tools"].split(",")) == {"WebSearch", "WebFetch"}, search[0]["tools"]
    assert FALSE_s16a3 in search[0]["prompt"] and TRUE in search[0]["prompt"]

    # Case 2 · the evidence → one verdict reading, by Opus with no tools, that gets both figures and the sources
    # that the search found
    checks = [r for r in readings if r["answer"] == "verdicts"]
    assert len(checks) == 1, [r["answer"] for r in readings]
    assert checks[0]["model"] == "opus", checks[0]["model"]
    assert checks[0]["tools"] == "", checks[0]["tools"]
    for text in (FALSE_s16a3, TRUE, INE["url"], EUROSTAT["url"]):
        assert text in checks[0]["prompt"], text

    # Case 3 · the false figure → one "Dato falso" flag at its second, with the source that the search found and
    # not the link that it never found; the right figure → no flag
    found = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["t"], f["label"], f["quote"]) for f in found] == [(SECOND, "false", FALSE_s16a3)], found
    assert found[0]["sources"] == [INE], found[0]["sources"]
    print("PASS S17 A3 · A cheaper model searches, Opus judges")


# S29 A2 · The figure search runs on the cheap model
#
# Story: With no settings file, the same interview's false figure is searched by `haiku` with web search, and its verdict
# is given by `opus`. With `provider = "anthropic"`, the search reading goes to `claude-haiku-5-5` with the web search
# tool and the verdict to `claude-opus-5-5`.
#
# Setup: the invented three-part interview of the S29 fakes (a greeting, a false figure, a stated position). The helper
# runs as it does for the person (Helper._run), with a fake YouTube, a fake Fact Check Tools API that finds nothing and
# no voices. Case 1: the `claude` command is a fake on PATH that logs the kind, model and tools of each reading. Case 2:
# `config.toml` says `provider = "anthropic"` with `[anthropic] base_url` on a fake Messages API on a free local port that
# records each request; ANTHROPIC_API_KEY is in the home's `.env`; the `claude` and `codex` commands fail. A temporary
# helper home per run.

def test_cheap_search(tmp_path, monkeypatch):
    fake_video(monkeypatch)

    # Case 1 · no settings → the search reading by haiku with WebSearch, the verdict by opus with no tool
    run = tmp_path / "default"
    home = run / "home"
    home.mkdir(parents=True)
    claude_log, _ = fake_clis(run, monkeypatch)
    server.Helper(home)._run("search1", 0)
    data = json.loads((home / "videos" / "search1.json").read_text())
    readings = jsonl(claude_log)
    assert data["status"] == "done", data
    search = [(r["model"], r["tools"]) for r in readings if r["kind"] == "evidence"]
    verdict = [(r["model"], r["tools"]) for r in readings if r["kind"] == "verdicts"]
    assert len(search) == 1 and search[0][0] == "haiku" and "WebSearch" in search[0][1], \
        f"FAIL S29 A2 · search readings {search}"
    assert verdict == [("opus", "")], f"FAIL S29 A2 · verdict readings {verdict}"
    assert [(f["label"], f["quote"]) for f in data["flags"] if f["type"] == "inaccuracy"] == [("false", FALSE)], data

    # Case 2 · provider anthropic → the search request to claude-haiku-5-5 with the web search tool, the verdict
    # request to claude-opus-5-5 with no tool
    run = tmp_path / "anthropic"
    home = run / "home"
    home.mkdir(parents=True)
    _, cli_log = fake_clis(run, monkeypatch, claude=False)
    api = FakeMessagesAPI()
    (home / "config.toml").write_text(f'provider = "anthropic"\n[anthropic]\nbase_url = "{api.url}"\n')
    (home / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-invented\n")
    server.Helper(home)._run("search2", 0)
    api.stop()
    data = json.loads((home / "videos" / "search2.json").read_text())
    assert data["status"] == "done", data
    assert not cli_log.exists(), cli_log.read_text()
    kinds = api.kinds()
    search = [(b["model"], [t["type"] for t in b.get("tools", [])]) for k, b in kinds if k == "evidence"]
    verdict = [(b["model"], b.get("tools")) for k, b in kinds if k == "verdicts"]
    assert len(search) == 1 and search[0][0] == "claude-haiku-5-5" and search[0][1][0].startswith("web_search"), \
        f"FAIL S29 A2 · search requests {search}"
    assert verdict == [("claude-opus-5-5", None)], f"FAIL S29 A2 · verdict requests {verdict}"
    print("PASS S29 A2 · The figure search runs on the cheap model")


# A network error in the search for published fact-checks does not stop the analysis of the video.

QUOTE = "la oposición no tiene ninguna autoridad moral"


class FakeTranscript_published_search_failure:
    def fetch(self, video_id):
        return Transcript(segments=[Segment(t=i * 0.5, text=w) for i, w in enumerate(QUOTE.split())],
                          published_at="2026-11-10")


class FailingGoogle:
    def search(self, query, language):
        raise ConnectionResetError(54, "Connection reset by peer")


class FakeClaude_published_search_failure:
    def complete(self, prompt, schema, tools=()):
        if tools:
            return {"verdicts": []}
        return {"flags": [{"quote": QUOTE, "label": "ad_hominem", "speaker": "Invitado",
                           "reason": "Ataca a la persona.", "confidence": 0.9}],
                "claims": [{"quote": QUOTE, "speaker": "Invitado", "queries": ["oposición autoridad"]}]}


def test_search_failure_keeps_analysis(tmp_path):
    run_analysis("reset", 0, transcript=FakeTranscript_published_search_failure(), llm=FakeClaude_published_search_failure(), factcheck=FailingGoogle(),
                 home=tmp_path, thresholds={})
    data = json.loads((tmp_path / "videos" / "reset.json").read_text())
    assert data["status"] == "done", data["stop_reason"]
    assert [f["label"] for f in data["flags"]] == ["ad_hominem"]


# Without the Google Fact Check key, figures are still checked by web search: only published fact-checks are missing.
#
# A helper restarted without that key once read three whole interviews and checked no figure at all.

VIDEO = "sinclave123"


def test_figures_checked_without_google_key(tmp_path, monkeypatch):
    fake_video(monkeypatch)
    monkeypatch.delenv("FACT_CHECK_API_KEY")
    home = tmp_path / "home"
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    claude_log, _ = fake_clis(tmp_path / "run", monkeypatch)
    monkeypatch.setattr(sys, "argv", ["fact-checker", "analyze", f"https://www.youtube.com/watch?v={VIDEO}"])

    cli.main()

    data = json.loads((home / "videos" / f"{VIDEO}.json").read_text())
    assert [f["quote"] for f in data["flags"] if f["type"] == "inaccuracy"] == [FALSE]
    assert "verdicts" in {r["kind"] for r in jsonl(claude_log)}
    assert [c["outcome"] for c in jsonl(home / "claims.jsonl")] == ["flagged"]
