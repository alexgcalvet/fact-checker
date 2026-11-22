import json
import os
import signal
import subprocess
import time
from pathlib import Path

from fact_checker.core.flags import split
from fact_checker.core.prices import cost as cost_of

RETRY_WAITS = (30, 60)
# The full ids of Claude Code's model aliases, for the price table.
MODEL_IDS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
TOKENS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


class NoAnswer(RuntimeError):
    """The reading ended with text instead of the JSON that the schema asks for."""


class Busy(RuntimeError):
    pass


class Answer(dict):
    """The structured output of one reading; `usage` holds its tokens, model and API-equivalent cost in dollars."""
    usage: dict


class ClaudeCLI:
    """Claude Code headless (`claude -p`) on the person's subscription."""

    def __init__(self, workdir: Path, model: str = "sonnet", timeout: int = 300, keys: tuple = ()):
        self.workdir = Path(workdir)
        self.keys = keys  # environment variables the reading never gets
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, schema: dict, tools: tuple = ()) -> dict:
        """Retries a 429 (too many requests at once) or an answer with no JSON twice, after 30 s and 60 s."""
        for wait in RETRY_WAITS:
            try:
                return self._complete(prompt, schema, tools)
            except (Busy, NoAnswer):
                time.sleep(wait)
        return self._complete(prompt, schema, tools)

    def _complete(self, prompt: str, schema: dict, tools: tuple) -> dict:
        # Claude Code's own coding prompt, its tools and any CLAUDE.md above the working folder would add
        # thousands of input tokens to every call: the call gets a short system prompt, only the tools it asks
        # for, and no setting sources (which also skips CLAUDE.md). A prompt with fixed `rules` sends them in the
        # system prompt, the same text in every reading, so they are read from cache.
        # Its own process group: on a timeout the whole group is killed, so a child that holds the
        # output open (a web tool) cannot keep the call waiting.
        # Every reading asks for medium effort and the five-minute cache: a reading's cache is read again within
        # minutes or never, and the one-hour cache that a subscription gets by default costs 1.6 times as much to write.
        # A reading never opens a page: the search results are enough, and a fetched page costs thousands of tokens.
        # WebFetch stays in --tools and is denied, because an approved S17 test lists both tools.
        # A prompt with a `session` resumes that Claude Code conversation; its files stay under the working folder's
        # project. Any other reading keeps no session on disk.
        system, text = split(prompt)
        session = getattr(prompt, "session", None)
        resume = (["--resume", session.id] if session.turns else ["--session-id", session.id]) if session \
            else ["--no-session-persistence"]
        proc = subprocess.Popen(
            ["claude", "-p", text, "--output-format", "json", "--json-schema", json.dumps(schema),
             "--model", self.model, "--effort", "medium", "--system-prompt", system, "--tools", ",".join(tools),
             "--setting-sources=", *resume, *(["--allowedTools", *tools, "--disallowedTools", "WebFetch"] if tools else [])],
            cwd=self.workdir, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True, env={k: v for k, v in os.environ.items() if k not in self.keys} | {"FORCE_PROMPT_CACHING_5M": "1"})
        try:
            stdout, stderr = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise RuntimeError(f"claude -p timed out after {self.timeout} s")
        try:
            out = json.loads(stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"claude -p failed: {stderr.strip()[:200]}")
        if out.get("api_error_status") == 429:
            raise Busy("claude -p error: 429")
        if proc.returncode or out.get("is_error"):
            raise RuntimeError(f"claude -p error: {out.get('api_error_status') or out.get('result')}")
        if "structured_output" not in out:
            raise NoAnswer(f"claude -p gave no JSON: {str(out.get('result'))[:200]}")
        answer = Answer(out["structured_output"])
        usage = {k: out["usage"][k] for k in TOKENS}
        # A resumed session's total_cost_usd keeps growing with the conversation, far past what its tokens cost (45.56
        # against 7.40 dollars on the 1.5-hour interview), so a resumed reading is priced from its own tokens.
        cost = cost_of(MODEL_IDS.get(self.model, self.model), usage) if session and session.turns \
            else out["total_cost_usd"]
        answer.usage = usage | {"cost_usd": cost if cost is None else round(cost, 6), "model": self.model}
        if session:
            session.turns += 1
            session.tokens = sum(out["usage"][k] for k in TOKENS[:3])
        return answer
