"""S25 A1 · One script installs everything, and a second run changes nothing

Story: On a fresh macOS or Linux account with Claude Code logged in and no uv, yt-dlp, ffmpeg or helper, a person runs
`./install.sh` from the repo. It installs uv with the official installer, yt-dlp, an ffmpeg from a Python wheel (no
Homebrew), and the helper, runs `fact-checker setup`, and ends with the ready extension folder, such as
`~/.fact-checker/extension`, which holds a built extension with no Node.js. A second run prints "already there" for uv,
yt-dlp, ffmpeg and the helper, downloads and installs nothing, and leaves every file the same.

Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME). PATH holds a folder with only the system
commands the script needs (sh, dirname, cp, chmod, mkdir) and a folder of fakes: `curl` answers the uv installer URL
with a script that puts a fake `uv` in ~/.local/bin; the fake `uv` writes each call to a log, makes `yt-dlp` and the
helper's `fact-checker` command on `tool install` (the helper command runs the real CLI from src/helper), and answers
the imageio-ffmpeg query with a fake ffmpeg file. `claude` is logged in and fails any reading; `codex` fails every call;
`launchctl`, `systemctl`, `brew` and `sudo` only log; `chromium` exists. The last case installs the helper package for real with
`uv tool install` into temporary tool folders. FACT_CHECKER_PORT moves the helper's ports to a free one, away from the
person's helper on 8765–8769.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]
HELPER_SRC = REPO / "src" / "helper"
REAL_HOME = Path.home()

FAKE_UV = """\
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(json.dumps(["uv", *args]) + "\\n")
bin_dir = os.path.join(os.environ["HOME"], ".local", "bin")
def make(name, text):
    path = os.path.join(bin_dir, name)
    open(path, "w").write(text)
    os.chmod(path, 0o755)
if args[:3] == ["tool", "dir", "--bin"]:
    print(bin_dir)
elif args[:2] == ["tool", "install"] and args[-1] == "yt-dlp":
    make("yt-dlp", "#!/bin/sh\\n")
elif args[:2] == ["tool", "install"]:
    make("fact-checker", f"#!/bin/sh\\nPYTHONPATH={os.environ['HELPER_SRC']} exec {sys.executable} -m fact_checker.cli \\"$@\\"\\n")
elif args[:1] == ["run"] and "imageio-ffmpeg" in args:
    print(os.environ["FAKE_FFMPEG"])
"""
FAKE_CURL = """\
import json, os, sys
open(os.environ["FAKE_LOG"], "a").write(json.dumps(["curl", *sys.argv[1:]]) + "\\n")
if sys.argv[-1] == "https://astral.sh/uv/install.sh":
    print('mkdir -p "$HOME/.local/bin" && cp "$FAKE_UV" "$HOME/.local/bin/uv" && chmod 755 "$HOME/.local/bin/uv"')
"""
FAKE_CLAUDE = """\
import json, sys
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True}))
else:
    sys.exit(1)
"""
FAKE_RECORDER = """\
import json, os, sys
open(os.environ["FAKE_LOG"], "a").write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + "\\n")
"""


def script(path: Path, code: str) -> None:
    path.write_text(f"#!{sys.executable}\n{code}")
    path.chmod(0o755)


def machine(tmp_path: Path) -> dict:
    fakes, system = tmp_path / "fakes", tmp_path / "system"
    fakes.mkdir()
    system.mkdir()
    for name in ("sh", "dirname", "cp", "chmod", "mkdir"):
        (system / name).symlink_to(shutil.which(name))
    for name, code in {"curl": FAKE_CURL, "claude": FAKE_CLAUDE, "codex": "import sys\nsys.exit(1)\n",
                       "launchctl": FAKE_RECORDER, "systemctl": FAKE_RECORDER, "brew": FAKE_RECORDER,
                       "sudo": FAKE_RECORDER, "chromium": ""}.items():
        script(fakes / name, code)
    script(tmp_path / "uv", FAKE_UV)
    (tmp_path / "ffmpeg-from-wheel").write_text("#!/bin/sh\n")
    home = tmp_path / "home"
    home.mkdir()
    return {"PATH": f"{fakes}{os.pathsep}{system}", "HOME": str(home), "FACT_CHECKER_HOME": str(home / ".fact-checker"),
            "FAKE_LOG": str(tmp_path / "calls.jsonl"), "FAKE_UV": str(tmp_path / "uv"),
            "FAKE_FFMPEG": str(tmp_path / "ffmpeg-from-wheel"), "HELPER_SRC": str(HELPER_SRC),
            "FACT_CHECKER_PORT": str(free_port())}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def install(env: dict) -> tuple[int, list[str], list[list[str]]]:
    log = Path(env["FAKE_LOG"])
    log.unlink(missing_ok=True)
    done = subprocess.run(["sh", str(REPO / "install.sh")], env=env, capture_output=True, text=True, timeout=120)
    calls = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    return done.returncode, (done.stdout + done.stderr).splitlines(), calls


def files(home: Path) -> dict:
    return {str(p.relative_to(home)): p.read_bytes() for p in sorted(home.rglob("*")) if p.is_file()}


def test_installer_twice(tmp_path):
    env = machine(tmp_path)
    home = Path(env["HOME"])
    bin_dir = home / ".local" / "bin"
    real = (REAL_HOME / "Library" / "LaunchAgents" / "com.fact-checker.helper.plist",
            REAL_HOME / ".config" / "systemd" / "user" / "fact-checker.service")
    before = [p.exists() and p.read_bytes() for p in real]

    # Case 1 · a fresh account → uv from its official installer, yt-dlp, ffmpeg from the wheel, the helper, setup
    code, out, calls = install(env)
    assert code == 0, f"FAIL S25 A1 · install.sh exit {code}: {out[-15:]}"
    assert ["curl", "-LsSf", "https://astral.sh/uv/install.sh"] in calls, f"FAIL S25 A1 · no uv installer: {calls}"
    assert ["uv", "tool", "install", "yt-dlp"] in calls, f"FAIL S25 A1 · no yt-dlp: {calls}"
    assert ["uv", "tool", "install", str(HELPER_SRC)] in calls, f"FAIL S25 A1 · no helper: {calls}"
    for name in ("uv", "yt-dlp", "ffmpeg", "fact-checker"):
        assert (bin_dir / name).exists(), f"FAIL S25 A1 · {name} is not in {bin_dir}"
    assert (bin_dir / "ffmpeg").read_bytes() == Path(env["FAKE_FFMPEG"]).read_bytes(), "FAIL S25 A1 · ffmpeg"
    assert not any(c[0] in ("brew", "sudo") for c in calls), f"FAIL S25 A1 · Homebrew or sudo: {calls}"
    assert any(c[0] in ("launchctl", "systemctl") for c in calls), f"FAIL S25 A1 · setup did not start the helper"

    # Case 2 · the end of the run → the extension folder, a built extension that needs no Node.js
    extension = home / ".fact-checker" / "extension"
    manifest = json.loads((extension / "manifest.json").read_text())
    for script_path in (manifest["background"]["service_worker"], *manifest["content_scripts"][0]["js"],
                        *manifest["content_scripts"][1]["js"]):
        assert (extension / script_path).stat().st_size > 0, f"FAIL S25 A1 · the extension lacks {script_path}"
    assert any(str(extension) in line for line in out[-5:]), f"FAIL S25 A1 · the end names no folder: {out[-5:]}"

    # Case 3 · a second run → "already there" for each tool, no download, no install, every file the same
    first = files(home)
    code, out, calls = install(env)
    assert code == 0, f"FAIL S25 A1 · second run exit {code}: {out[-15:]}"
    for name in ("uv", "yt-dlp", "ffmpeg", "helper"):
        assert f"{name}: already there" in out, f"FAIL S25 A1 · second run, {name}: {out}"
    installs = [c for c in calls if c[0] == "curl" or c[1:3] == ["tool", "install"] or c[1:2] == ["run"]]
    assert installs == [], f"FAIL S25 A1 · the second run installed: {installs}"
    assert files(home) == first, "FAIL S25 A1 · the second run changed files"
    assert [p.exists() and p.read_bytes() for p in real] == before, "FAIL S25 A1 · setup wrote into the real home"


def test_package_holds_the_extension(tmp_path):
    # Case 4 · uv tool install of the helper → its package holds the built extension: manifest and scripts
    uv = shutil.which("uv")
    assert uv, "FAIL S25 A1 · uv is not installed on this machine"
    cache = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True).stdout.strip()
    env = os.environ | {"UV_CACHE_DIR": cache, "UV_TOOL_DIR": str(tmp_path / "tools"),
                        "UV_TOOL_BIN_DIR": str(tmp_path / "bin"), "HOME": str(tmp_path)}
    done = subprocess.run([uv, "tool", "install", "--quiet", str(HELPER_SRC)], env=env, capture_output=True, text=True)
    assert done.returncode == 0, f"FAIL S25 A1 · uv tool install: {done.stderr[-400:]}"
    for name in ("manifest.json", "dist/content.js", "dist/sw.js", "dist/guard.js", "icons/icon128.png"):
        assert list((tmp_path / "tools").rglob(f"fact_checker/extension/{name}")), f"FAIL S25 A1 · package lacks {name}"
    print("PASS S25 A1 · One script installs everything, and a second run changes nothing")
