import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

from fact_checker.core.flags import split


class Answer(dict):
    """The structured output of one reading; `usage` holds its tokens and model, with no dollar cost."""
    usage: dict


class CodexCLI:
    """Codex CLI headless (`codex exec`) on the person's ChatGPT subscription."""

    def __init__(self, workdir: Path, model: str | None = None, timeout: int = 300):
        self.workdir = Path(workdir)
        self.model = model
        self.timeout = timeout

    def complete(self, prompt, schema: dict, tools: tuple = ()) -> dict:
        # The rules replace Codex's own coding instructions, and no user config, plugin, MCP server or AGENTS.md is
        # loaded, so a reading sends only the prompt. Any tool asked for means the web search: Codex has no fetch tool.
        # A ChatGPT limit lasts hours, so a failed reading is not retried. With no model, no -m is passed: Codex
        # uses the account's own default, since each plan allows other models; the usage then says codex-default.
        # Its event stream does not name the model.
        # A prompt with a `session` resumes that Codex thread; its first reading learns the thread id. Any other
        # reading keeps no session on disk.
        system, text = split(prompt)
        session = getattr(prompt, "session", None)
        with tempfile.TemporaryDirectory(dir=self.workdir) as tmp:
            (Path(tmp) / "rules.md").write_text(system)
            (Path(tmp) / "schema.json").write_text(json.dumps(schema))
            head = ["exec", "resume", session.id] if session and session.turns else ["exec"]
            options = [
                "--json", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
                *(["-m", self.model] if self.model else []),
                "-c", 'model_reasoning_effort="medium"', "-c", f'model_instructions_file="{tmp}/rules.md"',
                "-c", f'web_search="{"live" if tools else "disabled"}"', "-c", "project_doc_max_bytes=0",
                "-c", 'sandbox_mode="read-only"', "-c", 'approval_policy="never"',
                "--output-schema", f"{tmp}/schema.json", *([] if session else ["--ephemeral"]), "-"]
            proc = subprocess.Popen(
                [os.environ.get("CODEX_BIN", "codex"), *head, *options], cwd=self.workdir, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                stdout, stderr = proc.communicate(text, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                raise RuntimeError(f"codex exec timed out after {self.timeout} s")
        events = [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]
        failed = next((e for e in events if e["type"] in ("turn.failed", "error")), None)
        messages = [e["item"]["text"] for e in events
                    if e["type"] == "item.completed" and e["item"]["type"] == "agent_message"]
        if failed or proc.returncode or not messages:
            reason = failed and (failed.get("message") or failed.get("error", {}).get("message"))
            raise RuntimeError(f"codex exec error: {reason or stderr.strip()[-200:]}")
        usage = next(e["usage"] for e in reversed(events) if e["type"] == "turn.completed")
        answer = Answer(json.loads(messages[-1]))
        answer.usage = {"input_tokens": usage["input_tokens"] - usage["cached_input_tokens"],
                        "cache_creation_input_tokens": 0, "cache_read_input_tokens": usage["cached_input_tokens"],
                        "output_tokens": usage["output_tokens"], "cost_usd": 0, "model": self.model or "codex-default"}
        if session:
            if not session.turns:
                session.id = next(e["thread_id"] for e in events if e["type"] == "thread.started")
            session.turns += 1
            session.tokens = usage["input_tokens"]
        return answer
