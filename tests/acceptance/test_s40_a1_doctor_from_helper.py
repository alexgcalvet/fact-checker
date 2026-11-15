"""S40 A1 · The check shows what the helper finds

Story: The login helper runs with a search path that holds no yt-dlp, while the agent's terminal finds it. The agent
runs `fact-checker doctor`. The yt-dlp line says "the helper does not find yt-dlp" with the fix `fact-checker setup`,
and is not ok. The same holds for ffmpeg, uv and the command of the provider in use.

Setup: the S38 machine: a temporary user home and helper home, and five free local ports in place of 8765–8769
(FACT_CHECKER_PORT), so "8765" below is the first of them. The agent's PATH holds only fakes: `claude` logged in,
`codex` logged in, `uv`, `yt-dlp`, `ffmpeg`, `chromium`. The ChatGPT app search points at an empty temporary folder,
in the agent and in the helper. The helper is a real `fact-checker serve --port 8765` that the test starts with a
PATH of its own, as the login agent does: first a folder with every fake but yt-dlp, then an empty folder. A
connection to the real 8765–8769 fails the test. The test stops each helper it starts.
"""
import os
import shutil
import subprocess
import sys

from s38_fakes import health, listening, machine, run, wait
from s39_fakes import FAKE_CODEX, doctor_check, no_app


# The helper process, with the ChatGPT app search pointed at a folder that does not exist.
SERVE = """\
import sys
from pathlib import Path
from fact_checker.adapters import llm_codex_cli
llm_codex_cli.CHATGPT_CODEX = Path(sys.argv[1])
from fact_checker import cli
sys.argv = ["fact-checker", "serve", "--port", sys.argv[2]]
cli.main()
"""


def test_doctor_from_helper(tmp_path, monkeypatch, capsys):
    m = machine(tmp_path, monkeypatch, commands={"codex": FAKE_CODEX})
    no_app(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_LOGGED", "1")
    first, agent_bin = m["first"], tmp_path / "bin"
    helper_bin = tmp_path / "helper-bin"
    helper_bin.mkdir()
    for name in ("claude", "codex", "uv", "ffmpeg", "chromium"):
        shutil.copy(agent_bin / name, helper_bin / name)
    started = []

    def start_helper(path) -> None:
        env = os.environ | {"PATH": str(path), "FAKE_CODEX_LOGGED": "1"}
        started.append(subprocess.Popen([sys.executable, "-c", SERVE, str(tmp_path / "no-app" / "codex"), str(first)],
                                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        assert wait(lambda: health(first)), f"FAIL S40 A1 · the helper does not answer on {first}"

    def stop_helpers() -> None:
        for child in started:
            child.terminate()
            child.wait(timeout=10)
        started.clear()
        assert wait(lambda: not listening(first)), f"FAIL S40 A1 · a helper still listens on {first}"

    def missing(name: str) -> dict:
        return {"name": name, "state": f"the helper does not find {name}", "fix": "fact-checker setup", "ok": False}

    try:
        # Case 1 · the helper's PATH has no yt-dlp → /health says so, from the helper's own PATH
        start_helper(helper_bin)
        assert health(first).get("tools") == {"claude": True, "uv": True, "yt-dlp": False, "ffmpeg": True}, \
            f"FAIL S40 A1 · /health tools: {health(first).get('tools')}"

        # Case 2 · the agent finds yt-dlp, the helper does not → "the helper does not find yt-dlp", fix setup, not ok
        assert doctor_check(monkeypatch, capsys, "yt-dlp") == missing("yt-dlp"), "FAIL S40 A1 · the yt-dlp line"
        assert run(monkeypatch, capsys, "doctor", "--json")[0] == 1, \
            "FAIL S40 A1 · doctor passed with the helper missing yt-dlp"

        # Case 3 · the tools the helper finds keep the agent's line: claude logged in, uv and ffmpeg ok
        assert doctor_check(monkeypatch, capsys, "claude")["state"] == "logged in", "FAIL S40 A1 · the claude line"
        for name in ("uv", "ffmpeg"):
            assert doctor_check(monkeypatch, capsys, name) == {"name": name, "state": "ok", "fix": "", "ok": True}, \
                f"FAIL S40 A1 · the {name} line"

        # Case 4 · the helper's PATH is empty → ffmpeg, uv and claude also say the helper does not find them
        stop_helpers()
        start_helper(tmp_path / "empty")
        for name in ("claude", "uv", "yt-dlp", "ffmpeg"):
            assert doctor_check(monkeypatch, capsys, name) == missing(name), f"FAIL S40 A1 · the {name} line"

        # Case 5 · the provider in use is codex → /health names codex, not claude; the codex line says the helper
        # does not find it
        (m["home"] / "config.toml").write_text('provider = "codex"\n')
        assert set(health(first)["tools"]) == {"codex", "uv", "yt-dlp", "ffmpeg"}, \
            f"FAIL S40 A1 · /health tools for codex: {health(first)['tools']}"
        assert doctor_check(monkeypatch, capsys, "codex") == missing("codex"), "FAIL S40 A1 · the codex line"

        # Case 6 · no helper answers → the lines are the agent's own again: yt-dlp ok
        stop_helpers()
        assert doctor_check(monkeypatch, capsys, "yt-dlp") == {"name": "yt-dlp", "state": "ok", "fix": "", "ok": True}, \
            "FAIL S40 A1 · the yt-dlp line with no helper"
    finally:
        for child in started:
            child.terminate()
            child.wait(timeout=10)
    print("PASS S40 A1 · The check shows what the helper finds")
