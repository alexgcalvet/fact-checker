"""A 429 from `claude -p` is retried after a wait instead of stopping the analysis."""
import json
import os

from fact_checker.adapters import llm_claude_cli
from fact_checker.adapters.llm_claude_cli import ClaudeCLI


USAGE = {"input_tokens": 3, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 1}

def test_429_is_retried(tmp_path, monkeypatch):
    calls = tmp_path / "calls"
    fake = tmp_path / "claude"
    busy = json.dumps({"is_error": True, "api_error_status": 429})
    ok = json.dumps({"is_error": False, "total_cost_usd": 0.01, "usage": USAGE, "structured_output": {"flags": []}})
    fake.write_text(f"#!/bin/sh\necho x >> {calls}\n"
                    f"if [ $(wc -l < {calls}) -lt 3 ]; then echo '{busy}'; exit 1; fi\necho '{ok}'\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    waits = []
    monkeypatch.setattr(llm_claude_cli.time, "sleep", waits.append)
    assert ClaudeCLI(tmp_path).complete("hola", {"type": "object"}) == {"flags": []}
    assert len(calls.read_text().splitlines()) == 3
    assert len(waits) == 2
