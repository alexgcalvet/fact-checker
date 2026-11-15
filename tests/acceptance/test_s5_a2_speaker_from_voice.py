"""S5 A2 · A card names the voice that said its words

Story: In an invented interview the host says "la oposición no tiene autoridad para hablar". The model
calls it an ad hominem by the guest. The card says the host said it, because the audio puts those words
in the host's voice.
Edge case: when the quoted words cross from one voice to the other, no card is made.

Setup: invented word-by-word captions of a host (0-10 s) and a guest (10-20 s); fake voice turns that
put the first ten seconds in voice SPEAKER_00 and the rest in SPEAKER_01; a fake Claude that names the
voices "Presentadora" and "Invitado", and in the part call returns two ad hominem flags, both pinned on
the guest: one on the host's words, one on words that cross from the host to the guest; a temporary
helper home.
"""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST = "Mucha gente dice que la oposición no tiene autoridad para hablar de vivienda"
GUEST = "Nosotros hemos construido más viviendas que ningún otro gobierno"


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=words(0, HOST) + words(10, GUEST), published_at="2026-11-10")


class FakeVoices:
    def turns(self, video_id):
        return [{"start": 0.0, "end": 9.8, "speaker": "SPEAKER_00"},
                {"start": 9.9, "end": 20.0, "speaker": "SPEAKER_01"}]


def flag(quote):
    return {"quote": quote, "label": "ad_hominem", "speaker": "Invitado", "reason": "Ataca a la oposición.",
            "confidence": 0.9}


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "speakers" in schema["properties"]:
            return {"speakers": [{"voice": "SPEAKER_00", "name": "Presentadora"},
                                 {"voice": "SPEAKER_01", "name": "Invitado"}]}
        if "verdicts" in schema["properties"]:
            return {"verdicts": []}
        return {"flags": [flag("la oposición no tiene autoridad para hablar"),
                          flag("hablar de vivienda Nosotros hemos construido")], "claims": []}


def test_speaker_from_voice(tmp_path):
    run_analysis("voices", 0, transcript=FakeTranscript(), llm=FakeClaude(), home=tmp_path, voices=FakeVoices())
    data = json.loads((tmp_path / "videos" / "voices.json").read_text())
    flags = data["flags"]

    # Case 1 · the model pins the host's words on the guest → the card names the host, from the voice
    host = [f for f in flags if f["quote"] == "la oposición no tiene autoridad para hablar"]
    assert len(host) == 1, flags
    assert host[0]["speaker"] == "Presentadora"

    # Case 2 · the quoted words cross from the host's voice to the guest's → no card
    assert not [f for f in flags if "Nosotros" in f["quote"]], flags
    assert len(flags) == 1
    print("PASS S5 A2 · A card names the voice that said its words")
