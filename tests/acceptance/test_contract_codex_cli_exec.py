"""Contract · Codex CLI (codex exec) · exec

S20 A2 · The real Codex CLI answers as the adapter expects

Story: The person, logged in to Codex, runs the contract test. One real Codex reading returns a thread id, an answer
that follows the schema and its token usage, with the same fields as the recorded fake. Without a working login it
says SKIP and passes.

Setup: the command in CODEX_BIN, else `codex` on PATH. One live `codex exec --json` reading with a one-field schema,
by the model in CODEX_MODEL, else with no -m (the account's default model: S22), in a temporary folder, with no session on disk. The events of the live stream are compared with
tests/fakes/codex-cli/exec.jsonl by event type, field names and types, never by value. Then the same reading runs
through the Codex adapter, with the options that the helper uses. Skips when the command does not
run, `codex login status` fails, or the reading fails with an auth error.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "codex-cli" / "exec.jsonl"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
SKIP = "SKIP contract codex-cli: sandbox not reachable"
AUTH = ("sign in again", "log in", "login", "401", "unauthorized")


def shape(value):
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    return type(value).__name__


def missing(want, got, path=""):
    """The fields of `want` that `got` lacks or holds with another type."""
    if not isinstance(want, dict):
        return [] if want == got else [path]
    if not isinstance(got, dict):
        return [path]
    return [m for k, v in want.items() for m in missing(v, got.get(k), f"{path}.{k}")]


def by_type(lines):
    events = {}
    for e in (json.loads(x) for x in lines if x.strip()):
        key = e["type"] + (f":{e['item']['type']}" if "item" in e else "")
        events[key] = shape(e)
    return events


def test_contract_codex_cli_exec(tmp_path):
    codex = os.environ.get("CODEX_BIN", "codex")
    try:
        status = subprocess.run([codex, "login", "status"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except OSError:
        pytest.skip(SKIP)
    if status.returncode:
        pytest.skip(SKIP)
    (tmp_path / "schema.json").write_text(json.dumps(SCHEMA))
    model = os.environ.get("CODEX_MODEL")
    run = subprocess.run([codex, "exec", "--json", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
                          "--ignore-rules", *(["-m", model] if model else []), "-c", 'model_reasoning_effort="low"',
                          "-c", 'web_search="disabled"', "-c", 'sandbox_mode="read-only"',
                          "-c", 'approval_policy="never"', "--output-schema", str(tmp_path / "schema.json"), "-"],
                         input="Answer ok=true.", capture_output=True, text=True, cwd=tmp_path, timeout=300)
    failed = [json.loads(x) for x in run.stdout.splitlines() if '"turn.failed"' in x]
    if failed and any(word in json.dumps(failed).lower() for word in AUTH):
        pytest.skip(SKIP)
    assert run.returncode == 0, f"FAIL contract codex-cli: exit {run.returncode}: {run.stdout[-300:]}"

    # Case 1 · the live events → every event type of the fake, with its field names and types
    fake, live = by_type(FAKE.read_text().splitlines()), by_type(run.stdout.splitlines())
    for key, want in fake.items():
        assert key in live, f"FAIL contract codex-cli: {key}"
        assert not missing(want, live[key]), f"FAIL contract codex-cli: {key}{missing(want, live[key])}"

    # Case 2 · the agent message → JSON that follows the schema
    message = [json.loads(x)["item"]["text"] for x in run.stdout.splitlines() if '"agent_message"' in x][-1]
    assert isinstance(json.loads(message)["ok"], bool), f"FAIL contract codex-cli: answer {message[:200]}"
    # Case 3 · the same reading through the adapter, with its own options → the answer and its token usage
    from fact_checker.adapters.llm_codex_cli import CodexCLI
    answer = CodexCLI(tmp_path, model=model).complete("Answer ok=true.", SCHEMA)
    assert isinstance(answer["ok"], bool), f"FAIL contract codex-cli: adapter answer {answer}"
    assert answer.usage["model"] == (model or "codex-default") and answer.usage["output_tokens"] > 0, \
        f"FAIL contract codex-cli: adapter usage {answer.usage}"
    print("PASS S20 A2 · The real Codex CLI answers as the adapter expects")
