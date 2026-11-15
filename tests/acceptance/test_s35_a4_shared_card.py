"""S35 A4 · A shared analysis gives the same card

Story: The person analyses the invented interview with sharing on. A second person opens the same video, gets the
shared analysis and exports it. Their card reads the same "4 de 26" and "2 de 11" as the first person's.

Setup: the S28 fake collector on a free local port, empty. The first person's helper home holds the S35 invented
interview (s35_fakes.INTERVIEW) with its marks, and uploads it the way the helper does after a whole analysis with
sharing on (analyses.upload). The author's approval is out of this test: the fake collector serves what it holds. The
second person's helper home points `feedback_url` to the collector and has no flag file. Each helper runs its HTTP
server on a free port with the screenshot faked to return the card's HTML. Marks never travel, so the second person
reviews the flags too: they mark the same flags through POST /videos/<id>/marks with sharing off.
"""
import json
import urllib.request
from urllib.parse import quote

from s28_fakes import FakeCollector
from s35_fakes import GUEST, INTERVIEW, MARKS, VIDEO, get, save_with_marks, start, visible

from fact_checker import analyses


def post(url: str, body: dict) -> int:
    req = urllib.request.Request(url, method="POST", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return res.status


def test_shared_card(tmp_path, monkeypatch):
    collector = FakeCollector()
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (second / "config.toml").write_text(f'feedback_url = "{collector.url}"\nshare_marks = false\n')
    save_with_marks(first)
    try:
        analyses.upload(first, collector.url, json.loads((first / "videos" / f"{VIDEO}.json").read_text()))
        base, stop = start(first, monkeypatch)
        try:
            mine = visible(get(f"{base}/videos/{VIDEO}/summary.png?person={quote(GUEST)}"))
        finally:
            stop()

        base, stop = start(second, monkeypatch)
        try:
            assert get(f"{base}/videos/{VIDEO}?at=0&lang=es"), "FAIL S35 A4 · the second person got no analysis"
            for flag_id, verdict in MARKS.items():
                assert post(f"{base}/videos/{VIDEO}/marks", {"flag_id": flag_id, "verdict": verdict}) == 200
            theirs = visible(get(f"{base}/videos/{VIDEO}/summary.png?person={quote(GUEST)}"))
            alt = get(f"{base}/videos/{VIDEO}/summary.txt?person={quote(GUEST)}")
        finally:
            stop()
    finally:
        collector.stop()

    # Case 1 · the upload → the claims and questions per speaker travel, as numbers only
    sent = next(r["body"]["analysis"] for r in collector.requests if r["method"] == "PUT")
    assert sent.get("claims") == INTERVIEW["claims"] and sent.get("questions") == INTERVIEW["questions"], \
        f"FAIL S35 A4 · uploaded claims {sent.get('claims')!r}, questions {sent.get('questions')!r}"

    # Case 2 · the first person's card → "4 de 26" and "2 de 11"
    assert "4 de 26" in mine and "2 de 11" in mine, f"FAIL S35 A4 · the first card: {mine!r}"

    # Case 3 · the second person's card and alt text → the same "4 de 26" and "2 de 11"
    assert "4 de 26" in theirs and "2 de 11" in theirs, f"FAIL S35 A4 · the shared card: {theirs!r}"
    assert "4 de 26" in alt and "2 de 11" in alt, f"FAIL S35 A4 · the shared alt text: {alt!r}"
    print("PASS S35 A4 · A shared analysis gives the same card")
