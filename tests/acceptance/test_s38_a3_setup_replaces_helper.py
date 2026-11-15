"""S38 A3 · Setup replaces an old helper

Story: A fact-checker helper started by hand (for example by an agent) holds port 8765. The person's agent runs
`fact-checker setup`. The old helper stops, the login helper answers on 8765, and doctor's helper line is ok.

Setup: a temporary user home and helper home, and five free local ports in place of 8765–8769 (FACT_CHECKER_PORT), so
"8765" below is the first of them. The system is macOS. PATH holds only fake commands: `claude` logged in, `uv`,
`yt-dlp`, `ffmpeg`, `chromium`, and a `launchctl` that acts as launchd for this test only: `bootstrap` starts the
command of the agent file in the background and keeps its process id, `bootout` stops that process. The old helper
is a real `fact-checker serve --port 8765` started by the test. Another program, a small web server that answers every
request with an HTML 404, holds the last port, and a `serve` of another home holds the fourth: setup leaves both
running. A connection to the real 8765–8769 fails the test. Every process the test starts is stopped at the end.
"""
import os
import plistlib
import signal
import subprocess
import sys

from s38_fakes import Foreign, health, helper_check, listening, machine, run, wait

FAKE_LAUNCHD = """\
import json, os, plistlib, signal, subprocess, sys
pid_file = os.environ["FAKE_LAUNCHD_PID"]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(["launchctl"] + sys.argv[1:]) + "\\n")
if sys.argv[1] == "bootout" and os.path.exists(pid_file):
    try:
        os.kill(int(open(pid_file).read()), signal.SIGTERM)
    except ProcessLookupError:
        pass
    os.remove(pid_file)
if sys.argv[1] == "bootstrap":
    agent = plistlib.load(open(sys.argv[3], "rb"))
    args = agent["ProgramArguments"]
    port = int(args[args.index("--port") + 1]) if "--port" in args else int(os.environ.get("FACT_CHECKER_PORT", 8765))
    if port in range(8761, 8770):
        sys.exit("the test refuses to start a helper on the person's ports")
    log = open(agent["StandardOutPath"], "a")
    env = os.environ | agent["EnvironmentVariables"]
    child = subprocess.Popen(agent["ProgramArguments"], env=env, stdout=log, stderr=log, start_new_session=True)
    open(pid_file, "w").write(str(child.pid))
"""


def stop(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_setup_replaces_helper(tmp_path, monkeypatch, capsys):
    pid_file = tmp_path / "launchd.pid"
    monkeypatch.setenv("FAKE_LAUNCHD_PID", str(pid_file))
    m = machine(tmp_path, monkeypatch, commands={"launchctl": FAKE_LAUNCHD})
    first, home = m["first"], m["home"]
    old = subprocess.Popen([sys.executable, "-m", "fact_checker.cli", "serve", "--port", str(first)], env=os.environ.copy(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    foreign = other = None
    try:
        assert wait(lambda: listening(first)), f"FAIL S38 A3 · the old helper does not listen on {first}"
        foreign = Foreign(first + 4)
        other = subprocess.Popen([sys.executable, "-m", "fact_checker.cli", "serve", "--port", str(first + 3)],
                                 env=os.environ | {"FACT_CHECKER_HOME": str(tmp_path / "other-home")},
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert wait(lambda: listening(first + 3)), "FAIL S38 A3 · the other home's helper does not listen"

        # Case 1 · setup → exit 0, the old helper has stopped, the other program and the other home's helper still answer
        code, out = run(monkeypatch, capsys, "setup")
        assert code == 0, f"FAIL S38 A3 · setup exit {code}: {out}"
        try:
            old.wait(timeout=10)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"FAIL S38 A3 · the old helper {old.pid} still runs")
        assert foreign.answers(), "FAIL S38 A3 · setup stopped another program"
        assert (health(first + 3) or {}).get("home") == str(tmp_path / "other-home"), \
            "FAIL S38 A3 · setup stopped the helper of another home"

        # Case 2 · the login agent runs `serve` with no port, and its helper answers on 8765 with a new process
        agent = plistlib.loads((m["user"] / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist").read_bytes())
        assert agent["ProgramArguments"][-1] == "serve", f"FAIL S38 A3 · {agent['ProgramArguments']}"
        answer = health(first)
        assert answer and answer["app"] == "fact-checker" and answer["home"] == str(home), \
            f"FAIL S38 A3 · no login helper on {first}: {answer}"
        assert answer["pid"] == int(pid_file.read_text()) != old.pid, f"FAIL S38 A3 · not the login helper: {answer}"

        # Case 3 · doctor → the helper line is ok on 8765
        code, check = helper_check(monkeypatch, capsys)
        assert check == {"name": "helper", "state": f"running on port {first}", "fix": "", "ok": True}, \
            f"FAIL S38 A3 · {check}"
    finally:
        if old.poll() is None:
            old.kill()
            old.wait()
        if pid_file.exists():
            stop(int(pid_file.read_text()))
        if foreign:
            foreign.stop()
        if other and other.poll() is None:
            other.kill()
            other.wait()
    print("PASS S38 A3 · Setup replaces an old helper")
