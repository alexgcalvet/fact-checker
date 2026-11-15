"""S26 A2 · An English video is read as English

Story: The helper analyses an invented English interview whose captions are English, with a machine-translated Spanish
track beside them. It reads the English track; every reading is told the conversation is English, the claims get
English search queries, the published fact-check search asks for English, and the figure search looks at the sources
of the country the conversation is about instead of Spain's (no INE). The flag quotes the English words, such as
"unemployment fell by half in one year".

Setup: s26_fakes. The helper runs as it does for the person (Helper._run), with no language from the extension, in a
temporary helper home. PATH holds only fake commands: `yt-dlp` writes the English original track and the Spanish
translation of the invented interview, `claude` logs each reading and answers by its schema (an ad hominem and a false
figure, each quoting the English words), `codex` fails. The Fact Check Tools API is a fake that finds nothing and
records the language of each search. No voices.
"""
import json
import re

from fact_checker import server

from s26_fakes import ATTACK, FALSE, FactCheck, readings, setup, text


def test_english_video(tmp_path, monkeypatch):
    home, log = setup(tmp_path, monkeypatch)
    server.Helper(home)._run("enview", 0)
    data = json.loads((home / "videos" / "enview.json").read_text())
    done = readings(log)

    # Case 1 · English original and Spanish translation → the English track is read; the file says spoken "en"
    assert data["status"] == "done", f"FAIL S26 A2 · {data['status']} ({data['stop_reason']})"
    assert data.get("spoken") == "en", f"FAIL S26 A2 · spoken {data.get('spoken')!r}"
    attacks = [f["quote"] for f in data["flags"] if f["label"] == "ad_hominem"]
    assert attacks == [ATTACK["en"]], f"FAIL S26 A2 · the English words are not found: {data['flags']}"

    # Case 2 · every reading → told the conversation is English, never Spanish; the claims get English queries
    assert done, "FAIL S26 A2 · no reading ran"
    for r in done:
        assert r["system"].startswith("You analyse English conversations."), \
            f"FAIL S26 A2 · {r['answer']} reading: {r['system'][:80]!r}"
        assert not re.search(r"Spanish (conversation|video)", text(r)), \
            f"FAIL S26 A2 · the {r['answer']} reading names a Spanish conversation"
    part = next(r for r in done if r["answer"] == "flags")
    assert "English conversation" in text(part) and "English search queries" in text(part), \
        "FAIL S26 A2 · the part reading does not ask for an English conversation and English queries"

    # Case 3 · the published fact-check search → in English; the figure search → the country's sources, not Spain's
    assert FactCheck.searches and {lang for _, lang in FactCheck.searches} == {"en"}, \
        f"FAIL S26 A2 · fact-check searches {FactCheck.searches}"
    search = next(r for r in done if r["answer"] == "evidence")
    assert "WebSearch" in search["tools"], "FAIL S26 A2 · the search reading has no web search"
    assert "Search in English" in text(search) and "country" in text(search), \
        "FAIL S26 A2 · the search reading does not search in English with the country of the conversation"
    assert not re.search(r"\bINE\b|Banco de España|La Moncloa", text(search)), \
        "FAIL S26 A2 · the search reading lists Spain's sources"
    verdict = next(r for r in done if r["answer"] == "verdicts")
    assert not re.search(r"\bINE\b|Banco de España|La Moncloa|\bSEPE\b", text(verdict)), \
        "FAIL S26 A2 · the verdict reading ranks Spain's producers"

    # Case 4 · the false figure → a flag that quotes the English words
    false = [f for f in data["flags"] if f["type"] == "inaccuracy"]
    assert [(f["label"], f["quote"]) for f in false] == [("false", FALSE["en"])], f"FAIL S26 A2 · {false}"
    print("PASS S26 A2 · An English video is read as English")
