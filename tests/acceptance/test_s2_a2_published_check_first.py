"""S2 A2 · A published fact-check is used first, with its own date

Story: In an invented dialogue a guest says youth unemployment doubled last year. A published fact-check
by Newtral, rated "Falso" on 12 May 2025, matches it. The check step receives that fact-check, and the
flag cites Newtral with the date 2025-05-12, even if the web search gives no date.

Setup: the invented captions in tests/fakes/youtube/invented-claims.json3; a fake Fact Check Tools API
that returns the Newtral check for any query about "paro juvenil"; a fake Claude that lists the four
claims of the dialogue in the chunk call, and in the check call says the youth claim is false, citing
the Newtral link with no date; a temporary helper home.
"""
import json
from pathlib import Path

from fact_checker.adapters.youtube import parse_json3
from fact_checker.core.flags import PublishedCheck
from fact_checker.server import run_analysis

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
