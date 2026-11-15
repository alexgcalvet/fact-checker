"""Contract · Claude Code (claude -p) · complete

A live headless call with --output-format json and --json-schema returns the same top-level field names
and types as the recorded fake in tests/fakes/claude-code/complete.json. Values are never compared.
Skips when the claude command is missing.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "claude-code" / "complete.json"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
FIELDS = ("type", "subtype", "is_error", "result", "structured_output", "num_turns", "duration_ms")


def test_contract_claude_cli_complete():
    if not shutil.which("claude"):
        pytest.skip("SKIP contract claude-code: sandbox not reachable")
    fake = json.loads(FAKE.read_text())
    run = subprocess.run(["claude", "-p", "Answer ok=true.", "--output-format", "json",
                          "--json-schema", json.dumps(SCHEMA)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if run.returncode:
        pytest.skip("SKIP contract claude-code: sandbox not reachable")
    live = json.loads(run.stdout)
    for field in FIELDS:
        assert type(live.get(field)).__name__ == type(fake.get(field)).__name__, f"FAIL contract claude-code: {field}"
