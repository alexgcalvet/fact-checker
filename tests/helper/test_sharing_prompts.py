"""S7 A2 · A shared analysis names its prompts version and carries that prompts file

Story: A tester with sharing on finishes a whole analysis. The collector gets the analysis with helper version
`0.1.0+3f2a9c1b7d4e` (the version of that helper) and, in the same upload, the prompts file of that version. For the
invented prompts file of the API examples, the helper computes the same version that the file states.

Setup: the S28 fake collector on a free local port, a temporary helper home, and the invented shared analysis of
tests/support/shared_analysis_fakes.py, uploaded as the helper does after a whole analysis. The S28 tests already prove
that a whole analysis reaches this upload.
"""
import json
from pathlib import Path

from fact_checker import analyses, prompts
from fake_servers import FakeCollector
from shared_analysis_fakes import ANALYSIS

EXAMPLE = Path(__file__).resolve().parents[2] / "docs" / "api-examples" / "prompts.json"


def test_upload_names_prompts(tmp_path):
    collector = FakeCollector()
    try:
        # Case 1 · one upload → the body holds the install id, the analysis and the prompts file
        analyses.upload(tmp_path, collector.url, ANALYSIS)
        body = collector.wait_puts(1)[0]["body"]
        assert set(body) == {"install_id", "analysis", "prompts"}, f"FAIL S7 A2 · body fields {sorted(body)}"

        # Case 2 · the analysis's helper version → the version of the prompts file, which is this helper's export
        exported = prompts.export()
        assert body["analysis"]["helper_version"] == body["prompts"]["version"] == exported["version"], \
            f"FAIL S7 A2 · {body['analysis']['helper_version']} vs {body['prompts']['version']}"
        assert body["prompts"] == exported, "FAIL S7 A2 · the uploaded prompts differ from the export"
    finally:
        collector.stop()

    # Case 3 · the invented prompts file of the API examples → the helper computes the version it states
    example = json.loads(EXAMPLE.read_text())
    assert prompts.version_of(example["components"], example["version"].split("+")[0]) == example["version"], \
        "FAIL S7 A2 · the helper and the example disagree on the version"
    print("PASS S7 A2 · A shared analysis names its prompts version and carries that prompts file")
