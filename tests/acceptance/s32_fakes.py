"""The fakes that the S32 acceptance tests share: an invented 4-minute interview between a host ("Presentadora") and a
guest ("Ana Ruiz"), its four flags as the parts found them, and a judge LLM that answers with the rulings it is given
and records each prompt and schema."""
from fact_checker.core.flags import Segment, Transcript

HOST, GUEST = "SPEAKER_00", "SPEAKER_01"
REPROACH = "usted nunca ha tenido palabra en esta casa"
FALLACY = "mis rivales no saben ni gestionar su propia comunidad de vecinos"
FALSE = "España recibió cuarenta y nueve coma ocho millones de turistas"
DISPUTED = "el paro juvenil es el más alto de toda Europa"
EARLIER = "nunca subiré el impuesto de la gasolina"
LATER = "subimos el impuesto de la gasolina en primavera"
LINES = [(0, HOST, REPROACH), (30, GUEST, FALLACY), (60, GUEST, FALSE), (120, GUEST, DISPUTED),
         (150, GUEST, EARLIER), (210, GUEST, LATER)]


def transcript() -> Transcript:
    segments = [Segment(t=t, text=text, speaker=voice) for t, voice, text in LINES]
    return Transcript(segments=segments, published_at="2026-11-10",
                      speakers={HOST: "Presentadora", GUEST: "Ana Ruiz"})


def flag(t, quote, type, label, speaker="Ana Ruiz", **extra):
    return {"id": f"{label}-{t:.1f}", "t": float(t), "speaker": speaker, "quote": quote, "type": type,
            "label": label, "reason": f"Motivo inventado de {label}.", "confidence": 0.9} | extra


FLAGS = [
    flag(0, REPROACH, "fallacy", "ad_hominem"),  # the host's words, given to the guest
    flag(30, FALLACY, "fallacy", "ad_hominem"),
    flag(60, FALSE, "inaccuracy", "false"),
    flag(120, DISPUTED, "inaccuracy", "disputed"),
    flag(210, LATER, "contradiction", "self", related={"t": 150.0, "quote": EARLIER}),
]
REPROACH_ID, FALLACY_ID, FALSE_ID, DISPUTED_ID, SELF_ID = (f["id"] for f in FLAGS)


class FakeJudge:
    """Answers each judge reading with `rulings`: flag id → (verdict, reason, speaker)."""

    def __init__(self, rulings):
        self.rulings = rulings
        self.calls = []

    def complete(self, prompt, schema, tools=()):
        self.calls.append({"prompt": str(prompt), "schema": schema})
        return {"rulings": [{"id": i, "verdict": v, "reason": r, "speaker": s}
                            for i, (v, r, s) in self.rulings.items()]}
