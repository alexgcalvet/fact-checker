"""Contract · YouTube via yt-dlp · captions

The live json3 captions of a real video have the same field names and types as the invented fake in
tests/fakes/youtube/. Values are never compared. Skips when S1_VIDEO_URL is not set or yt-dlp fails.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "youtube" / "invented-dialogue.json3"


def shape(event):
    return {k: type(v).__name__ for k, v in event.items() if k != "segs"}


def test_contract_youtube_captions(tmp_path):
    url = os.environ.get("S1_VIDEO_URL")
    if not url:
        pytest.skip("SKIP contract youtube: sandbox not reachable")
    run = subprocess.run(["yt-dlp", "--no-simulate", "--skip-download", "--write-auto-subs", "--sub-langs", "es-orig",
                          "--sub-format", "json3", "-o", str(tmp_path / "v"), url], capture_output=True)
    files = list(tmp_path.glob("*.json3"))
    if run.returncode or not files:
        pytest.skip("SKIP contract youtube: sandbox not reachable")
    live = json.loads(files[0].read_text())
    fake = json.loads(FAKE.read_text())
    for key in ("events",):
        assert isinstance(live.get(key), list), f"FAIL contract youtube: {key}"
    live_event = next(e for e in live["events"] if e.get("segs") and "aAppend" not in e)
    fake_event = next(e for e in fake["events"] if e.get("segs") and "aAppend" not in e)
    for field, kind in shape(fake_event).items():
        assert shape(live_event).get(field) == kind, f"FAIL contract youtube: events[].{field}"
    live_seg_fields = {k for e in live["events"] for s in e.get("segs", []) for k in s}
    fake_seg_fields = {k for e in fake["events"] for s in e.get("segs", []) for k in s}
    assert fake_seg_fields <= live_seg_fields, f"FAIL contract youtube: segs {fake_seg_fields - live_seg_fields}"
