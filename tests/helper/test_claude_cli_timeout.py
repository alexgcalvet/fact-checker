"""A `claude -p` that hangs is cut at the timeout, also when a child process it started holds its output open."""
import os
import time

import pytest

from fact_checker.adapters.llm_claude_cli import ClaudeCLI


def test_hung_claude_is_cut(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\nsleep 30 &\nsleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        ClaudeCLI(tmp_path, timeout=1).complete("hola", {"type": "object"})
    assert time.monotonic() - t0 < 10
