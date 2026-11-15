"""Contract · OpenAI Responses API · responses

A live Responses request with a one-field strict JSON schema returns the same top-level and usage field names and
types as the docs-built fake in tests/fakes/openai-api/responses.json, and the same reading through the adapter gives
the answer and its tokens. Values are never compared. The endpoint is OPENAI_BASE_URL (default
https://api.openai.com/v1), the key is in the variable that OPENAI_KEY_ENV names (default OPENAI_API_KEY), and the model
is OPENAI_CONTRACT_MODEL (default gpt-6-luna); for xAI set https://api.x.ai/v1, XAI_API_KEY and a Grok model. Skips
when the key is not set or the API cannot be reached. Spends one small reading twice.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "openai-api" / "responses.json"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
SKIP = "SKIP contract openai-api: sandbox not reachable"


def types(obj):
    return {k: type(v).__name__ for k, v in obj.items()}


def test_contract_openai_responses():
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    key = os.environ.get(os.environ.get("OPENAI_KEY_ENV", "OPENAI_API_KEY"))
    model = os.environ.get("OPENAI_CONTRACT_MODEL", "gpt-6-luna")
    if not key:
        pytest.skip(SKIP)
    body = {"model": model, "input": "Answer ok=true.", "store": False, "reasoning": {"effort": "low"},
            "text": {"format": {"type": "json_schema", "name": "answer", "schema": SCHEMA, "strict": True}}}
    request = urllib.request.Request(f"{base_url}/responses", data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as r:
            live = json.load(r)
    except urllib.error.HTTPError as e:
        assert e.code not in (400, 404), f"FAIL contract openai-api: HTTP {e.code} {e.read()[:300]}"
        pytest.skip(SKIP)
    except OSError:
        pytest.skip(SKIP)
    fake = json.loads(FAKE.read_text())

    # Case 1 · the live answer → the fields the adapter reads, with the fake's types
    for field in ("id", "status", "output", "usage"):
        assert types(live).get(field) == types(fake)[field], f"FAIL contract openai-api: {field}"
    for field, kind in types(fake["usage"]).items():
        assert types(live["usage"]).get(field) == kind, f"FAIL contract openai-api: usage.{field}"
    assert isinstance(live["usage"]["input_tokens_details"].get("cached_tokens"), int), \
        "FAIL contract openai-api: usage.input_tokens_details.cached_tokens"
    # Case 2 · the last message → output_text that follows the schema
    message = [i for i in live["output"] if i["type"] == "message"][-1]
    text = [c["text"] for c in message["content"] if c["type"] == "output_text"][-1]
    assert isinstance(json.loads(text)["ok"], bool), f"FAIL contract openai-api: answer {text[:200]}"
    # Case 3 · the same reading through the adapter → the answer and its tokens
    from fact_checker.adapters.llm_openai_api import OpenAIAPI
    answer = OpenAIAPI(model=model, key=key, base_url=base_url).complete("Answer ok=true.", SCHEMA)
    assert isinstance(answer["ok"], bool), f"FAIL contract openai-api: adapter answer {answer}"
    assert answer.usage["output_tokens"] > 0, f"FAIL contract openai-api: adapter usage {answer.usage}"
    print("PASS contract openai-api · responses")
