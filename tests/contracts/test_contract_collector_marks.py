"""Contract · feedback collector · POST /marks and GET /marks

A deployed collector (the owner's Cloudflare Worker) answers a POST and an admin GET with the same field names and types
as the fake in tests/fakes/collector/marks.json. Values are never compared. Opt-in: skips unless S24_COLLECTOR_URL and
FEEDBACK_ADMIN_TOKEN are set in the environment, or when the collector cannot be reached. Stores one invented mark under
a fresh random install id, which the owner can delete by that id.
"""
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

FAKE = json.loads((Path(__file__).parents[1] / "fakes" / "collector" / "marks.json").read_text())
SKIP = "SKIP contract collector: sandbox not reachable"
MARK = {"video_id": "abcdefgh", "flag_id": "contract-12.5", "t": 12.5, "type": "fallacy", "label": "ad_hominem",
        "quote": "frase inventada", "confidence": 0.5, "verdict": "unfair", "reason": "", "provider": "claude",
        "model": "opus"}


def types(obj):
    return {k: type(v).__name__ for k, v in obj.items()}


def call(req):
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        pytest.fail(f"FAIL contract collector: HTTP {e.code} {e.read()[:300]}")
    except OSError:
        pytest.skip(SKIP)


def test_contract_collector_marks():
    url, token = os.environ.get("S24_COLLECTOR_URL"), os.environ.get("FEEDBACK_ADMIN_TOKEN")
    if not url or not token:
        pytest.skip(SKIP)
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    install = str(uuid.uuid4())
    body = {"install_id": install, "helper_version": "contract", "marks": [MARK]}

    # Case 1 · a POST of one mark → the fake's field names and types
    posted = call(urllib.request.Request(f"{url}/marks", data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "User-Agent": "fact-checker-helper"}))
    assert types(posted) == types(FAKE["post"]), f"FAIL contract collector: {posted}"

    # Case 2 · an admin GET → rows whose fields have the fake's names and types
    rows = call(urllib.request.Request(f"{url}/marks?since={since}", headers={"Authorization": f"Bearer {token}", "User-Agent": "fact-checker-helper"}))
    mine = [r for r in rows["rows"] if r["install_id"] == install]
    assert mine, "FAIL contract collector: rows"
    assert types(mine[0]) == types(FAKE["get"]["rows"][0]), f"FAIL contract collector: {types(mine[0])}"
    print("PASS contract collector")
