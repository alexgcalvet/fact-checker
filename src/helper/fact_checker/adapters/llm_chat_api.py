import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from fact_checker.core.prices import cost
from fact_checker.core.flags import split

RETRY_WAITS = (30, 60)
LOCAL = ("localhost", "127.0.0.1", "::1")
TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool,
         "null": type(None)}


class Answer(dict):
    """The structured output of one reading; `usage` holds its tokens, model and dollar cost."""
    usage: dict


def needs_key(base_url: str) -> bool:
    """A server on this machine, such as Ollama or LM Studio, takes no key."""
    return urlparse(base_url).hostname not in LOCAL


def mismatch(value, schema: dict, path: str = "answer") -> str | None:
    """The first place where `value` breaks `schema` (types, enum, required, properties, items), else None."""
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    if kinds and not any(isinstance(value, TYPES[k]) and not (k in ("integer", "number") and isinstance(value, bool))
                         for k in kinds):
        return f"{path} is not {' or '.join(kinds)}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{path} is not one of {schema['enum']}"
    if isinstance(value, dict):
        missing = [k for k in schema.get("required", []) if k not in value]
        if missing:
            return f"{path} lacks {', '.join(missing)}"
        return next((m for k, s in schema.get("properties", {}).items() if k in value
                     if (m := mismatch(value[k], s, f"{path}.{k}"))), None)
    if isinstance(value, list) and "items" in schema:
        return next((m for i, v in enumerate(value) if (m := mismatch(v, schema["items"], f"{path}[{i}]"))), None)
    return None


class ChatAPI:
    """Any Chat Completions API, set by its base URL: Hugging Face, OpenRouter, Groq, Together, DeepSeek, Mistral, or a
    local Ollama or LM Studio. It never searches the web."""

    def __init__(self, model: str, key: str | None = None, base_url: str = "http://localhost:11434/v1",
                 key_env: str = "CHAT_API_KEY", timeout: int = 300):
        self.model, self.key, self.base_url, self.key_env, self.timeout = model, key, base_url, key_env, timeout
        self.json_object = False  # the server rejected json_schema: ask for a JSON object, the schema in the rules
        self.conversations = {}  # session id → its messages so far

    def complete(self, prompt, schema: dict, tools: tuple = ()) -> dict:
        if tools:
            raise RuntimeError("a chat API has no web search")
        if not self.key and needs_key(self.base_url):
            raise RuntimeError(f"{self.key_env} is not set")
        system, text = split(prompt)
        session = getattr(prompt, "session", None)
        earlier = self.conversations.get(session.id) if session else None
        messages = [*(earlier or [{"role": "system", "content": system}]), {"role": "user", "content": text}]
        reply = self._ask(messages, schema)
        choice = reply["choices"][0]
        if choice["message"].get("refusal"):
            raise RuntimeError(f"Chat API refused: {choice['message']['refusal'][:200]}")
        if choice["finish_reason"] != "stop":
            raise RuntimeError(f"Chat API stopped: {choice['finish_reason']}")
        content = choice["message"]["content"]
        try:
            answer = Answer(json.loads(content))
        except (TypeError, json.JSONDecodeError):
            raise RuntimeError(f"Chat API answer is not JSON by the schema: {str(content)[:200]}")
        problem = mismatch(answer, schema)
        if problem:
            raise RuntimeError(f"Chat API answer is not JSON by the schema: {problem}")
        u = reply["usage"]
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        usage = {"input_tokens": u["prompt_tokens"] - cached, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": cached, "output_tokens": u["completion_tokens"]}
        dollars = cost(self.model, usage)
        answer.usage = usage | {"cost_usd": None if dollars is None else round(dollars, 6), "model": self.model}
        if session:
            self.conversations[session.id] = [*messages, {"role": "assistant", "content": content}]
            session.turns += 1
            session.tokens = u["prompt_tokens"]
            session.cost_usd += dollars or 0
        return answer

    def _ask(self, messages: list, schema: dict) -> dict:
        """Asks for strict JSON by the schema. A server that rejects it gets a JSON object request with the schema
        in the rules, from then on."""
        if not self.json_object:
            try:
                return self._post({"model": self.model, "messages": messages, "response_format": {
                    "type": "json_schema", "json_schema": {"name": "answer", "schema": schema, "strict": True}}})
            except urllib.error.HTTPError as e:
                detail = e.read().decode()
                if e.code != 400 or not ("response_format" in detail or "json_schema" in detail):
                    raise RuntimeError(f"Chat API error {e.code}: {detail[:200]}")
                self.json_object = True
        rules = f"{messages[0]['content']}\n\nAnswer with one JSON object that follows this JSON schema:\n" \
                f"{json.dumps(schema)}"
        return self._post({"model": self.model, "messages": [{"role": "system", "content": rules}, *messages[1:]],
                           "response_format": {"type": "json_object"}}, fallback=True)

    def _post(self, body: dict, fallback: bool = False) -> dict:
        """Retries a rate limit (429) twice, after 30 s and 60 s. Without `fallback`, a 400 goes back to `_ask`."""
        for wait in (*RETRY_WAITS, None):
            request = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json",
                                                      **({"Authorization": f"Bearer {self.key}"} if self.key else {})})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 400 and not fallback:
                    raise
                if e.code != 429 or wait is None:
                    raise RuntimeError(f"Chat API error {e.code}: {e.read().decode()[:200]}")
                time.sleep(wait)
