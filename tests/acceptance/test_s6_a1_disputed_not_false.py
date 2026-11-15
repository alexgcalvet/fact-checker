"""S6 A1 · A figure that a credible measure supports is disputed, not false

Story: A guest says "tenemos casi tres millones y medio de parados registrados". The check finds three
measures: SEPE registered unemployment (2.4 million, against), registered unemployment plus inactive fijos
discontinuos (about 3.3 million, for) and the EPA (2.6 million, against). The flag file gets a "disputed"
flag with the three measures and a note on the fijos discontinuos controversy, not a "false" flag.
Edge case: when the only measure that contradicts a claim comes from a think tank or a newspaper, no
"false" flag is made.

Setup: invented captions with three claims; a fake Fact Check Tools API that finds nothing; a fake Claude
that lists the three claims and judges all three "false" with a dated source: the unemployment claim with
the three measures of tests/golden/empleo.json (SEPE and SEPE-based measures tier 2, EPA tier 1) and a
controversy line; the rent claim with one newspaper measure (tier 5) against it; the EPA rate claim with
one INE measure (tier 1) against it; a temporary helper home.
"""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

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


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=words(0, PARO) + words(10, ALQUILER) + words(20, EPA), published_at="2025-11-10")


class NoPublishedChecks:
    def search(self, query, language):
        return []


def verdict(quote, publisher, url, measures, controversy=None):
    return {"quote": quote, "verdict": "false", "reason": "Las fuentes dan otra cifra.", "confidence": 0.9,
            "sources": [{"publisher": publisher, "url": url, "date": "2025-11-04"}], "note": None,
            "published": [], "measures": measures, "controversy": controversy}


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                verdict(PARO, "SEPE", "https://www.sepe.es/paro-octubre-2025", PARO_MEASURES, CONTROVERSY),
                verdict(ALQUILER, "El Diario Económico", "https://example.org/alquiler",
                        [{"name": "precio del alquiler", "value": "+11 %", "source": "El Diario Económico",
                          "tier": 5, "supports": False}]),
                verdict(EPA, "INE", "https://www.ine.es/epa",
                        [{"name": "tasa de paro EPA", "value": "10,45 %", "source": "INE, EPA 3T 2025", "tier": 1,
                          "supports": False}]),
            ]}
        return {"flags": [], "claims": [{"quote": q, "speaker": "Invitado", "queries": [q]}
                                        for q in (PARO, ALQUILER, EPA)]}


def test_disputed_not_false(tmp_path):
    run_analysis("disputed", 0, transcript=FakeTranscript(), llm=FakeClaude(), factcheck=NoPublishedChecks(),
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
