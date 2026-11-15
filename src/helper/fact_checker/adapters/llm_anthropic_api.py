import json
import time
import urllib.error
import urllib.request

from fact_checker.core.prices import cost
from fact_checker.core.flags import split

VERSION = "2026-10-21"
RETRY_WAITS = (30, 60)
BUSY = (429, 529)
SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}
LIMITS = ("minimum", "maximum", "maxItems")  # schema keywords that structured outputs reject
TOKENS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


class Answer(dict):
    """The structured output of one reading; `usage` holds its tokens, model and dollar cost."""
    usage: dict


def supported(schema):
    """The schema without the limits that structured outputs reject; the prompts state the same ranges."""
    if isinstance(schema, list):
        return [supported(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    return {k: {name: supported(s) for name, s in v.items()} if k == "properties" else supported(v)
            for k, v in schema.items() if k not in LIMITS}


class AnthropicAPI:
    """The Anthropic Messages API on the person's API key."""

    def __init__(self, model: str = "claude-opus-5-5", key: str | None = None,
                 base_url: str = "https://api.anthropic.com", key_env: str = "ANTHROPIC_API_KEY", timeout: int = 300):
        self.model, self.key, self.base_url, self.key_env, self.timeout = model, key, base_url, key_env, timeout
        self.conversations = {}  # session id → its messages so far

    def complete(self, prompt, schema: dict, tools: tuple = ()) -> dict:
        # The fixed rules go in a cached system block, the same text in every reading. A conversation also sends
        # the top-level cache control, which moves the breakpoint to its last message, so the next part reads the
        # history from cache. Any tool asked for means the web search: a reading never opens a page.
        # A long search can pause (`pause_turn`): the paused content goes back as the assistant turn and the
        # request runs again.
        if not self.key:
            raise RuntimeError(f"{self.key_env} is not set")
        system, text = split(prompt)
        session = getattr(prompt, "session", None)
        messages = [*self.conversations.get(session.id, []), {"role": "user", "content": text}] if session \
            else [{"role": "user", "content": text}]
        body = {"model": self.model, "max_tokens": 16000,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                **({"cache_control": {"type": "ephemeral"}} if session else {}),
                "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": supported(schema)}},
                **({"tools": [SEARCH_TOOL]} if tools else {})}
        usage, searches = dict.fromkeys(TOKENS, 0), 0
        while True:
            reply = self._post(body | {"messages": messages})
            usage = {k: usage[k] + reply["usage"][k] for k in TOKENS}
            searches += reply["usage"].get("server_tool_use", {}).get("web_search_requests", 0)
            if messages[-1]["role"] == "assistant":
                messages[-1] = {"role": "assistant", "content": messages[-1]["content"] + reply["content"]}
            else:
                messages.append({"role": "assistant", "content": reply["content"]})
            if reply["stop_reason"] != "pause_turn":
                break
        if reply["stop_reason"] in ("refusal", "max_tokens"):
            raise RuntimeError(f"Anthropic API stopped: {reply['stop_reason']}")
        answer = Answer(json.loads([b["text"] for b in reply["content"] if b["type"] == "text"][-1]))
        dollars = cost(self.model, usage, searches)
        answer.usage = usage | {"cost_usd": None if dollars is None else round(dollars, 6), "model": self.model}
        if session:
            self.conversations[session.id] = messages
            session.turns += 1
            session.tokens = sum(reply["usage"][k] for k in TOKENS[:3])
            session.cost_usd += dollars or 0
        return answer

    def _post(self, body: dict) -> dict:
        """Retries a busy API (429 or 529) twice, after 30 s and 60 s."""
        for wait in (*RETRY_WAITS, None):
            request = urllib.request.Request(f"{self.base_url}/v1/messages", data=json.dumps(body).encode(), headers={
                "x-api-key": self.key, "anthropic-version": VERSION, "content-type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code not in BUSY or wait is None:
                    raise RuntimeError(f"Anthropic API error {e.code}: {e.read().decode()[:200]}")
                time.sleep(wait)
