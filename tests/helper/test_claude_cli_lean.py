"""A `claude -p` call carries only our prompt: no Claude Code coding prompt, no tools it was not given, and no
CLAUDE.md of a folder above it (each costs thousands of input tokens per call)."""
import json
import os
from pathlib import Path

from fact_checker.adapters.llm_claude_cli import ClaudeCLI


USAGE = {"input_tokens": 3, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 1}

def run(tmp_path, monkeypatch, tools=()):
    seen = tmp_path / "seen"
    fake = tmp_path / "claude"
    ok = json.dumps({"is_error": False, "total_cost_usd": 0.01, "usage": USAGE, "structured_output": {}})
    fake.write_text(f'#!/bin/sh\npwd > {seen}\nfor a in "$@"; do echo "[$a]" >> {seen}; done\necho \'{ok}\'\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    ClaudeCLI(tmp_path, model="opus").complete("hola", {"type": "object"}, tools=tools)
    cwd, *args = seen.read_text().splitlines()
    return Path(cwd).resolve(), args


def test_no_coding_prompt_no_tools_no_claude_md(tmp_path, monkeypatch):
    _, args = run(tmp_path, monkeypatch)
    assert "[--setting-sources=]" in args
    assert "[--system-prompt]" in args
    assert args[args.index("[--tools]") + 1] == "[]"


def test_web_search_is_the_only_tool_when_asked(tmp_path, monkeypatch):
    _, args = run(tmp_path, monkeypatch, tools=("WebSearch",))
    assert args[args.index("[--tools]") + 1] == "[WebSearch]"
