"""S21 A2 · A video without captions uses the speech engine of the machine

Story: The helper analyses an invented video with no Spanish captions. On an Apple silicon Mac it transcribes the audio
with mlx-whisper; on an Intel Mac or on Linux, with faster-whisper; the flags come from the transcribed words in both
cases.
Edge case: WHEN the machine has no speech engine (no uv) THEN the analysis stops with the reason "no Spanish captions,
and no speech engine on this machine: run fact-checker doctor".

Setup: the helper runs as it does for the person (Helper._run), in a temporary helper home per machine, with PATH
holding only a folder of fake commands: `yt-dlp` (prints the publish date and writes no captions), `uv` (writes the
synthetic words of tests/fakes/whisper/transcribe.json to its last argument and logs the script it runs) and `claude`
(flags "La oposición no tiene autoridad para hablar." as an ad hominem, answers every other reading with nothing).
The operating system and the processor are set by replacing platform.system and platform.machine. No Hugging Face
token and no Fact Check Tools API key.
"""
import json
import os
import platform
import sys
from pathlib import Path

import pytest

from fact_checker import server

WORDS = Path(__file__).parents[1] / "fakes" / "whisper" / "transcribe.json"
QUOTE = "La oposición no tiene autoridad para hablar."

FAKE_YTDLP = """\
print("20240315")
"""
FAKE_UV = f"""\
import json, os, shutil, sys
with open(os.environ["FAKE_UV_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
shutil.copy({str(WORDS)!r}, sys.argv[-1])
"""
FAKE_CLAUDE = f"""\
import json, sys
args = sys.argv[1:]
schema = json.loads(args[args.index("--json-schema") + 1])["properties"]
answer = {{k: [] for k in schema}}
if "flags" in schema:
    answer["flags"] = [{{"quote": {QUOTE!r}, "label": "ad_hominem", "speaker": "ministro",
                        "reason": "Ataca a la oposición.", "confidence": 0.9}}]
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "total_cost_usd": 0.0, "usage": {{"input_tokens": 1, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 0, "output_tokens": 1}}, "result": json.dumps(answer), "structured_output": answer}}))
"""


def fake_bin(tmp_path, with_uv: bool) -> Path:
    bin_dir = tmp_path / ("bin-uv" if with_uv else "bin")
    bin_dir.mkdir()
    for name, code in {"yt-dlp": FAKE_YTDLP, "claude": FAKE_CLAUDE, **({"uv": FAKE_UV} if with_uv else {})}.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    return bin_dir


def analyse(tmp_path, monkeypatch, system, machine, with_uv=True) -> tuple[dict, list]:
    home = tmp_path / f"{system}-{machine}-{with_uv}"
    home.mkdir()
    log = home / "uv.jsonl"
    monkeypatch.setenv("PATH", str(fake_bin(home, with_uv)))
    monkeypatch.setenv("FAKE_UV_LOG", str(log))
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "machine", lambda: machine)
    server.Helper(home)._run("sincaption", 0)
    data = json.loads((home / "videos" / "sincaption.json").read_text())
    return data, [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)


@pytest.mark.parametrize("system, machine, script", [
    ("Darwin", "arm64", "whisper_cli.py"),
    ("Darwin", "x86_64", "faster_whisper_cli.py"),
    ("Linux", "x86_64", "faster_whisper_cli.py"),
    ("Linux", "aarch64", "faster_whisper_cli.py"),
])
def test_engine_of_the_machine(tmp_path, monkeypatch, system, machine, script):
    # Case 1 · no Spanish captions on this machine → its engine transcribes the audio, the flag quotes its words
    data, runs = analyse(tmp_path, monkeypatch, system, machine)
    assert data["status"] == "done", f"FAIL S21 A2 · {system} {machine}: {data['status']} ({data['stop_reason']})"
    scripts = [Path(a).name for r in runs for a in r if a.endswith(".py")]
    assert scripts == [script], f"FAIL S21 A2 · {system} {machine} ran {scripts}, not {script}"
    flags = [f for f in data["flags"] if f["label"] == "ad_hominem"]
    assert flags and flags[0]["quote"] == QUOTE, f"FAIL S21 A2 · {system} {machine}: flags {data['flags']}"


def test_no_engine(tmp_path, monkeypatch):
    # Case 2 · no Spanish captions and no uv → stopped, with the reason that names the doctor
    data, runs = analyse(tmp_path, monkeypatch, "Linux", "x86_64", with_uv=False)
    assert data["status"] == "stopped", f"FAIL S21 A2 · status {data['status']} with no engine"
    assert "no Spanish captions, and no speech engine on this machine: run fact-checker doctor" in data["stop_reason"], \
        f"FAIL S21 A2 · stop reason {data['stop_reason']!r}"
    print("PASS S21 A2 · A video without captions uses the speech engine of the machine")
