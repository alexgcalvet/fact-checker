"""Contract · Google Fact Check Tools API · claims:search

A live search returns the same field names and types as the recorded fake in
tests/fakes/google-factcheck/claims-search.json. Values are never compared. Skips when
FACT_CHECK_API_KEY is not set or the API cannot be reached.
"""
import json
import os
import urllib.request
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "google-factcheck" / "claims-search.json"
URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search?languageCode=es&pageSize=5&query=paro%20juvenil"


def types(obj):
    return {k: type(v).__name__ for k, v in obj.items()}


def test_contract_google_factcheck_claims_search():
    key = os.environ.get("FACT_CHECK_API_KEY")
    if not key:
        pytest.skip("SKIP contract google-factcheck: sandbox not reachable")
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers={"X-goog-api-key": key}), timeout=20) as r:
            live = json.load(r)
    except OSError:
        pytest.skip("SKIP contract google-factcheck: sandbox not reachable")
    fake = json.loads(FAKE.read_text())
    assert isinstance(live.get("claims"), list), "FAIL contract google-factcheck: claims"
    for field, kind in types(fake["claims"][0]).items():
        assert any(types(c).get(field) == kind for c in live["claims"]), f"FAIL contract google-factcheck: claims[].{field}"
    for field, kind in types(fake["claims"][0]["claimReview"][0]).items():
        reviews = [r for c in live["claims"] for r in c["claimReview"]]
        assert any(types(r).get(field) == kind for r in reviews), f"FAIL contract google-factcheck: claimReview[].{field}"
