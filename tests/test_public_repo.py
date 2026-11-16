"""S30 A4 · The repo names no real person or real video, and has a licence and a privacy notice

Story: A stranger clones the repo. A search of the tracked files for the names and video ids of the real interviews
finds nothing outside the cited public sources of the research notes. `LICENSE` is MIT, 2026 Alex G. Calvet;
`PRIVACY.md` says what the collector keeps and how to ask for deletion; the README lists the third-party software
that the setup downloads.

Setup: none. The test reads the files that git tracks in the working tree (not the history). It skips itself and
the S30 spec, which name the search, and the source links of docs/research/, which cite public articles.
"""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).parents[1]
PATTERN = "feij|sánchez|sanchez|1YlGArMx_N4|mStOFBvToUI|ábalos|koldo|óscar puente|Óscar Puente|évole|Évole"
RESEARCH_SOURCE = re.compile(r"^docs/(archive/[^/]+/)?research/[^:]+:[0-9]+:- \[[^]]*\]\(https?://")


def git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout
    return out.splitlines()


# Case 1 · the content of the tracked files → no real name or real video id
def test_no_real_names_in_tracked_files():
    hits = git("grep", "-niE", PATTERN, "--", ".", ":!tests/test_public_repo.py", ":!docs/archive/*/specs/030-ready-to-publish/")
    hits = [h for h in hits if not RESEARCH_SOURCE.match(h)]
    assert not hits, f"FAIL S30 A4 · real names or video ids in tracked files: {hits}"


# Case 2 · the names of the tracked files → no real name or real video id
def test_no_real_names_in_file_names():
    names = [n for n in git("ls-files") if re.search(PATTERN, n, re.I)]
    assert not names, f"FAIL S30 A4 · real names in file names: {names}"


# Case 3 · LICENSE → MIT, 2026 Alex G. Calvet
def test_license():
    text = (REPO / "LICENSE").read_text()
    assert "MIT License" in text and "Copyright (c) 2026 Alex G. Calvet" in text, \
        "FAIL S30 A4 · LICENSE is missing or not MIT 2026 Alex G. Calvet"


# Case 4 · PRIVACY.md → what is kept, the IP, how to turn sharing off and ask for deletion, no real address
def test_privacy_notice():
    text = (REPO / "PRIVACY.md").read_text()
    for part in ("install id", "IP", "share_marks", "<owner email>"):
        assert part in text, f'FAIL S30 A4 · PRIVACY.md does not mention "{part}"'
    assert re.search("delet", text, re.I), "FAIL S30 A4 · PRIVACY.md does not say how to ask for deletion"
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", text), \
        "FAIL S30 A4 · PRIVACY.md holds a real email address"


# Case 5 · README → a "Third-party software" section with yt-dlp and FFmpeg (LGPL/GPL), and a link to PRIVACY.md
def test_readme_third_party_software():
    readme = (REPO / "README.md").read_text()
    section = re.search(r"^## Third-party software\n(.*?)(?=^## |\Z)", readme, re.M | re.S)
    for part in ("yt-dlp", "FFmpeg", "LGPL", "GPL"):
        assert section and part in section[1], f'FAIL S30 A4 · README "Third-party software" does not name {part}'
    assert "PRIVACY.md" in readme, "FAIL S30 A4 · README does not link PRIVACY.md"
