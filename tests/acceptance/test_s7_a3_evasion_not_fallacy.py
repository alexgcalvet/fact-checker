"""S7 A3 · "Evasion" is no longer a fallacy

Story: In an invented interview, the model still names a passage "evasion" as a fallacy. The flag file has
no fallacy flag for it; the passage only goes to the log of candidate names.

Setup: invented word-by-word captions of a host question and a guest answer; a fake Claude that returns
one flag labelled "evasion" on the guest's words, no claim and no question; a temporary helper home.
"""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

HOST = "¿Cuántas viviendas se han entregado?"
GUEST = "Mire lo importante es que hemos aprobado la primera ley de vivienda"
PASSAGE = "lo importante es que hemos aprobado la primera ley de vivienda"


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=words(0, HOST) + words(3, GUEST), published_at="2026-11-10")


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        return {"flags": [{"quote": PASSAGE, "label": "evasion", "speaker": "Invitado",
                           "reason": "No responde a la pregunta.", "confidence": 0.9}], "claims": []}


def test_evasion_not_fallacy(tmp_path):
    run_analysis("evasion", 0, transcript=FakeTranscript(), llm=FakeClaude(), home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "evasion.json").read_text())["flags"]

    # Case 1 · the model names the passage "evasion" → no fallacy flag in the flag file
    assert not [f for f in flags if f["type"] == "fallacy" or f["label"] == "evasion"], flags

    # Case 2 · the same passage → one line in the log of candidate names
    log = [json.loads(line) for line in (tmp_path / "candidates.log").read_text().splitlines()]
    assert [(c["label"], c["quote"]) for c in log] == [("evasion", PASSAGE)], log
    print('PASS S7 A3 · "Evasion" is no longer a fallacy')
