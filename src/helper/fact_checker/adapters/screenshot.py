import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

MAC_APPS = ("Google Chrome.app/Contents/MacOS/Google Chrome", "Chromium.app/Contents/MacOS/Chromium")
COMMANDS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def find_chrome(system: str | None = None) -> str | None:
    """The person's Chrome or Chromium: an app in /Applications or ~/Applications on macOS, else a command on PATH."""
    if (system or platform.system()) == "Darwin":
        for folder in (Path("/Applications"), Path.home() / "Applications"):
            for app in MAC_APPS:
                if (folder / app).exists():
                    return str(folder / app)
    return next((path for name in COMMANDS if (path := shutil.which(name))), None)


def screenshot(html: str, width: int = 1080, height: int = 1350) -> bytes:
    """A PNG of the page at exactly the window size, through the person's headless Chrome."""
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("no Chrome or Chromium: run fact-checker doctor")
    with tempfile.TemporaryDirectory() as tmp:
        page, out = Path(tmp) / "page.html", Path(tmp) / "page.png"
        page.write_text(html)
        subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars", f"--screenshot={out}",
                        f"--window-size={width},{height}", page.as_uri()], capture_output=True, check=True, timeout=60)
        return out.read_bytes()
