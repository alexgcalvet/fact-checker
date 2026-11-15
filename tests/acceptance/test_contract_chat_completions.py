"""Contract · Chat Completions API · chat/completions

A live Chat Completions request with a one-field strict JSON schema returns the same top-level, choice and usage field
names and types as the docs-built fake in tests/fakes/chat-api/completion.json, and the same reading through the
adapter gives the answer and its tokens. Values are never compared. It runs only when the person opts in: the
endpoint is CHAT_CONTRACT_BASE_URL (such as https://router.huggingface.co/v1), the model CHAT_CONTRACT_MODEL, and the
key is in the variable that CHAT_CONTRACT_KEY_ENV names (default HF_TOKEN; none needed on localhost). Skips otherwise,
or when the API cannot be reached. Spends one small reading twice.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

FAKE = Path(__file__).parents[1] / "fakes" / "chat-api" / "completion.json"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
SKIP = "SKIP contract chat-api: sandbox not reachable"


def types(obj):
    return {k: type(v).__name__ for k, v in obj.items()}


def test_contract_chat_completions():
    base_url, model = os.environ.get("CHAT_CONTRACT_BASE_URL"), os.environ.get("CHAT_CONTRACT_MODEL")
    key = os.environ.get(os.environ.get("CHAT_CONTRACT_KEY_ENV", "HF_TOKEN"))
    local = base_url and urlparse(base_url).hostname in ("localhost", "127.0.0.1", "::1")
    if not base_url or not model or not (key or local):
        pytest.skip(SKIP)
    body = {"model": model, "messages": [{"role": "user", "content": "Answer ok=true as JSON."}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": SCHEMA,
                                                                       "strict": True}}}
    request = urllib.request.Request(f"{base_url}/chat/completions", data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})})
    try:
        with urllib.request.urlopen(request, timeout=120) as r:
            live = json.load(r)
    except urllib.error.HTTPError as e:
        assert e.code not in (401, 404), f"FAIL contract chat-api: HTTP {e.code} {e.read()[:300]}"
        pytest.skip(SKIP)
    except OSError:
        pytest.skip(SKIP)
    fake = json.loads(FAKE.read_text())

    # Case 1 · the live answer → the fields the adapter reads, with the fake's types
    for field in ("choices", "usage"):
        assert types(live).get(field) == types(fake)[field], f"FAIL contract chat-api: {field}"
    for field in ("message", "finish_reason"):
        assert types(live["choices"][0]).get(field) == types(fake["choices"][0])[field], \
            f"FAIL contract chat-api: choices[0].{field}"
    for field in ("prompt_tokens", "completion_tokens"):
        assert types(live["usage"]).get(field) == types(fake["usage"])[field], f"FAIL contract chat-api: usage.{field}"
    # Case 2 · the message → content that follows the schema
    text = live["choices"][0]["message"]["content"]
    assert isinstance(json.loads(text)["ok"], bool), f"FAIL contract chat-api: answer {text[:200]}"
    # Case 3 · the same reading through the adapter → the answer and its tokens
    from fact_checker.adapters.llm_chat_api import ChatAPI
    answer = ChatAPI(model=model, key=key, base_url=base_url).complete("Answer ok=true as JSON.", SCHEMA)
    assert isinstance(answer["ok"], bool), answer
    assert answer.usage["output_tokens"] > 0, answer.usage
    print("PASS contract chat-api")
