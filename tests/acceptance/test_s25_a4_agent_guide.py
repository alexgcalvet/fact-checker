"""S25 A4 · One sentence leads any agent through the install, in Spanish and English

Story: The README starts with the sentence to paste into Claude or ChatGPT, in Spanish and English; the extension's
"helper does not answer" notice shows the same sentence in both languages. The agent guide names only commands that
exist, and each message it tells the person has a Spanish and an English text. The person reads the guide and the
README quick start in both languages.

Setup: none. The test reads INSTALL-AGENT.md, README.md, install.sh and the notice texts of the extension. The guide
address comes from the repo address in install.sh. Each `fact-checker` command in a shell block or a code span of the
guide runs with `--help` through the real CLI from src/helper; a `<NAME>` placeholder becomes a sample name.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]
GUIDE = REPO / "INSTALL-AGENT.md"
TEXTS = REPO / "src" / "extension" / "src" / "texts.ts"


def guide_url() -> str:
    assert (REPO / "install.sh").exists(), "FAIL S25 A4 · no install.sh, so no guide address"
    found = re.search(r'FACT_CHECKER_REPO:-([^}"]+)', (REPO / "install.sh").read_text())
    assert found, "FAIL S25 A4 · install.sh has no FACT_CHECKER_REPO default"
    return f"{found.group(1)}/blob/main/INSTALL-AGENT.md"


def test_agent_guide():
    url = guide_url()
    spanish, english = f"Instala fact-checker siguiendo {url}", f"Install fact-checker by following {url}"

    # Case 1 · the README → its first lines link the guide and give the sentence in Spanish and English
    readme = (REPO / "README.md").read_text()
    head = "\n".join(readme.splitlines()[:12])
    assert "INSTALL-AGENT.md" in head, f"FAIL S25 A4 · the README does not start with the guide: {head}"
    assert spanish in readme and english in readme, "FAIL S25 A4 · the README lacks the sentence in a language"

    # Case 2 · the "helper does not answer" notice → the same sentence in Spanish and English
    texts = TEXTS.read_text()
    assert "export const TEXTS" in texts, "FAIL S25 A4 · no exported TEXTS object"
    assert "INSTALL-AGENT.md" in texts and "Instala fact-checker siguiendo" in texts and \
        "Install fact-checker by following" in texts, "FAIL S25 A4 · the notice lacks the sentence in a language"
    assert url in texts, f"FAIL S25 A4 · the notice does not name {url}"

    # Case 3 · each message for the person in the guide → a Spanish text, then an English text
    lines = GUIDE.read_text().splitlines()
    es = [i for i, x in enumerate(lines) if x.startswith("> **ES:**")]
    en = [i for i, x in enumerate(lines) if x.startswith("> **EN:**")]
    assert len(es) >= 4, f"FAIL S25 A4 · {len(es)} messages for the person"
    assert [i + 1 for i in es] == en, "FAIL S25 A4 · a message lacks its English text right after the Spanish one"

    # Case 4 · each fact-checker command the guide names → it exists (--help exits 0); install.sh exists
    text = GUIDE.read_text()
    blocks = "\n".join(re.findall(r"```sh\n(.*?)```", text, re.S))
    spans = re.findall(r"`([^`\n]+)`", re.sub(r"```.*?```", "", text, flags=re.S))
    commands = {re.sub(r"<[A-Z_]+>", "HF_TOKEN", c.strip()).split(" #")[0].split(" &&")[0].strip()
                for c in [*blocks.splitlines(), *spans] if c.strip().startswith("fact-checker ")}
    assert {"fact-checker doctor --json", "fact-checker key set HF_TOKEN", "fact-checker setup"} <= commands, \
        f"FAIL S25 A4 · the guide misses a command: {sorted(commands)}"
    for command in sorted(commands):
        done = subprocess.run([sys.executable, "-m", "fact_checker.cli", *command.split()[1:], "--help"],
                              cwd=REPO / "src" / "helper", capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, f"FAIL S25 A4 · `{command}` does not exist: {done.stderr[-300:]}"
    assert "./install.sh" in text and (REPO / "install.sh").exists(), "FAIL S25 A4 · the guide names no installer"
    print("PASS S25 A4 · One sentence leads any agent through the install, in Spanish and English")
