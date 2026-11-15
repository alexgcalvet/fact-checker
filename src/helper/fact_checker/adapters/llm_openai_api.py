import json
import time
import urllib.error
import urllib.request

from fact_checker.core.prices import cost
from fact_checker.core.flags import split

RETRY_WAITS = (30, 60)


class Answer(dict):
    """The structured output of one reading; `usage` holds its tokens, model and dollar cost."""
    usage: dict


class OpenAIAPI:
    """Any OpenAI-compatible Responses API on the person's API key: OpenAI, or xAI Grok by its base URL."""

    def __init__(self, model: str = "gpt-6-astra", key: str | None = None, base_url: str = "https://api.openai.com/v1",
                 key_env: str = "OPENAI_API_KEY", timeout: int = 300):
        self.model, self.key, self.base_url, self.key_env, self.timeout = model, key, base_url, key_env, timeout
        self.last = {}  # session id → the id of its last response

    def complete(self, prompt, schema: dict, tools: tuple = ()) -> dict:
        # The rules go in `instructions`, which a chained response does not carry over, so every reading sends them.
        # A conversation is stored and continues from its last response id with only the new part. Any tool asked
        # for means the web search.
        if not self.key:
            raise RuntimeError(f"{self.key_env} is not set")
        system, text = split(prompt)
        session = getattr(prompt, "session", None)
        previous = session and self.last.get(session.id)
        reply = self._post({
            "model": self.model, "instructions": system, "input": text, "reasoning": {"effort": "medium"},
            "text": {"format": {"type": "json_schema", "name": "answer", "schema": schema, "strict": True}},
            "store": bool(session), **({"previous_response_id": previous} if previous else {}),
            **({"tools": [{"type": "web_search"}]} if tools else {})})
        if reply["status"] != "completed":
            raise RuntimeError(f"Responses API {reply['status']}: {reply.get('error') or reply.get('incomplete_details')}")
        content = [i for i in reply["output"] if i["type"] == "message"][-1]["content"]
        refusal = next((c["refusal"] for c in content if c["type"] == "refusal"), None)
        if refusal:
            raise RuntimeError(f"Responses API refused: {refusal[:200]}")
        answer = Answer(json.loads([c["text"] for c in content if c["type"] == "output_text"][-1]))
        u = reply["usage"]
        cached = u["input_tokens_details"]["cached_tokens"]
        usage = {"input_tokens": u["input_tokens"] - cached, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": cached, "output_tokens": u["output_tokens"]}
        dollars = cost(self.model, usage, sum(i["type"] == "web_search_call" for i in reply["output"]))
        answer.usage = usage | {"cost_usd": None if dollars is None else round(dollars, 6), "model": self.model}
        if session:
            self.last[session.id] = reply["id"]
            session.turns += 1
            session.tokens = u["input_tokens"]
            session.cost_usd += dollars or 0
        return answer

    def _post(self, body: dict) -> dict:
        """Retries a rate limit (429) twice, after 30 s and 60 s."""
        for wait in (*RETRY_WAITS, None):
            request = urllib.request.Request(f"{self.base_url}/responses", data=json.dumps(body).encode(), headers={
                "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code != 429 or wait is None:
                    raise RuntimeError(f"Responses API error {e.code}: {e.read().decode()[:200]}")
                time.sleep(wait)
