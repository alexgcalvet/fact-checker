"""The fakes that the S31 tests share: an invented 11-minute interview, captions with no voices, a slow
speaker separation and a fake model whose part readings take 0.2 s.

The host opens with an ad hominem in the first seconds, which the fake model pins on the guest ("Invitado") as a model
that reads only the text may do; the guest answers with an ad hominem that the model pins on the guest; at minute 11
the guest says a third one, which the model pins on "alguien". The voices put the first 10 seconds and 3:20-4:20 in the
host's voice and the rest in the guest's.
"""
import json
import threading
import time
from pathlib import Path

from video_fakes import FakeTranscript, spoken

HOST_LINE = "Buenas noches la oposición no tiene autoridad para hablar de nada"
HOST_QUOTE = "la oposición no tiene autoridad para hablar"
GUEST_LINE = "Gracias pero usted miente siempre como todos los suyos"
GUEST_QUOTE = "usted miente siempre"
LATE_LINE = "Y ustedes son unos corruptos que no saben gobernar"
LATE_QUOTE = "ustedes son unos corruptos"
LINES = [(0, HOST_LINE), (12, GUEST_LINE), (200, "Hablemos ahora de la vivienda y de los alquileres"),
         (660, LATE_LINE)]
GUESS = {HOST_QUOTE: "Invitado", GUEST_QUOTE: "Invitado", LATE_QUOTE: "alguien"}
# The host also asks at 3:20, so the host's voice holds over 5 % of the talk and is not dropped as noise.
TURNS = [{"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00"}, {"start": 11.0, "end": 199.0, "speaker": "SPEAKER_01"},
         {"start": 200.0, "end": 260.0, "speaker": "SPEAKER_00"}, {"start": 261.0, "end": 700.0, "speaker": "SPEAKER_01"}]
NAMES = {"speakers": [{"voice": "SPEAKER_00", "name": "Presentadora"}, {"voice": "SPEAKER_01", "name": "Invitado"}]}
PART_S = 0.2
CAPTIONS = FakeTranscript(spoken(LINES))  # with no voices, as YouTube gives them


class SlowVoices:
    """A speaker separation that takes `seconds`; `done` is set when it returns."""

    def __init__(self, seconds: float):
        self.seconds, self.done = seconds, threading.Event()

    def turns(self, video_id):
        time.sleep(self.seconds)
        self.done.set()
        return TURNS


class GuessingModel:
    """Answers the speakers reading with the two names, and each part reading after 0.2 s with an ad hominem for each
    known line in its PART, pinned on the name that a reading of the text alone gives. Records each PART it reads."""

    def __init__(self):
        self.parts, self.speakers_readings, self.lock = [], 0, threading.Lock()

    def complete(self, prompt, schema, tools=()):
        if "speakers" in schema["properties"]:
            with self.lock:
                self.speakers_readings += 1
            return NAMES
        if "flags" not in schema["properties"]:
            return {"rulings": []}
        part = str(prompt).rpartition("PART:")[2]
        with self.lock:
            self.parts.append(part)
        time.sleep(PART_S)
        return {"flags": [{"quote": q, "label": "ad_hominem", "closest": None, "speaker": who, "reason": "Ataca.",
                           "confidence": 0.9} for q, who in GUESS.items() if q in part],
                "claims": [], "questions": [], "contradictions": [], "positions": [], "context": []}


def flag_file(home: Path, video_id: str) -> dict | None:
    path = home / "videos" / f"{video_id}.json"
    for _ in range(5):  # the helper replaces the file whole; a read may meet the rename
        try:
            return json.loads(path.read_text()) if path.exists() else None
        except (OSError, ValueError):
            time.sleep(0.01)
    return None


def wait_for(cond, timeout: float = 15, step: float = 0.02):
    """The first truthy value of `cond()`, or None after `timeout` seconds."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if value := cond():
            return value
        time.sleep(step)
    return None


def speaker_of(data: dict | None, quote: str) -> str | None:
    return next((f["speaker"] for f in (data or {}).get("flags", []) if f["quote"] == quote), None)
