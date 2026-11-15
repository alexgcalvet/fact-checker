"""A resumed Claude Code session reports a total cost that keeps growing; a resumed reading is priced from its tokens."""
import json
import os

from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fact_checker.core.flags import Prompt, Session

USAGE = {"input_tokens": 1000, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 100000, "output_tokens": 500}


def test_resumed_reading_costs_its_tokens(tmp_path, monkeypatch):
    totals = tmp_path / "totals"
    totals.write_text("0.10\n2.15\n")
    fake = tmp_path / "claude"
    fake.write_text(f'#!/bin/sh\nt=$(head -1 {totals}); sed -i "" 1d {totals} 2>/dev/null || sed -i 1d {totals}\n'
                    f'echo \'{{"is_error": false, "usage": {json.dumps(USAGE)}, "structured_output": {{}}, '
                    f'"total_cost_usd": \'$t\'}}\'\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    llm, session = ClaudeCLI(tmp_path, model="opus"), Session()
    costs = [llm.complete(Prompt("reglas", "parte", session), {"type": "object"}).usage["cost_usd"] for _ in range(2)]
    # Opus: 1000 × 4 + 2000 × 5 + 100000 × 0.20 + 500 × 20 dollars per million tokens.
    assert costs == [0.10, 0.044], costs
