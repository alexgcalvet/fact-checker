"""The fakes that the S39 tests share, on top of the S38 machine: a `codex` that answers `login status` by
FAKE_CODEX_LOGGED, a ChatGPT app folder that is never the real /Applications, and one check of doctor --json.
"""
import json
from pathlib import Path

from s38_fakes import run

from fact_checker import install

FAKE_CODEX = """\
import os, sys
sys.exit(0 if sys.argv[1:3] == ["login", "status"] and os.environ.get("FAKE_CODEX_LOGGED") == "1" else 1)
"""
APP_CODEX = Path("ChatGPT.app") / "Contents" / "Resources" / "codex-cli" / "bin" / "codex"


def no_app(tmp_path: Path, monkeypatch) -> Path:
    """Points the helper's ChatGPT app search at an empty temporary folder; returns where the app's codex would be."""
    codex = tmp_path / "Applications" / APP_CODEX
    monkeypatch.setattr(install, "CHATGPT_CODEX", codex)
    return codex


def doctor_check(monkeypatch, capsys, name: str) -> dict:
    """The check called `name` of `fact-checker doctor --json`."""
    code, out = run(monkeypatch, capsys, "doctor", "--json")
    found = [c for c in json.loads("\n".join(out))["checks"] if c["name"] == name]
    assert len(found) == 1, f"FAIL S39 · one {name} check: {out}"
    return found[0]


def calls(env: dict) -> list[list[str]]:
    """The calls that the fake `launchctl` and `systemctl` logged."""
    log = Path(env["FAKE_LOG"])
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
