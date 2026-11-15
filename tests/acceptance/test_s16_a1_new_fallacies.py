"""S16 A1 · The live analysis flags four new kinds of fallacy

Story: The helper analyses an invented interview. The guest asks "¿es verdad que su campaña se pagó con dinero de
la prostitución? ¿Sí o no?" with no evidence; demands the rival resign for a case in his circle but excuses his own
leader for the same; picks the one measure that suits him; and calls immigrants an invasion. The player shows
"Insinuación", "Doble rasero", "Datos a conveniencia" and "Apelación al miedo", each with the colour of a fallacy.

Setup: invented word-by-word captions (one word every 0.5 s) of a 6-minute interview, each line in the voice of
SPEAKER_00 ("Presentadora") or SPEAKER_01 ("Invitado"); the guest's four lines sit in four different parts. A fake
Claude that, in each part tool call, lists the fallacy whose words are in that PART, with the new label; it lists
no claim, question or contradiction. A temporary helper home. The player part imports the extension's flags.ts with
Node (type stripping) and asks it for the card title and look of each label.
"""
import json
import subprocess
from pathlib import Path

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
FLAGS_TS = Path(__file__).parents[2] / "src" / "extension" / "src" / "flags.ts"
INSINUATION = "es verdad que su campaña se pagó con dinero de la prostitución"
DOUBLE = "usted tiene que dimitir por su asesor pero nuestro presidente no tiene por qué dimitir por el suyo"
CHERRY = "el único dato que cuenta es el paro registrado de agosto"
FEAR = "esto es una invasión y si no la paramos perderemos nuestro país"
LINES = [
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
    for start, _, text in LINES:
        words = [w.strip("¿?") for w in text.split()]
        for i in range(len(words)):
            if words[i:i + len(needle)] == needle:
                return start + i * 0.5
    raise ValueError(quote)


class FakeTranscript:
    def fetch(self, video_id):
        segments = [Segment(t=start + i * 0.5, text=w, speaker=voice)
                    for start, voice, text in LINES for i, w in enumerate(text.split())]
        return Transcript(segments=segments, published_at="2026-11-10", speakers={HOST: "Presentadora", GUEST: "Invitado"})


class FakeClaude:
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
    claude = FakeClaude()
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
