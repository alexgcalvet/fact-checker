"""The reading: what a part reading flags, with the text before it as context, and the cheap screen before it."""
import json
import os
import re
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from fact_checker import server
from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fact_checker.adapters.youtube import parse_json3
from fact_checker.core import scheduler
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis
from language_fakes import ATTACK, FactCheck, FALSE, readings, setup, text
from screen_fakes import fake_clis, fake_video, FALSE as FALSE_screen, GREETING, jsonl


# S1 A2 · Flags quote the exact words, at their second, from the closed list only
#
# Story: From an invented 4-minute dialogue with 3 planted fallacies, the analysis returns flags whose
# words appear word for word in the captions, whose second is when those words start, and whose name is
# one of the 8 in the list. A name outside the list, or words that are not in the captions, give no flag;
# an out-of-list name goes to the candidates log with its words.
#
# Setup: the invented captions in tests/fakes/youtube/, parsed by the YouTube adapter; a fake Claude that
# answers every part with the same five flags (three valid, one outside the list, one invented quote),
# written with capitals and punctuation as a model would; a temporary helper home.

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-dialogue.json3"

SCRIPTED = [
    {"quote": "La oposición no tiene autoridad para hablar.", "label": "ad_hominem", "speaker": "minister",
     "reason": "Attacks the critic instead of the criticism.", "confidence": 0.9},
    {"quote": "Ustedes, cuando gobernaron, subieron más los alquileres", "label": "tu_quoque", "speaker": "minister",
     "reason": "Answers a criticism by pointing at the critic's past.", "confidence": 0.85},
    {"quote": "O aprobamos nuestra ley o los alquileres seguirán subiendo", "label": "false_dilemma", "speaker": "minister",
     "reason": "Presents two options when there are more.", "confidence": 0.82},
    {"quote": "Piense en las familias que lo están pasando mal", "label": "appeal_to_emotion", "speaker": "minister",
     "reason": "Appeals to emotion.", "confidence": 0.7},
    {"quote": "Esta frase nunca se dijo en el programa", "label": "straw_man", "speaker": "host",
     "reason": "Invented.", "confidence": 0.95},
]


class FakeTranscript_s1a2:
    def fetch(self, video_id):
        return parse_json3(json.loads(FAKE.read_text()), published_at="2026-11-10")


class FakeClaude:
    def complete(self, prompt, schema):
        return {"flags": [dict(f) for f in SCRIPTED]}


def test_flags_from_captions(tmp_path):
    run_analysis("invented", 0, transcript=FakeTranscript_s1a2(), llm=FakeClaude(), home=tmp_path)
    data = json.loads((tmp_path / "videos" / "invented.json").read_text())
    by_label = {f["label"]: f for f in data["flags"]}

    # Case 1 · three valid fallacies → exactly three flags, one per planted fallacy, none duplicated
    assert data["status"] == "done"
    assert sorted(by_label) == ["ad_hominem", "false_dilemma", "tu_quoque"]
    assert len(data["flags"]) == 3

    # Case 2 · each flag quotes the caption words, not the model's punctuation → exact caption text
    assert by_label["ad_hominem"]["quote"] == "la oposición no tiene autoridad para hablar"
    assert by_label["tu_quoque"]["quote"] == "ustedes cuando gobernaron subieron más los alquileres"
    assert by_label["false_dilemma"]["quote"] == "o aprobamos nuestra ley o los alquileres seguirán subiendo"

    # Case 3 · each flag's second is when its first word starts → 42, 62 and 168 seconds
    assert abs(by_label["ad_hominem"]["t"] - 42.0) < 0.01
    assert abs(by_label["tu_quoque"]["t"] - 62.0) < 0.01
    assert abs(by_label["false_dilemma"]["t"] - 168.0) < 0.01
    for f in data["flags"]:
        assert f["type"] == "fallacy" and f["reason"] and 0 <= f["confidence"] <= 1

    # Case 4 · a name outside the list → no flag, one line in the candidates log with its words
    lines = [json.loads(x) for x in (tmp_path / "candidates.log").read_text().splitlines()]
    assert [(c["label"], c["quote"]) for c in lines] == [
        ("appeal_to_emotion", "piense en las familias que lo están pasando mal")]

    # Case 5 · words that are not in the captions → no flag and no candidate
    assert all("nunca se dijo" not in f["quote"] for f in data["flags"])
    print("PASS S1 A2 · Flags quote the exact words, at their second, from the closed list only")


# S7 A1 · A dodged question is flagged at the end of its answer
#
# Story: In an invented interview, the host asks "¿cuántas viviendas se han entregado?" and the guest talks
# about the housing law. When the helper analyses it, the flag file has a "question" flag with status
# "dodged" at the second the answer ends; it holds the host's question and a reason.
# Edge case: when the guest answers with another figure, "184.000 viviendas entregadas o en proceso", the
# question is still "dodged".
#
# Setup: invented word-by-word captions (one word every 0.5 s) of four questions and their answers over two
# parts (0-30 s and 30-150 s); the third question sits in the first part and its answer ends in the second.
# A fake Claude that, in each part call, lists the questions whose answer ends in that PART: the first three
# dodged (the second because it gives another figure), the fourth answered; it lists no fallacy and no
# claim. The real bars of thresholds.json (no bar for questions); a temporary helper home.

Q1 = "¿Cuántas viviendas se han entregado?"
A1 = "Mire lo importante es que hemos aprobado la primera ley de vivienda de la democracia"
Q2 = "¿Y cuántas se han terminado este año?"
A2 = "Tenemos 184.000 viviendas entregadas o en proceso"
Q3 = "¿Cuándo bajarán los alquileres?"
A3 = "Lo que le digo es que la oposición votó en contra de todas nuestras medidas"
Q4 = "¿Mantendrá el bono joven?"
A4 = "Sí lo mantendremos el año que viene con el mismo importe"
LINES = [(0, Q1), (3, A1), (14, Q2), (18, A2), (25, Q3), (31, A3), (40, Q4), (43, A4)]


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


def end(start, text):
    return start + (len(text.split()) - 1) * 0.5


def tail(text, n=5):
    return " ".join(text.split()[-n:])


class FakeTranscript_s7a1:
    def fetch(self, video_id):
        return Transcript(segments=[s for start, text in LINES for s in words(start, text)], published_at="2026-11-10")


def question(q, a, status, confidence):
    return {"question": q, "answer_end": tail(a), "speaker": "Invitado", "status": status,
            "reason": f"Se preguntó «{q}» y la respuesta no lo dice.", "confidence": confidence}


QUESTIONS = [question(Q1, A1, "dodged", 0.9), question(Q2, A2, "dodged", 0.7), question(Q3, A3, "dodged", 0.85),
             question(Q4, A4, "answered", 0.9)]


class FakeClaude_s7a1:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, schema, tools=()):
        self.calls += 1
        part = prompt.split("PART:")[-1]
        return {"flags": [], "claims": [], "questions": [q for q in QUESTIONS if q["answer_end"] in part]}


def test_dodged_question(tmp_path):
    claude = FakeClaude_s7a1()
    run_analysis("questions", 0, transcript=FakeTranscript_s7a1(), llm=claude, home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "questions.json").read_text())["flags"]
    questions = [f for f in flags if f["type"] == "question"]
    by_question = {f["related"]["quote"]: f for f in questions}

    # Case 1 · the guest talks about the housing law → a dodged question flag at the end of the answer,
    # with the host's question and a reason
    first = by_question.get(Q1)
    assert first, flags
    assert first["answer"] == "dodged"
    assert first["t"] == end(3, A1)
    assert first["reason"] == QUESTIONS[0]["reason"]
    assert first["speaker"] == "Invitado"

    # Case 2 · the guest answers with another figure ("entregadas o en proceso") → still dodged
    second = by_question.get(Q2)
    assert second and second["answer"] == "dodged", flags
    assert second["t"] == end(18, A2)

    # Case 3 · the question sits in the first part, its answer ends in the second → flagged at the end of
    # the answer, with the question from the context
    third = by_question.get(Q3)
    assert third and third["answer"] == "dodged", flags
    assert third["t"] == end(31, A3)

    # Case 4 · an answered question → no flag
    assert Q4 not in by_question
    assert len(questions) == 3, questions

    # Case 5 · no bar for questions → on the player from 0.8 confidence
    assert first["on_player"] is True
    assert second["on_player"] is False

    # Case 6 · the questions come from the part tool calls → one Claude tool call per part, no extra one
    assert claude.calls == 2
    print("PASS S7 A1 · A dodged question is flagged at the end of its answer")


# S7 A3 · "Evasion" is no longer a fallacy
#
# Story: In an invented interview, the model still names a passage "evasion" as a fallacy. The flag file has
# no fallacy flag for it; the passage only goes to the log of candidate names.
#
# Setup: invented word-by-word captions of a host question and a guest answer; a fake Claude that returns
# one flag labelled "evasion" on the guest's words, no claim and no question; a temporary helper home.

HOST_s7a3 = "¿Cuántas viviendas se han entregado?"
GUEST_s7a3 = "Mire lo importante es que hemos aprobado la primera ley de vivienda"
PASSAGE = "lo importante es que hemos aprobado la primera ley de vivienda"


class FakeTranscript_s7a3:
    def fetch(self, video_id):
        return Transcript(segments=words(0, HOST_s7a3) + words(3, GUEST_s7a3), published_at="2026-11-10")


class FakeClaude_s7a3:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [{"quote": PASSAGE, "label": "evasion", "speaker": "Invitado",
                           "reason": "No responde a la pregunta.", "confidence": 0.9}], "claims": []}


def test_evasion_not_fallacy(tmp_path):
    run_analysis("evasion", 0, transcript=FakeTranscript_s7a3(), llm=FakeClaude_s7a3(), home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "evasion.json").read_text())["flags"]

    # Case 1 · the model names the passage "evasion" → no fallacy flag in the flag file
    assert not [f for f in flags if f["type"] == "fallacy" or f["label"] == "evasion"], flags

    # Case 2 · the same passage → one line in the log of candidate names
    log = [json.loads(line) for line in (tmp_path / "candidates.log").read_text().splitlines()]
    assert [(c["label"], c["quote"]) for c in log] == [("evasion", PASSAGE)], log
    print('PASS S7 A3 · "Evasion" is no longer a fallacy')


# S8 A1 · A speaker who contradicts themself gets a flag at the second statement
#
# Story: In an invented interview, the guest says "no vamos a subir el IVA" and, four minutes later,
# "subiremos el IVA de la luz el año que viene". When the helper analyses it, the flag file has a
# contradiction flag at the second of the second statement, quoting it, with the first statement and its
# second as the earlier utterance.
# Edge case: when the audio puts the two statements in different voices, no contradiction flag is made.
#
# Setup: invented word-by-word captions (one word every 0.5 s) over four parts (0-30, 30-150, 150-270 and
# 270-390 s), each word in the voice of its line: SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado").
# The guest says the IVA pair at 6 s and 250 s; the host proposes freezing pensions at 40 s and the guest
# rejects it at 280 s. A fake Claude that, in each part call, lists the contradictions whose second
# statement is in that PART, both pinned on "Invitado" by both names; it lists no fallacy, claim or
# question. A second run uses the same captions without voices. The real bars of thresholds.json; a
# temporary helper home.

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FIRST_s8a1 = "no vamos a subir el IVA"
SECOND = "subiremos el IVA de la luz el año que viene"
PROPOSAL = "congelar las pensiones el año que viene"
REJECTION = "no vamos a congelar las pensiones"
LINES_s8a1 = [
    (0, HOST, "Buenas noches hoy hablamos de impuestos con nuestro invitado"),
    (6, GUEST, f"Gracias por invitarme lo digo claro {FIRST_s8a1} en esta legislatura"),
    (40, HOST, f"Hay quien propone {PROPOSAL} para cuadrar las cuentas"),
    (250, GUEST, f"Y le adelanto una cosa {SECOND} para pagar la transición"),
    (280, GUEST, f"Mire nosotros {REJECTION} pase lo que pase"),
]
FIRST_T = 6 + 6 * 0.5
SECOND_T = 250 + 5 * 0.5


class FakeTranscript_s8a1:
    def __init__(self, with_voices):
        self.with_voices = with_voices

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice if self.with_voices else None)
                    for start, voice, text in LINES_s8a1 for i, w in enumerate(text.split())]
        names = {HOST: "Presentadora", GUEST: "Invitado"} if self.with_voices else {}
        return Transcript(segments=segments, published_at="2026-11-10", speakers=names)


def contradiction(quote, earlier):
    return {"quote": quote, "earlier": earlier, "speaker": "Invitado", "earlier_speaker": "Invitado",
            "reason": f"Antes dijo «{earlier}» y ahora «{quote}».", "confidence": 0.9}


CONTRADICTIONS = [contradiction(SECOND, FIRST_s8a1), contradiction(REJECTION, PROPOSAL)]


class FakeClaude_s8a1:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, schema, tools=()):
        self.calls += 1
        part = prompt.split("PART:")[-1]
        return {"flags": [], "claims": [], "questions": [],
                "contradictions": [c for c in CONTRADICTIONS if c["quote"] in part]}


def analyse(tmp_path, with_voices):
    claude = FakeClaude_s8a1()
    run_analysis("taxes", 0, transcript=FakeTranscript_s8a1(with_voices), llm=claude, home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "taxes.json").read_text())["flags"]
    return [f for f in flags if f["type"] == "contradiction"], claude.calls


def test_self_contradiction(tmp_path):
    found, calls = analyse(tmp_path / "voices", with_voices=True)
    by_quote = {f["quote"]: f for f in found}

    # Case 1 · the guest says the opposite four minutes later, in the same voice → a contradiction flag at
    # the second of the second statement, with the first statement as the earlier utterance
    flag = by_quote.get(SECOND)
    assert flag, found
    assert flag["label"] == "self"
    assert flag["t"] == SECOND_T
    assert flag["speaker"] == "Invitado"
    assert flag["related"] == {"t": FIRST_T, "quote": FIRST_s8a1}
    assert flag["reason"] == CONTRADICTIONS[0]["reason"]

    # Case 2 · the model pins the host's proposal on the guest, but the audio puts it in the host's voice
    # → no contradiction flag
    assert REJECTION not in by_quote
    assert len(found) == 1, found

    # Case 3 · the contradictions come from the part tool calls → one Claude tool call per part, no extra one
    assert calls == 4

    # Case 4 · a video without voices, and the model names the same speaker for both statements → both
    # pairs flagged, since only the model's names tell the speakers apart
    found, _ = analyse(tmp_path / "no-voices", with_voices=False)
    by_quote = {f["quote"]: f for f in found}
    assert by_quote.get(SECOND, {}).get("related") == {"t": FIRST_T, "quote": FIRST_s8a1}, found
    assert by_quote.get(REJECTION, {}).get("related", {}).get("quote") == PROPOSAL, found
    print("PASS S8 A1 · A speaker who contradicts themself gets a flag at the second statement")


# S10 A1 · A named person gets one context card, at the first mention
#
# Story: In an invented interview, the guest names "Marta Gil" at minute 3 and again at minute 9, in
# another part. When the helper analyses it, the flag file has one context flag for Marta Gil, at the
# second of the first mention, with one sentence saying who he is.
# Edge case: when the later part is analysed before the earlier one, the file still keeps one context flag,
# at the first mention.
#
# Setup: invented word-by-word captions (one word every 0.5 s) over four parts (0-30, 150-270, 270-390 and
# 510-630 s), each word in the voice of its line: SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado").
# The guest names Marta Gil at 180 s and at 540 s. A fake Claude that, in each part call, lists the
# context of each name in that PART, with the same sentence each time; it lists no fallacy, claim, question
# or contradiction. A second run starts at second 500, so the part of minute 9 is planned first, and the fake
# answers the part of minute 3 late. The real bars of thresholds.json; a temporary helper home.

NAME = "Marta Gil"
SENTENCE = "Ministro de Transportes del Gobierno de España desde noviembre de 2023."
FIRST_LINE = f"Como dijo el ministro {NAME} los trenes van a llegar a su hora"
LINES_s10a1 = [
    (0, HOST, "Buenas noches hoy hablamos de trenes con nuestro invitado"),
    (180, GUEST, FIRST_LINE),
    (300, HOST, "Pero los retrasos siguen en todas las líneas del país"),
    (540, GUEST, f"Ya se lo expliqué a {NAME} la semana pasada en el ministerio"),
]
FIRST_T_s10a1 = 180 + 4 * 0.5


class FakeTranscript_s10a1:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES_s10a1 for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10",
                          speakers={HOST: "Presentadora", GUEST: "Invitado"})


class FakeClaude_s10a1:
    def __init__(self, slow_first=False):
        self.calls = 0
        self.slow_first = slow_first

    def complete(self, prompt, schema, tools=()):
        self.calls += 1
        part = prompt.split("PART:")[-1]
        if self.slow_first and FIRST_LINE in part:
            time.sleep(0.5)
        context = [{"name": NAME, "kind": "person", "speaker": "Invitado", "sentence": SENTENCE,
                    "confidence": 0.95}] if NAME in part else []
        return {"flags": [], "claims": [], "questions": [], "contradictions": [], "context": context}


def analyse_s10a1(home, from_t=0, slow_first=False):
    claude = FakeClaude_s10a1(slow_first)
    run_analysis("trains", from_t, transcript=FakeTranscript_s10a1(), llm=claude, home=home)
    flags = json.loads((home / "videos" / "trains.json").read_text())["flags"]
    return [f for f in flags if f["type"] == "context"], claude.calls


def test_first_mention(tmp_path):
    found, calls = analyse_s10a1(tmp_path / "in-order")

    # Case 1 · the guest names Marta Gil at minute 3 → a context flag at the second of the first
    # mention, with the name as said and one sentence on who he is
    assert found, "no context flag"
    flag = found[0]
    assert flag["label"] == "person"
    assert flag["quote"] == NAME
    assert flag["t"] == FIRST_T_s10a1
    assert flag["reason"] == SENTENCE

    # Case 2 · the guest names him again at minute 9, in another part → no second context flag
    assert len(found) == 1, found

    # Case 3 · the context comes from the part tool calls → one Claude tool call per part, no extra one
    assert calls == 4

    # Case 4 · the part of minute 9 is analysed before the part of minute 3 → still one context flag, at
    # the first mention
    found, _ = analyse_s10a1(tmp_path / "out-of-order", from_t=500, slow_first=True)
    assert [f["t"] for f in found] == [FIRST_T_s10a1], found
    print("PASS S10 A1 · A named person gets one context card, at the first mention")


# S16 A1 · The live analysis flags four new kinds of fallacy
#
# Story: The helper analyses an invented interview. The guest asks "¿es verdad que su campaña se pagó con dinero de
# la prostitución? ¿Sí o no?" with no evidence; demands the rival resign for a case in his circle but excuses his own
# leader for the same; picks the one measure that suits him; and calls immigrants an invasion. The player shows
# "Insinuación", "Doble rasero", "Datos a conveniencia" and "Apelación al miedo", each with the colour of a fallacy.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 6-minute interview, each line in the voice of
# SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado"); the guest's four lines sit in four different parts. A fake
# Claude that, in each part tool call, lists the fallacy whose words are in that PART, with the new label; it lists
# no claim, question or contradiction. A temporary helper home. The player part imports the extension's flags.ts with
# Node (type stripping) and asks it for the card title and look of each label.

FLAGS_TS = Path(__file__).parents[2] / "src" / "extension" / "src" / "flags.ts"
INSINUATION = "es verdad que su campaña se pagó con dinero de la prostitución"
DOUBLE = "usted tiene que dimitir por su asesor pero nuestro presidente no tiene por qué dimitir por el suyo"
CHERRY = "el único dato que cuenta es el paro registrado de agosto"
FEAR = "esto es una invasión y si no la paramos perderemos nuestro país"
LINES_s16a1 = [
    (0, HOST, "Buenas noches hoy entrevistamos al portavoz de la oposición"),
    (6, GUEST, f"Yo solo pregunto ¿{INSINUATION}? ¿Sí o no?"),
    (60, GUEST, f"Mire {DOUBLE} porque aquello fue otra cosa"),
    (160, GUEST, f"Los datos son claros {CHERRY} y bajó"),
    (280, GUEST, f"Con la inmigración lo digo claro {FEAR} para siempre"),
    (350, HOST, "Muchas gracias por venir y buenas noches"),
]
NAMES = {
    "insinuation": "Insinuación",
    "double_standard": "Doble rasero",
    "cherry_picking": "Datos a conveniencia",
    "appeal_to_fear": "Apelación al miedo",
}
QUOTES = {"insinuation": INSINUATION, "double_standard": DOUBLE, "cherry_picking": CHERRY, "appeal_to_fear": FEAR}


def second(quote):
    """The second of the first word of the quote in its line."""
    needle = quote.split()
    for start, _, text in LINES_s16a1:
        words = [w.strip("¿?") for w in text.split()]
        for i in range(len(words)):
            if words[i:i + len(needle)] == needle:
                return start + i * 0.5
    raise ValueError(quote)


class FakeTranscript:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES_s16a1 for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class FakeClaude_s16a1:
    def __init__(self):
        self.prompts = []
        self.schemas = []

    def complete(self, prompt, schema, tools=()):
        self.prompts.append(prompt)
        self.schemas.append(schema)
        part = prompt.split("PART:")[-1]
        return {"flags": [{"quote": q, "label": label, "closest": None, "speaker": "Invitado",
                           "reason": f"Razón inventada de {label}.", "confidence": 0.8}
                          for label, q in QUOTES.items() if q in part],
                "claims": [], "questions": [], "contradictions": [], "context": []}


def player(labels):
    """The card title and the look of a fallacy flag with each label, from the extension's flags.ts."""
    script = (f"import {{ title, look, TYPE_LOOK }} from {json.dumps(str(FLAGS_TS))};"
              f"const labels = {json.dumps(labels)};"
              "console.log(JSON.stringify({fallacy: TYPE_LOOK.fallacy.color, cards: Object.fromEntries(labels.map("
              "l => [l, {title: title({type: 'fallacy', label: l}), color: look({type: 'fallacy', label: l}).color}]))}));")
    run = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
                         capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


def test_new_fallacies(tmp_path):
    claude = FakeClaude_s16a1()
    run_analysis("rasero", 0, transcript=FakeTranscript(), llm=claude, home=tmp_path)
    found = json.loads((tmp_path / "videos" / "rasero.json").read_text())["flags"]
    flags = {f["label"]: f for f in found}

    # Case 1 · the guest's insinuation, double standard, cherry-picked figure and appeal to fear → one fallacy flag
    # each, with the new label, at the second of its words, on the guest
    for label, quote in QUOTES.items():
        flag = flags.get(label)
        assert flag, (label, list(flags))
        assert flag["type"] == "fallacy", flag
        assert flag["quote"].strip("¿?") == quote, flag
        assert flag["t"] == second(quote), (label, flag["t"])
        assert flag["speaker"] == "Invitado", flag
    assert len(found) == 4, [f["label"] for f in found]

    # Case 2 · every part tool call → the prompt defines the four labels and the schema accepts them as `closest`
    for prompt, schema in zip(claude.prompts, claude.schemas):
        for label in NAMES:
            assert f"- {label}:" in prompt, label
            assert label in schema["properties"]["flags"]["items"]["properties"]["closest"]["enum"], label

    # Case 3 · the player → the Spanish name of each label as the card title, in the colour of a fallacy
    shown = player(list(NAMES))
    for label, name in NAMES.items():
        assert shown["cards"][label]["title"] == name, (label, shown["cards"][label])
        assert shown["cards"][label]["color"] == shown["fallacy"], (label, shown["cards"][label])
    print("PASS S16 A1 · The live analysis flags four new kinds of fallacy")


# S16 A2 · A part sees what each speaker stated earlier in the whole video
#
# Story: In an invented 30-minute interview the guest says at 3:00 "no vamos a quitar el Ministerio de Igualdad", and
# at 25:00 "no habrá Ministerio de Igualdad". The part at 25:00 receives a list with "Invitado (3:00): no quitará el
# Ministerio de Igualdad", and the contradiction flag at 25:00 quotes the words at 3:00 with their second.
# Edge case: WHEN the part that holds 3:00 is not done yet (parts run from the playback second) THEN the list holds
# only what finished parts before 25:00 stated.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 30-minute interview, each line in the voice of
# SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado"). The guest states a position at 3:00 and another at 24:10,
# and says the opposite of the 3:00 one at 25:00, far outside the 10 minutes of CONTEXT. A fake Claude that, in each
# part tool call, lists the positions whose words are in that PART (quote, speaker and a one-line summary), and lists
# the 25:00 contradiction with the 3:00 words as `earlier` only when its prompt holds the 3:00 line. The parts run one
# at a time (scheduler.PARALLEL = 1), so which parts are finished before a part starts is fixed. A second run starts
# at 24:00, so the part with 3:00 runs after the part with 25:00. A third run has an invented 140-minute talk where
# every part states one position. A temporary helper home per run.

FIRST_s16a2 = "no vamos a quitar el Ministerio de Igualdad"
OTHER = "vamos a bajar el IVA de la luz"
SECOND_s16a2 = "no habrá Ministerio de Igualdad en mi gobierno"
POSITIONS = {FIRST_s16a2: "no quitará el Ministerio de Igualdad", OTHER: "bajará el IVA de la luz"}
LINE = "Invitado (3:00): no quitará el Ministerio de Igualdad"
OTHER_LINE = "Invitado (24:10): bajará el IVA de la luz"
LINES_s16a2 = [
    (0, HOST, "Buenas noches hoy hablamos de igualdad con nuestro invitado"),
    (180, GUEST, f"{FIRST_s16a2} en ningún caso"),
    (1450, GUEST, f"{OTHER} y le digo más"),
    (1490, HOST, "¿Y qué pasará con ese ministerio si gobiernan?"),
    (1500, GUEST, f"{SECOND_s16a2} se lo aseguro"),
    (1790, HOST, "Muchas gracias por venir y buenas noches"),
]


class FakeTranscript_s16a2:
    def __init__(self, lines):
        self.lines = lines

    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in self.lines for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class FakeClaude_s16a2:
    def __init__(self, positions):
        self.positions = positions
        self.calls = []  # (part text, text before the PART)

    def complete(self, prompt, schema, tools=()):
        head, _, part = prompt.rpartition("PART:")
        self.calls.append((part, head))
        contradictions = []
        if SECOND_s16a2 in part and LINE in head:
            contradictions.append({"quote": SECOND_s16a2, "earlier": FIRST_s16a2, "speaker": "Invitado",
                                   "earlier_speaker": "Invitado", "confidence": 0.9,
                                   "reason": "A las 3:00 dijo que no quitaría el ministerio y ahora que no habrá."})
        return {"flags": [], "claims": [], "questions": [], "context": [], "contradictions": contradictions,
                "positions": [{"quote": q, "speaker": "Invitado", "summary": s}
                              for q, s in self.positions.items() if q in part]}

    def head_of(self, words):
        return next(head for part, head in self.calls if words in part)


def analyse_s16a2(home, from_t, lines=LINES_s16a2, positions=POSITIONS):
    claude = FakeClaude_s16a2(positions)
    run_analysis("igualdad", from_t, transcript=FakeTranscript_s16a2(lines), llm=claude, home=home)
    data = json.loads((home / "videos" / "igualdad.json").read_text())
    return [f for f in data["flags"] if f["type"] == "contradiction"], claude


def test_positions_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    found, claude = analyse_s16a2(tmp_path / "from-start", 0)

    # Case 1 · the part at 25:00, after the part with 3:00 is done → its prompt lists the guest's 3:00 position with
    # its minute, and the 24:10 one
    head = claude.head_of(SECOND_s16a2)
    assert LINE in head, head
    assert OTHER_LINE in head, head

    # Case 2 · the guest says the opposite at 25:00 → a contradiction flag at 25:00 that quotes the 3:00 words with
    # their second, though they are far outside the 10 minutes of CONTEXT
    assert len(found) == 1, found
    assert found[0]["t"] == 1500.0
    assert found[0]["speaker"] == "Invitado"
    assert found[0]["related"] == {"t": 180.0, "quote": FIRST_s16a2}

    # Case 3 · the positions come out of the part tool calls → one Claude tool call per part, no extra one
    assert len(claude.calls) == len(scheduler.plan(FakeTranscript_s16a2(LINES_s16a2).fetch("igualdad"), 0))

    # Case 4 · the playback starts at 24:00, so the part with 3:00 is not done when the part at 25:00 starts → its
    # list holds the 24:10 position of a finished part, not the 3:00 one, and no contradiction is flagged
    found, claude = analyse_s16a2(tmp_path / "from-24", 1440)
    head = claude.head_of(SECOND_s16a2)
    assert OTHER_LINE in head, head
    assert LINE not in head, head
    assert found == [], found

    # Case 5 · the part with 3:00 runs last → it never lists a position stated later in the video
    assert OTHER_LINE not in claude.head_of(FIRST_s16a2)

    # Case 6 · a 140-minute talk with one position per part → the last part gets at most 60 lines, the newest
    # position on a line of its own and the oldest one merged, not lost
    talk = [(60 + 120 * k, GUEST, f"posición número {k} del invitado") for k in range(70)]
    summaries = {text: f"defiende la posición {k}" for k, (_, _, text) in enumerate(talk)}
    _, claude = analyse_s16a2(tmp_path / "long", 0, lines=talk, positions=summaries)
    head = claude.head_of(talk[-1][2])
    listed = [line for line in head.splitlines() if re.match(r"Invitado \(\d+:\d\d", line)]
    assert 1 <= len(listed) <= 60, len(listed)
    assert listed[-1].startswith("Invitado (2:17:00): defiende la posición 68"), listed[-1]
    assert re.search(r"defiende la posición 0\b", listed[0]), listed[0]
    for k in range(69):
        assert re.search(rf"defiende la posición {k}\b", head), k
    print("PASS S16 A2 · A part sees what each speaker stated earlier in the whole video")


# S18 A2 · A part gets its context as a short window or as one long conversation
#
# Story: The helper analyses an invented 20-minute interview twice. With the short window, each part reading holds the 3
# minutes before it and the list of earlier positions. With the long conversation, the parts are read in order in one
# Claude Code session that each reading resumes, and each reading sends only its own 2 minutes; a contradiction between
# minute 1 and minute 18 is flagged in both.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 20-minute interview: one numbered line every 30 s,
# each in the voice of SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado"). The guest states a position at 1:00 and
# says the opposite at 18:00. The helper runs run_analysis from second 0 with the real Claude Code adapter
# (ClaudeCLI(home, model="opus")); the `claude` command is a fake on PATH that keeps sessions as Claude Code does: a
# reading with --session-id starts a session, a reading with --resume continues it and fails for an unknown one. Each
# reading's prompt is logged. In each part reading, the fake lists the 1:00 position when its PART holds it, and lists
# the 18:00 contradiction with the 1:00 words as `earlier` only when it has seen the 1:00 words: earlier in the same
# session, or before the PART of this prompt. The window run reads one part at a time (scheduler.PARALLEL = 1); the
# conversation run keeps the helper's parallel setting. A temporary helper home per run.

FIRST = "no vamos a subir el IVA de la luz"
SECOND_s18a2 = "vamos a subir el IVA de la luz este mismo año"
STATEMENTS = {60: FIRST, 1080: SECOND_s18a2}


def line(t):
    return STATEMENTS.get(t, f"frase número {t} del programa")


LINES_s18a2 = [(t, GUEST if t in STATEMENTS or t % 60 else HOST, line(t)) for t in range(0, 1200, 30)]
NUMBERED = {t: text for t, _, text in LINES_s18a2 if t not in STATEMENTS}

FAKE_CLAUDE = """\
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
prompt = opt("-p")
sessions = os.environ["FAKE_CLAUDE_SESSIONS"]
seen = ""
if opt("--resume"):
    path = os.path.join(sessions, opt("--resume"))
    if not os.path.exists(path):
        print(json.dumps({"type": "result", "is_error": True, "api_error_status": None, "result": "No conversation found"}))
        sys.exit(1)
    seen = open(path).read()
    open(path, "a").write(prompt)
elif opt("--session-id"):
    path = os.path.join(sessions, opt("--session-id"))
    if os.path.exists(path):
        print(json.dumps({"type": "result", "is_error": True, "api_error_status": None, "result": "Session ID in use"}))
        sys.exit(1)
    open(path, "w").write(prompt)
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:
    f.write(json.dumps({"prompt": prompt, "session_id": opt("--session-id"), "resume": opt("--resume")}) + "\\n")
head, _, part = prompt.rpartition("PART:")
first, second = os.environ["FIRST"], os.environ["SECOND"]
answer = {"flags": [], "claims": [], "questions": [], "context": [], "contradictions": [], "positions": []}
if first in part:
    answer["positions"].append({"quote": first, "speaker": "Invitado", "summary": "no subirá el IVA de la luz"})
if second in part and first in seen + head:
    answer["contradictions"].append({"quote": second, "earlier": first, "speaker": "Invitado",
                                     "earlier_speaker": "Invitado", "confidence": 0.9,
                                     "reason": "Al minuto 1 dijo que no subiría el IVA y ahora que sí."})
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "num_turns": 1, "duration_ms": 1000, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 3, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0,
                            "output_tokens": 10}, "result": json.dumps(answer), "structured_output": answer}))
"""


class FakeTranscript_s18a2:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES_s18a2 for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


def analyse_s18a2(tmp_path, monkeypatch, mode):
    run_dir = tmp_path / mode
    (run_dir / "sessions").mkdir(parents=True)
    bin_dir = run_dir / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    log = run_dir / "readings.jsonl"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_SESSIONS", str(run_dir / "sessions"))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FIRST", FIRST)
    monkeypatch.setenv("SECOND", SECOND_s18a2)
    home = run_dir / "home"
    home.mkdir()
    run_analysis("iva", 0, transcript=FakeTranscript_s18a2(), llm=ClaudeCLI(home, model="opus"), home=home,
                 context_mode=mode)
    data = json.loads((home / "videos" / "iva.json").read_text())
    assert data["status"] == "done", data
    readings = [json.loads(x) for x in log.read_text().splitlines()]
    return data, readings


def part_start(reading):
    """The second of the first line in the PART of a reading."""
    part = reading["prompt"].rpartition("PART:")[2]
    return min(t for t, text in [*NUMBERED.items(), *STATEMENTS.items()] if text in part)


def contradiction_s18a2(data):
    return [(f["t"], f["related"]["t"]) for f in data["flags"] if f["type"] == "contradiction"]


def test_short_window(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "PARALLEL", 1)
    data, readings = analyse_s18a2(tmp_path, monkeypatch, "window")

    # Case 1 · every part reading → holds the numbered lines of the 3 minutes before its part, and none older
    assert len(readings) > 5, len(readings)
    for r in readings:
        start = part_start(r)
        head = r["prompt"].rpartition("PART:")[0]
        for t, text in NUMBERED.items():
            if start - 180 <= t < start:
                assert text in head, (start, t)
            elif t < start - 180:
                assert text not in head, (start, t)

    # Case 2 · a part after 1:00 → its prompt lists the guest's 1:00 position with its minute
    late = [r for r in readings if part_start(r) > 240]
    assert late
    for r in late:
        assert "Invitado (1:00): no subirá el IVA de la luz" in r["prompt"], part_start(r)

    # Case 3 · the guest says the opposite at 18:00 → a contradiction flag at 18:00 that points to 1:00
    assert contradiction_s18a2(data) == [(1080.0, 60.0)], contradiction_s18a2(data)


def test_long_conversation(tmp_path, monkeypatch):
    data, readings = analyse_s18a2(tmp_path, monkeypatch, "conversation")

    # Case 4 · the parts → read in time order, the first one starts a session and every other one resumes it
    starts = [part_start(r) for r in readings]
    assert len(starts) > 5 and starts == sorted(starts), starts
    session = readings[0]["session_id"]
    assert session and not readings[0]["resume"], readings[0]
    assert all(r["resume"] == session and not r["session_id"] for r in readings[1:]), readings[1:]

    # Case 5 · each reading → sends only its own part: no line said before its part, and no list of positions
    for r, start in zip(readings, starts):
        for t, text in [*NUMBERED.items(), *STATEMENTS.items()]:
            if t < start:
                assert text not in r["prompt"], (start, t)
        assert "(1:00)" not in r["prompt"], start

    # Case 6 · the guest says the opposite at 18:00 → a contradiction flag at 18:00 that points to 1:00
    assert contradiction_s18a2(data) == [(1080.0, 60.0)], contradiction_s18a2(data)
    print("PASS S18 A2 · A part gets its context as a short window or as one long conversation")


# S19 A1 · A new analysis reads the parts as one conversation
#
# Story: The person opens an invented video and the helper starts its analysis as it does for the extension. Every part
# reading continues the same Claude Code conversation, not a fresh reading with a short window.
#
# Setup: an invented 6-minute transcript with one numbered line every 10 seconds, served by a fake YouTube. A fake
# Claude records the conversation (session) that each part reading names, and finds nothing. No Fact Check Tools key and
# no voices. The helper starts the analysis from second 0 as the extension's first request does (Helper.start), and the
# test waits until the flag file says done. A temporary helper home.

VIDEO = "conversa1"
LINES_s19a1 = [Segment(t=float(t), text=f"frase número {t} del programa") for t in range(0, 360, 10)]


class FakeYouTube:
    def __init__(self, *args):
        pass

    def fetch(self, video_id):
        return Transcript(segments=LINES_s19a1, published_at="2026-11-10")


class FakeClaude_s19a1:
    sessions = []

    def __init__(self, *args, **kwargs):
        pass

    def complete(self, prompt, schema, tools=()):
        if "flags" in schema["properties"]:
            session = getattr(prompt, "session", None)
            FakeClaude_s19a1.sessions.append(session and session.id)
            if session:
                session.turns += 1
            return {"flags": [], "claims": [], "questions": [], "contradictions": [], "positions": [], "context": []}
        return {"rulings": []}


def test_parts_continue_one_conversation(tmp_path, monkeypatch):
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(server, "YouTube", FakeYouTube)
    monkeypatch.setattr(server, "ClaudeCLI", FakeClaude_s19a1)
    FakeClaude_s19a1.sessions = []
    helper = server.Helper(tmp_path)

    # Case 1 · the extension's first request → the analysis of the whole short video ends done
    helper.start(VIDEO, 0)
    path = tmp_path / "videos" / f"{VIDEO}.json"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not (path.exists() and json.loads(path.read_text())["status"] != "running"):
        time.sleep(0.1)
    data = json.loads(path.read_text())
    assert data["status"] == "done", data

    # Case 2 · every part reading → names a conversation, and all name the same one
    assert len(FakeClaude_s19a1.sessions) >= 3, FakeClaude_s19a1.sessions
    assert None not in FakeClaude_s19a1.sessions, FakeClaude_s19a1.sessions
    assert len(set(FakeClaude_s19a1.sessions)) == 1, FakeClaude_s19a1.sessions


# S26 A2 · An English video is read as English
#
# Story: The helper analyses an invented English interview whose captions are English, with a machine-translated Spanish
# track beside them. It reads the English track; every reading is told the conversation is English, the claims get
# English search queries, the published fact-check search asks for English, and the figure search looks at the sources
# of the country the conversation is about instead of Spain's (no INE). The flag quotes the English words, such as
# "unemployment fell by half in one year".
#
# Setup: language_fakes. The helper runs as it does for the person (Helper._run), with no language from the extension, in a
# temporary helper home. PATH holds only fake commands: `yt-dlp` writes the English original track and the Spanish
# translation of the invented interview, `claude` logs each reading and answers by its schema (an ad hominem and a false
# figure, each quoting the English words), `codex` fails. The Fact Check Tools API is a fake that finds nothing and
# records the language of each search. No voices.

def test_english_video(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    server.Helper(home)._run("enview", 0)
    data = json.loads((home / "videos" / "enview.json").read_text())
    done = readings(log)

    # Case 1 · English original and Spanish translation → the English track is read; the file says spoken "en"
    assert data["status"] == "done", f"FAIL S26 A2 · {data['status']} ({data['stop_reason']})"
    assert data.get("spoken") == "en", f"FAIL S26 A2 · spoken {data.get('spoken')!r}"
    attacks = [f["quote"] for f in data["flags"] if f["label"] == "ad_hominem"]
    assert attacks == [ATTACK["en"]], f"FAIL S26 A2 · the English words are not found: {data['flags']}"

    # Case 2 · every reading → told the conversation is English, never Spanish; the claims get English queries
    assert done, "FAIL S26 A2 · no reading ran"
    for r in done:
        assert r["system"].startswith("You analyse English conversations."), \
            f"FAIL S26 A2 · {r['answer']} reading: {r['system'][:80]!r}"
        assert not re.search(r"Spanish (conversation|video)", text(r)), \
            f"FAIL S26 A2 · the {r['answer']} reading names a Spanish conversation"
    part = next(r for r in done if r["answer"] == "flags")
    assert "English conversation" in text(part) and "English search queries" in text(part), \
        "FAIL S26 A2 · the part reading does not ask for an English conversation and English queries"

    # Case 3 · the published fact-check search → in English; the figure search → the country's sources, not Spain's
    assert FactCheck.searches and {lang for _, lang in FactCheck.searches} == {"en"}, \
        f"FAIL S26 A2 · fact-check searches {FactCheck.searches}"
    search = next(r for r in done if r["answer"] == "evidence")
    assert "WebSearch" in search["tools"], "FAIL S26 A2 · the search reading has no web search"
    assert "Search in English" in text(search) and "country" in text(search), \
        "FAIL S26 A2 · the search reading does not search in English with the country of the conversation"
    assert not re.search(r"\bINE\b|Banco de España|La Moncloa", text(search)), \
        "FAIL S26 A2 · the search reading lists Spain's sources"
    verdict = next(r for r in done if r["answer"] == "verdicts")
    assert not re.search(r"\bINE\b|Banco de España|La Moncloa|\bSEPE\b", text(verdict)), \
        "FAIL S26 A2 · the verdict reading ranks Spain's producers"

    # Case 4 · the false figure → a flag that quotes the English words
    false = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["label"], f["quote"]) for f in false] == [("false", FALSE["en"])], f"FAIL S26 A2 · {false}"
    print("PASS S26 A2 · An English video is read as English")


# S26 A3 · Reasons come in the viewer's language, quotes stay as said
#
# Story: A person with a Spanish browser clicks "Analizar este vídeo" on that English interview: the extension sends its
# language, and the part, fact-check and judge readings ask for reasons in Spanish about an English conversation; the
# flag file says `lang` "es" and the quote stays English. An English viewer of a Spanish video gets readings that ask
# for English reasons. With no language sent, the reasons follow the video's language.
#
# Setup: language_fakes, the same fake commands as A2, and the helper's own HTTP server on a free local port in a temporary
# helper home. Each case posts `/videos/<id>?from=0` with or without `lang`, as the extension does, then reads the flag
# file with GET until it is no longer running. What the extension sends is checked in
# tests/extension/start.test.ts (S26 A3).

def analyse_s26a3(home, video: str, query: str) -> dict:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}/videos/{video}"
    try:
        urllib.request.urlopen(urllib.request.Request(f"{url}?from=0{query}", method="POST"), timeout=10)
        for _ in range(300):
            try:
                data = json.loads(urllib.request.urlopen(url, timeout=10).read())
                if data["status"] != "running":
                    return data
            except urllib.error.HTTPError:
                pass
            time.sleep(0.1)
        raise AssertionError("FAIL S26 A3 · the analysis did not finish in 30 s")
    finally:
        httpd.shutdown()


def by_kind(log) -> dict:
    return {r["answer"]: text(r) for r in readings(log)}


def test_spanish_viewer_of_an_english_video(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    data = analyse_s26a3(home, "enview", "&lang=es")
    seen = by_kind(log)

    # Case 1 · a Spanish viewer, an English video → reasons asked in Spanish about an English conversation
    assert data["status"] == "done", f"FAIL S26 A3 · {data['status']} ({data['stop_reason']})"
    assert (data.get("lang"), data.get("spoken")) == ("es", "en"), \
        f"FAIL S26 A3 · lang {data.get('lang')!r}, spoken {data.get('spoken')!r}"
    assert "English conversation" in seen["flags"] and "reason: one short sentence in Spanish" in seen["flags"], \
        "FAIL S26 A3 · the part reading does not ask for Spanish reasons about an English conversation"
    assert "reason: one short sentence in Spanish" in seen["verdicts"], \
        "FAIL S26 A3 · the verdict reading does not ask for a Spanish reason"
    assert "one short reason in Spanish" in seen["rulings"], "FAIL S26 A3 · the judge does not rule in Spanish"
    for kind in ("flags", "verdicts", "rulings"):
        assert "sentence in English" not in seen[kind] and "reason in English" not in seen[kind], \
            f"FAIL S26 A3 · the {kind} reading asks for English reasons"

    # Case 2 · the quote → the English words, as said
    attacks = [f["quote"] for f in data["flags"] if f["label"] == "ad_hominem"]
    assert attacks == [ATTACK["en"]], f"FAIL S26 A3 · quotes {attacks}"


def test_english_viewer_of_a_spanish_video(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    data = analyse_s26a3(home, "esview", "&lang=en")
    seen = by_kind(log)

    # Case 3 · an English viewer, a Spanish video → reasons asked in English about a Spanish conversation
    assert (data.get("lang"), data.get("spoken")) == ("en", "es"), \
        f"FAIL S26 A3 · lang {data.get('lang')!r}, spoken {data.get('spoken')!r}"
    assert seen["flags"].startswith("You analyse Spanish conversations."), "FAIL S26 A3 · not a Spanish conversation"
    assert "reason: one short sentence in English" in seen["flags"], "FAIL S26 A3 · the part reading asks no English"
    assert "reason: one short sentence in English" in seen["verdicts"], "FAIL S26 A3 · the verdict asks no English"
    assert "one short reason in English" in seen["rulings"], "FAIL S26 A3 · the judge does not rule in English"
    attacks = [f["quote"] for f in data["flags"] if f["label"] == "ad_hominem"]
    assert attacks == [ATTACK["es"]], f"FAIL S26 A3 · quotes {attacks}"


def test_no_language_sent(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    data = analyse_s26a3(home, "enview", "")

    # Case 4 · no language sent → the reasons follow the video's language
    assert (data.get("lang"), data.get("spoken")) == ("en", "en"), \
        f"FAIL S26 A3 · lang {data.get('lang')!r}, spoken {data.get('spoken')!r}"
    assert "reason: one short sentence in English" in by_kind(log)["flags"], "FAIL S26 A3 · not English reasons"
    print("PASS S26 A3 · Reasons come in the viewer's language, quotes stay as said")


# S29 A1 · A cheap screen skips the parts with nothing to check
#
# Story: The helper analyses an invented interview of three parts: a greeting, a false figure and a stated position. The
# usage log shows one `screen` reading per part, by `haiku`; the greeting is logged as skipped and gets no full reading;
# the two others get it. The part after the greeting still sees the greeting's words before its own.
# Edge case: WHEN the screen reading fails or does not say "no" THEN the part gets the full reading.
#
# Setup: invented word-by-word captions (one word every 0.5 s) of a 2.5-minute interview in three parts: the host's
# greeting (0:00), the guest's false figure (0:30) and the guest's stance on taxes (2:30). The helper runs as it does for
# the person (Helper._run, conversation mode, no settings file), with a fake YouTube, a fake Fact Check Tools API that
# finds nothing and no voices. The `claude` command is a fake on PATH that logs the kind, model, tools and message of
# each reading and answers by the JSON schema it gets; its screen says "no" only to the part that holds the greeting.
# The `codex` command fails. A temporary helper home per run.

def analyse_s29a1(tmp_path, monkeypatch, name: str, config: str | None = None):
    run = tmp_path / name
    home = run / "home"
    home.mkdir(parents=True)
    claude_log, _ = fake_clis(run, monkeypatch)
    if config is not None:
        (home / "config.toml").write_text(config)
    server.Helper(home)._run("screen1", 0)
    data = json.loads((home / "videos" / "screen1.json").read_text())
    return data, jsonl(home / "usage.log"), jsonl(claude_log)


def test_screen_skips_small_talk(tmp_path, monkeypatch):
    fake_video(monkeypatch)

    # Case 1 · no settings → one screen reading per part by haiku, with no tool; the greeting part is logged as
    # skipped (read false, with the screen's reason) and the two others as read
    data, usage, readings = analyse_s29a1(tmp_path, monkeypatch, "default")
    assert data["status"] == "done", data
    screens = sorted((u["chunk_start"], u["model"], u["read"]) for u in usage if u["step"] == "screen")
    assert screens == [(0, "haiku", False), (30, "haiku", True), (150, "haiku", True)], \
        f"FAIL S29 A1 · screen lines {[u for u in usage if u['step'] == 'screen']}"
    assert all(u["reason"] for u in usage if u["step"] == "screen"), usage
    assert [r["tools"] for r in readings if r["kind"] == "screen"] == ["", "", ""], readings

    # Case 2 · the greeting gets no full reading; the figure and the stance do, and the figure still gives its
    # "Dato falso" flag
    parts = sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk")
    assert parts == [30, 150], f"FAIL S29 A1 · full readings of the parts at {parts}"
    assert [(f["label"], f["quote"]) for f in data["flags"] if f["type"] == "inaccuracy"] == [("false", FALSE_screen)], data

    # Case 3 · the full reading of the part after the greeting → the greeting's words come before its own PART
    first = next(r["text"] for r in readings if r["kind"] == "flags" and FALSE_screen in r["text"].split("PART:")[-1])
    before, _, part = first.partition("PART:")
    assert GREETING in before and FALSE_screen in part, f"FAIL S29 A1 · the next part does not see the greeting: {first}"

    # Case 4 · the screen reading fails → every part gets the full reading
    monkeypatch.setenv("FAKE_SCREEN_FAILS", "1")
    data, usage, _ = analyse_s29a1(tmp_path, monkeypatch, "failing")
    monkeypatch.delenv("FAKE_SCREEN_FAILS")
    assert data["status"] == "done", data
    assert sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk") == [0, 30, 150], usage

    # Case 5 · the screen answers with no `read` at all → every part gets the full reading
    monkeypatch.setenv("FAKE_SCREEN_ODD", "1")
    data, usage, _ = analyse_s29a1(tmp_path, monkeypatch, "odd")
    monkeypatch.delenv("FAKE_SCREEN_ODD")
    assert data["status"] == "done", data
    assert sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk") == [0, 30, 150], usage

    # Case 6 · `screen = false` in the settings (for a measurement) → no screen reading, every part read in full
    data, usage, readings = analyse_s29a1(tmp_path, monkeypatch, "off", "screen = false\n")
    assert data["status"] == "done", data
    assert not [r for r in readings if r["kind"] == "screen"], readings
    assert sorted(u["chunk_start"] for u in usage if u["step"] == "analyze_chunk") == [0, 30, 150], usage
    print("PASS S29 A1 · A cheap screen skips the parts with nothing to check")


# A fallacy that the model names outside the list becomes a flag of the listed label it is a form of.

QUOTE = "el partido socialista en la oposición no pidió la dimisión de ana pastor"
OTHER_closest_label = "esto es como lo que hacían en los años treinta"


class FakeTranscript_closest_label:
    def fetch(self, video_id):
        words = f"{QUOTE} {OTHER_closest_label}".split()
        return Transcript(segments=[Segment(t=i * 0.5, text=w) for i, w in enumerate(words)], published_at=None)


class FakeClaude_closest_label:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [
            {"quote": QUOTE, "label": "whataboutism", "closest": "tu_quoque", "speaker": "Invitado",
             "reason": "Responde con lo que hizo el otro partido.", "confidence": 0.8},
            {"quote": OTHER_closest_label, "label": "false_analogy", "closest": None, "speaker": "Invitado",
             "reason": "Compara dos épocas sin base.", "confidence": 0.7},
        ], "claims": []}


def test_closest_listed_label(tmp_path):
    run_analysis("closest", 0, transcript=FakeTranscript_closest_label(), llm=FakeClaude_closest_label(), home=tmp_path, thresholds={})
    flags = json.loads((tmp_path / "videos" / "closest.json").read_text())["flags"]
    assert [(f["label"], f["quote"]) for f in flags] == [("tu_quoque", QUOTE)]
    names = [json.loads(line)["label"] for line in (tmp_path / "candidates.log").read_text().splitlines()]
    assert names == ["whataboutism", "false_analogy"]


# A conversation whose context passes 150k tokens goes on in a new session, which gets the positions list.

LINES_session_rollover = [(0, "Buenas noches y bienvenidos"), (60, FIRST), (200, "frase del programa"), (330, "otra frase más")]


class FakeTranscript_session_rollover:
    def fetch(self, video_id):
        return Transcript(segments=[Segment(t=float(t + i * 0.5), text=w) for t, text in LINES_session_rollover
                                    for i, w in enumerate(text.split())], published_at="2026-11-10")


class FakeClaude_session_rollover:
    """Grows the session as Claude Code does, by 100k tokens a reading."""

    def __init__(self):
        self.readings = []

    def complete(self, prompt, schema):
        session = prompt.session
        self.readings.append((session.id, session.turns, prompt.data))
        session.turns += 1
        session.tokens += 100_000
        part = prompt.data.rpartition("PART:")[2]
        return {"flags": [], "claims": [], "questions": [], "contradictions": [], "context": [],
                "positions": [{"quote": FIRST, "speaker": "Invitado", "summary": "no subirá el IVA"}] if FIRST in part else []}


def test_new_session_carries_positions(tmp_path):
    claude = FakeClaude_session_rollover()
    run_analysis("largo", 0, transcript=FakeTranscript_session_rollover(), llm=claude, home=tmp_path, context_mode="conversation")
    ids = [r[0] for r in claude.readings]
    assert ids[0] == ids[1] != ids[2] == ids[3], ids
    assert claude.readings[2][1] == 0
    assert "no subirá el IVA" in claude.readings[2][2]
    assert "no subirá el IVA" not in claude.readings[3][2]
