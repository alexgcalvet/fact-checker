"""The fakes that the S33 tests share: an invented interview where the host opens with "Buenos días, hoy está
con nosotros Ana Ruiz", voice turns that give the host 1260 s of speech, Ana Ruiz 2460 s and a third voice 30 s (under
5 % of the talk), and a fake model that names the voices with the roles it is given and records each speakers reading.
"""
from fact_checker.core.flags import Segment
from video_fakes import FakeTranscript

HOST, GUEST, NOISE = "SPEAKER_00", "SPEAKER_01", "SPEAKER_02"
TITLE = "Entrevista inventada a Ana Ruiz"
LINES = [(0, "Buenos días, hoy está con nosotros Ana Ruiz"), (30, "¿Qué opina de la vivienda?"),
         (1300, "Gracias por invitarme, la vivienda es la prioridad de este curso"),
         (3730, "Perdón, se oye un ruido en la sala")]
TURNS = [{"start": 0.0, "end": 1260.0, "speaker": HOST}, {"start": 1260.0, "end": 3720.0, "speaker": GUEST},
         {"start": 3720.0, "end": 3750.0, "speaker": NOISE}]
# The captions with no voices, as YouTube gives them, with the video title.
TITLED = FakeTranscript([Segment(t=t, text=text) for t, text in LINES], title=TITLE, channel="Canal inventado",
                        duration=3750.0)


class NamingModel:
    """Answers the speakers reading with `named`: voice → (name, role, person); every other reading finds nothing.
    Records the prompt and the schema of each speakers reading."""

    def __init__(self, named):
        self.named, self.readings = named, []

    def complete(self, prompt, schema, tools=()):
        if "speakers" in schema["properties"]:
            self.readings.append({"prompt": str(prompt), "schema": schema})
            return {"speakers": [{"voice": v, "name": n, "role": r, "person": p}
                                 for v, (n, r, p) in self.named.items()]}
        if "flags" not in schema["properties"]:
            return {"verdicts": [], "rulings": []}
        return {"flags": [], "claims": [], "questions": [], "contradictions": [], "positions": [], "context": []}
