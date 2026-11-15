"""Contract · Anthropic Messages API · messages

A live Messages request with a one-field JSON schema returns the same top-level and usage field names and types as the
docs-built fake in tests/fakes/anthropic-api/messages.json, and the same reading through the adapter gives the answer,
its tokens and a dollar cost. Values are never compared. Skips when ANTHROPIC_API_KEY is not set or the API cannot be
reached. Spends one small reading of `claude-sonnet-5-5` twice.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "anthropic-api" / "messages.json"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
MODEL = "claude-sonnet-5-5"
SKIP = "SKIP contract anthropic-api: sandbox not reachable"


def types(obj):
    return {k: type(v).__name__ for k, v in obj.items()}


def test_contract_anthropic_messages():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip(SKIP)
    body = {"model": MODEL, "max_tokens": 1024, "messages": [{"role": "user", "content": "Answer ok=true."}],
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}}
    request = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={
        "x-api-key": key, "anthropic-version": "2026-10-21", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as r:
            live = json.load(r)
    except urllib.error.HTTPError as e:
        assert e.code not in (400, 404), f"FAIL contract anthropic-api: HTTP {e.code} {e.read()[:300]}"
        pytest.skip(SKIP)
    except OSError:
        pytest.skip(SKIP)
    fake = json.loads(FAKE.read_text())

    # Case 1 · the live answer → every top-level and usage field of the fake, with its type
    for field, kind in types(fake).items():
        if field not in ("stop_details", "stop_sequence"):
            assert types(live).get(field) == kind, f"FAIL contract anthropic-api: {field}"
    for field, kind in types(fake["usage"]).items():
        if field in ("server_tool_use", "service_tier"):
            continue  # a request with no server tool may leave them out
        assert types(live["usage"]).get(field) == kind, f"FAIL contract anthropic-api: usage.{field}"
    # Case 2 · the last text block → JSON that follows the schema
    text = [b["text"] for b in live["content"] if b["type"] == "text"][-1]
    assert isinstance(json.loads(text)["ok"], bool), f"FAIL contract anthropic-api: answer {text[:200]}"
    # Case 3 · the same reading through the adapter → the answer, its tokens and a dollar cost
    from fact_checker.adapters.llm_anthropic_api import AnthropicAPI
    answer = AnthropicAPI(model=MODEL, key=key).complete("Answer ok=true.", SCHEMA)
    assert isinstance(answer["ok"], bool), f"FAIL contract anthropic-api: adapter answer {answer}"
    assert answer.usage["output_tokens"] > 0 and answer.usage["cost_usd"] > 0, \
        f"FAIL contract anthropic-api: adapter usage {answer.usage}"
    print("PASS contract anthropic-api · messages")
