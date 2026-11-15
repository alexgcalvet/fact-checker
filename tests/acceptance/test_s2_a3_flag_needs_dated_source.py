"""S2 A3 · A claim is flagged only when a dated source contradicts it

Story: In the same dialogue three claims are checked: one the sources confirm, one they contradict but
with no date anywhere, and one the INE contradicts in a release dated 2025-10-28. Only the third becomes
a flag, citing INE and that date.

Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake Fact Check Tools API
that finds nothing; a fake Claude that lists the three claims in the chunk call and, in the check call,
confirms the population, contradicts the inflation with an undated source, and contradicts the
unemployment figure with an INE release dated 2025-10-28; a temporary helper home.
"""
import json
from pathlib import Path

from fact_checker.adapters.youtube import parse_json3
from fact_checker.server import run_analysis

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-claims.json3"
INE_URL = "https://www.ine.es/daco/daco42/daco4211/epa0325.pdf"

CLAIMS = [
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


class FakeTranscript:
    def fetch(self, video_id):
        return parse_json3(json.loads(FAKE.read_text()), published_at="2026-11-10")


class NoPublishedChecks:
    def search(self, query, language):
        return []


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": [dict(v) for v in VERDICTS]}
        return {"flags": [], "claims": [dict(c) for c in CLAIMS]}


def test_flag_needs_dated_source(tmp_path):
    run_analysis("claims", 0, transcript=FakeTranscript(), llm=FakeClaude(), factcheck=NoPublishedChecks(),
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
