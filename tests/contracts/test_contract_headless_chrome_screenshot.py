"""Contract · Headless Chrome · screenshot

The person's installed Chrome, called with the command of docs/archive/001-personal-fact-checker-for-recorded-youtube-videos/research/external-contracts.md, turns a small
page into a PNG whose fields (format, width, height, exit code) have the same names and types as the recorded
fake in tests/fakes/headless-chrome/screenshot.json, and whose size is the window size it was given. Values of
the fake are never compared. Skips when Chrome is not installed at its macOS path.
"""
import json
import struct
import subprocess
from pathlib import Path

import pytest

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FAKE = Path(__file__).parents[1] / "fakes" / "headless-chrome" / "screenshot.json"


def test_contract_headless_chrome_screenshot(tmp_path):
    if not CHROME.exists():
        pytest.skip("SKIP contract headless-chrome: sandbox not reachable")
    page = tmp_path / "page.html"
    page.write_text('<html><body style="margin:0;background:#111;color:#fff;font:30px sans-serif">'
                    "«Ñandú» ✗ ! ≈ ⚑ ? ⇄</body></html>")
    out = tmp_path / "out.png"
    run = subprocess.run([str(CHROME), "--headless", "--disable-gpu", "--hide-scrollbars", f"--screenshot={out}",
                          "--window-size=400,300", page.as_uri()], capture_output=True, timeout=60)
    raw = out.read_bytes() if out.exists() else b""
    live = {"exit_code": run.returncode,
            "format": "png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else None,
            "width": struct.unpack(">I", raw[16:20])[0] if len(raw) > 24 else None,
            "height": struct.unpack(">I", raw[20:24])[0] if len(raw) > 24 else None}
    fake = json.loads(FAKE.read_text())
    for field, value in fake.items():
        assert type(live.get(field)).__name__ == type(value).__name__, f"FAIL contract headless-chrome: {field}"
    assert (live["exit_code"], live["width"], live["height"]) == (0, 400, 300), \
        f"FAIL contract headless-chrome: size {live['width']}×{live['height']}, exit {live['exit_code']}"
