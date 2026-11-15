"""S25 A3 · A key goes in through a hidden prompt, and doctor answers in JSON

Story: A person with `provider = "anthropic"` runs `fact-checker doctor --json`: an agent reads `"ok": false` and the
check `ANTHROPIC_API_KEY` with state "missing" and its fix, the same as in the
text output. The person runs `fact-checker key set ANTHROPIC_API_KEY` in
a terminal and types an invented key: the screen never shows it, and `~/.fact-checker/.env` gets one
`ANTHROPIC_API_KEY=` line with it, readable only by the person. A second `key set` replaces that line.
`doctor --json` then says "set", and its output never holds the key.

Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME) with `provider = "anthropic"` in config.toml
and the commented keys example as .env. PATH holds only fakes: `claude` and `codex` fail every call; `uv`, `yt-dlp`,
`ffmpeg` and `chromium` exist. Each command runs the real CLI from src/helper in a child process. `key set` runs in a
pseudo-terminal, as in a real terminal window: the test waits for the prompt, types the key and reads every byte the
screen gets. No helper listens on the port.
"""
import json
import os
import pty
import select
import socket
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]
HELPER_SRC = REPO / "src" / "helper"
EXAMPLE = HELPER_SRC / "fact_checker" / "env.example"
FIRST, SECOND = "sk-ant-invented-first-1234", "sk-ant-invented-second-5678"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def machine(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, code in {"claude": "import sys\nsys.exit(1)\n", "codex": "import sys\nsys.exit(1)\n",
                       "uv": "", "yt-dlp": "", "ffmpeg": "", "chromium": ""}.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    home = tmp_path / "helper"
    home.mkdir()
    (home / "config.toml").write_text('provider = "anthropic"\n')
    (home / ".env").write_text(EXAMPLE.read_text())
    (tmp_path / "user").mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "FACT_CHECK_PROVIDER")}
    return env | {"PATH": str(bin_dir), "HOME": str(tmp_path / "user"), "FACT_CHECKER_HOME": str(home),
                  "PYTHONPATH": str(HELPER_SRC)}


def doctor(env: dict) -> tuple[int, str]:
    done = subprocess.run([sys.executable, "-m", "fact_checker.cli", "doctor", "--json", "--port", str(free_port())],
                          env=env, capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout + done.stderr


def key_set(env: dict, name: str, typed: str) -> tuple[int, str]:
    """Runs `key set` in a pseudo-terminal; types the key after the prompt; returns the exit code and the screen."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execve(sys.executable, [sys.executable, "-m", "fact_checker.cli", "key", "set", name], env)
    screen = b""

    def read() -> bytes:
        if not select.select([fd], [], [], 30)[0]:
            return b""
        try:
            return os.read(fd, 1024)
        except OSError:
            return b""
    while name.encode() not in screen:
        chunk = read()
        if not chunk:
            break
        screen += chunk
    os.write(fd, typed.encode() + b"\n")
    while chunk := read():
        screen += chunk
    os.close(fd)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), screen.decode(errors="replace")


def check(report: dict, name: str) -> dict:
    found = [c for c in report["checks"] if c["name"] == name]
    assert len(found) == 1, f"FAIL S25 A3 · one check named {name}: {report['checks']}"
    return found[0]


def test_key_and_doctor_json(tmp_path):
    env = machine(tmp_path)
    dotenv = Path(env["FACT_CHECKER_HOME"]) / ".env"
    example_lines = [x for x in EXAMPLE.read_text().splitlines() if "ANTHROPIC_API_KEY" not in x]

    # Case 1 · doctor --json, no key → "ok": false, the key check "missing" with its fix, each check with its fields
    code, out = doctor(env)
    assert code == 1, f"FAIL S25 A3 · doctor exit {code}: {out}"
    report = json.loads(out)
    assert report["ok"] is False, f"FAIL S25 A3 · {report}"
    key = check(report, "ANTHROPIC_API_KEY")
    assert key["state"] == "missing" and key["ok"] is False, f"FAIL S25 A3 · {key}"
    assert key["fix"] == f"add ANTHROPIC_API_KEY=<key> to {dotenv}", f"FAIL S25 A3 · the fix: {key}"
    assert check(report, "helper")["ok"] is False, f"FAIL S25 A3 · {report}"
    assert all(set(c) == {"name", "state", "fix", "ok"} for c in report["checks"]), f"FAIL S25 A3 · {report}"

    # Case 2 · key set in a terminal → the prompt names the key, the screen never shows it, one line in .env, mode 600
    code, screen = key_set(env, "ANTHROPIC_API_KEY", FIRST)
    assert code == 0, f"FAIL S25 A3 · key set exit {code}: {screen}"
    assert FIRST not in screen, f"FAIL S25 A3 · the screen showed the key: {screen!r}"
    lines = dotenv.read_text().splitlines()
    assert [x for x in lines if "ANTHROPIC_API_KEY" in x] == [f"ANTHROPIC_API_KEY={FIRST}"], f"FAIL S25 A3 · {lines}"
    assert [x for x in lines if "ANTHROPIC_API_KEY" not in x] == example_lines, "FAIL S25 A3 · other lines changed"
    assert dotenv.stat().st_mode & 0o777 == 0o600, f"FAIL S25 A3 · .env mode {oct(dotenv.stat().st_mode & 0o777)}"

    # Case 3 · key set again → the line is replaced, still one line
    code, screen = key_set(env, "ANTHROPIC_API_KEY", SECOND)
    assert code == 0 and SECOND not in screen, f"FAIL S25 A3 · second key set: {code} {screen!r}"
    lines = dotenv.read_text().splitlines()
    assert [x for x in lines if "ANTHROPIC_API_KEY" in x] == [f"ANTHROPIC_API_KEY={SECOND}"], f"FAIL S25 A3 · {lines}"

    # Case 4 · doctor --json with the key → "set", and the output never holds the key
    code, out = doctor(env)
    key = check(json.loads(out), "ANTHROPIC_API_KEY")
    assert key["state"] == "set" and key["ok"] is True, f"FAIL S25 A3 · {key}"
    assert FIRST not in out and SECOND not in out, "FAIL S25 A3 · doctor printed a key"
    print("PASS S25 A3 · A key goes in through a hidden prompt, and doctor answers in JSON")
