"""S9 A1 · A claim about one's own earlier words that the record contradicts is flagged with the earlier statement

Story: In an invented interview, the guest says "yo nunca dije que no pactaría con ese partido". The check
finds a dated interview in a newspaper where the guest said "no pactaré con ese partido". The flag file has
a contradiction flag with the label "record", quoting the guest, with the earlier statement, its date and
its link.
Edge case: when the earlier statement has no date that a source confirms, no flag is made.

Setup: invented word-by-word captions with two claims of the guest about their own earlier words: the pact
(at 0 s) and taxes (at 10 s); a fake Fact Check Tools API that finds nothing; a fake Claude whose part
call lists both claims as "own_words", and whose check call judges both "false" with an earlier
statement: the pact one dated 2023-07-02 in El Diario with its link, the taxes one with no date and an
undated source; a temporary helper home.
"""
import json

from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis

PACT = "yo nunca dije que no pactaría con ese partido"
TAXES = "nunca he dicho que bajaría los impuestos"
EARLIER = "no pactaré con ese partido"
URL = "https://example.org/el-diario/entrevista-2023-07-02"
REASON = "En julio de 2023 dijo en una entrevista que no pactaría con ese partido."


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript:
    def fetch(self, video_id):
        return Transcript(segments=words(0, PACT) + words(10, TAXES), published_at="2026-11-10")


class NoPublishedChecks:
    def search(self, query, language):
        return []


def verdict(quote, earlier, sources):
    return {"quote": quote, "verdict": "false", "reason": REASON, "confidence": 0.9, "sources": sources,
            "note": None, "measures": [], "controversy": None, "published": [], "earlier": earlier,
            "promise": None}


class FakeClaude:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, schema, tools=()):
        self.prompts.append(prompt)
        if "verdicts" in schema["properties"]:
            return {"verdicts": [
                verdict(PACT, {"quote": EARLIER, "date": "2023-07-02", "publisher": "El Diario", "url": URL},
                        [{"publisher": "El Diario", "url": URL, "date": "2023-07-02"}]),
                verdict(TAXES, {"quote": "bajaremos los impuestos", "date": None, "publisher": "Un blog",
                                "url": "https://example.org/blog"},
                        [{"publisher": "Un blog", "url": "https://example.org/blog", "date": None}]),
            ]}
        return {"flags": [], "questions": [], "contradictions": [],
                "claims": [{"quote": q, "speaker": "Invitado", "queries": [q], "question": None, "kind": "own_words"}
                           for q in (PACT, TAXES)]}


def test_record_contradiction(tmp_path):
    claude = FakeClaude()
    run_analysis("record", 0, transcript=FakeTranscript(), llm=claude, factcheck=NoPublishedChecks(), home=tmp_path)
    flags = json.loads((tmp_path / "videos" / "record.json").read_text())["flags"]
    by_quote = {f["quote"]: f for f in flags}

    # Case 1 · a dated newspaper interview contradicts the guest's claim about their own words → a
    # contradiction flag "record" quoting the guest, with the earlier statement, its date and its link
    flag = by_quote.get(PACT)
    assert flag, flags
    assert flag["type"] == "contradiction"
    assert flag["label"] == "record"
    assert flag["t"] == 0
    assert flag["speaker"] == "Invitado"
    assert flag["related"]["quote"] == EARLIER
    assert flag["related"]["date"] == "2023-07-02"
    assert flag["related"]["source"] == {"publisher": "El Diario", "url": URL}
    assert {"publisher": "El Diario", "url": URL, "date": "2023-07-02"} in flag["sources"]
    assert flag["reason"] == REASON

    # Case 2 · the earlier statement has no date that a source confirms → no flag
    assert TAXES not in by_quote, by_quote[TAXES]

    # Case 3 · the record is checked in the check tool call of the part, which knows the claim is about
    # the speaker's own words → two Claude tool calls in all
    assert len(claude.prompts) == 2
    assert "own_words" in next(line for line in claude.prompts[1].splitlines() if PACT in line)
    print("PASS S9 A1 · A claim about one's own earlier words that the record contradicts is flagged with the "
          "earlier statement")
