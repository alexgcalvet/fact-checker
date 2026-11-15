"""Contract · Tavily · search

A live Tavily search returns the same top-level and result field names and types as the docs-built fake in
tests/fakes/tavily/search.json, and the adapter gives results with a title, a URL and a snippet. Values are never
compared. Skips when TAVILY_API_KEY is not set or the API cannot be reached. Spends 2 of the free monthly credits.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "tavily" / "search.json"
SKIP = "SKIP contract tavily: sandbox not reachable"
QUERY = "tasa de paro EPA INE"


def types(obj):
    return {k: type(v).__name__ for k, v in obj.items()}


def test_contract_tavily_search():
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        pytest.skip(SKIP)
    body = {"query": QUERY, "search_depth": "basic", "max_results": 5, "include_published_date": True}
    request = urllib.request.Request("https://api.tavily.com/search", data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            live = json.load(r)
    except urllib.error.HTTPError as e:
        assert e.code not in (400, 401, 422), f"FAIL contract tavily: HTTP {e.code} {e.read()[:300]}"
        pytest.skip(SKIP)
    except OSError:
        pytest.skip(SKIP)
    fake = json.loads(FAKE.read_text())

    # Case 1 · the live answer → a results list whose items have the fake's field names and types
    assert types(live).get("results") == "list", "FAIL contract tavily: results"
    assert live["results"], "FAIL contract tavily: results is empty"
    for field in ("title", "url", "content"):
        assert types(live["results"][0]).get(field) == types(fake["results"][0])[field], f"FAIL contract tavily: {field}"
    assert "published_date" in live["results"][0], "FAIL contract tavily: published_date"
    # Case 2 · the adapter → results with a title, a URL and a snippet
    from fact_checker.adapters.search_tavily import Tavily
    results = Tavily(key).search(QUERY)
    assert results and all(r["url"] and r["title"] and r["content"] for r in results), results
    print("PASS contract tavily")
