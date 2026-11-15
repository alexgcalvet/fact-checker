"""S40 A3 · A key saved from the extension (the helper side)

Story: The provider is `anthropic` and no key is set. On YouTube, the person opens ⚙ and clicks "Claves". A helper page
lists `ANTHROPIC_API_KEY` as "falta". The person pastes the key in a hidden field and saves. The page says "guardada",
never shows the value, the key file is readable only by the person, and the next analysis reads with that key with no
restart.

Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME); the helper home's settings say `provider = "anthropic"`, `screen = false`, and send the Anthropic
API to a fake Messages API on a free local port. The home's `.env` holds only a comment. The helper's HTTP handler
runs in this process on a free local port, never 8765–8769, and the same helper later runs the analysis, as one
running helper does. The video is the invented two-part interview of S23 (fake YouTube, published fact-checks that
find nothing, no voices); failing `claude` and `codex` commands are first on PATH. The key is an invented string. The
extension side is checked in s40-a3-settings-opens-keys.test.ts.
"""
import re
import stat
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

from s23_fakes import FakeMessagesAPI, fail_clis, fake_video
from s38_fakes import free_ports, guard

from fact_checker import server

KEY = "sk-ant-invented-s40-key-0123456789"


def test_key_page(tmp_path, monkeypatch, capsys):
    fake_video(monkeypatch)
    fail_clis(tmp_path, monkeypatch)
    guard(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY")  # restored after the test: the helper sets the key it saves
    api = FakeMessagesAPI()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    (home / "config.toml").write_text(f'provider = "anthropic"\nscreen = false\n[anthropic]\nbase_url = "{api.url}"\n')
    (home / ".env").write_text("# ANTHROPIC_API_KEY=\n")
    port = free_ports()
    base = f"http://127.0.0.1:{port}"
    helper = server.Helper(home)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), server.handler(helper))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def page(method="GET", form=None) -> tuple[int, str]:
        data = urllib.parse.urlencode(form).encode() if form else None
        req = urllib.request.Request(f"{base}/keys", data=data, method=method, headers={"Origin": base} if form else {})
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, res.read().decode()

    def row(text: str, name: str) -> str:
        """The text of the page around the key name, with the tags removed."""
        plain = re.sub(r"<[^>]+>", " ", text)
        return plain[plain.index(name):][:200]

    try:
        # Case 1 · GET /keys → 200, an HTML page that lists ANTHROPIC_API_KEY as "falta", with a hidden field for it
        status, text = page()
        assert status == 200, f"FAIL S40 A3 · /keys answered {status}"
        assert "ANTHROPIC_API_KEY" in text and "falta" in row(text, "ANTHROPIC_API_KEY"), \
            f"FAIL S40 A3 · ANTHROPIC_API_KEY is not listed as falta: {text}"
        assert re.search(r'<input[^>]*type="password"', text), "FAIL S40 A3 · no hidden field for the key"

        # Case 2 · the person saves the key → the page says "guardada" and never holds the value
        status, text = page("POST", {"name": "ANTHROPIC_API_KEY", "value": f"  {KEY}  "})
        assert status == 200, f"FAIL S40 A3 · saving answered {status}"
        assert "guardada" in row(text, "ANTHROPIC_API_KEY"), f"FAIL S40 A3 · the page does not say guardada: {text}"
        assert KEY not in text, "FAIL S40 A3 · the page shows the key"
        assert KEY not in page()[1], "FAIL S40 A3 · the page shows the key on a later visit"

        # Case 3 · the key file holds the key in place of its commented line, and is readable only by the person
        assert (home / ".env").read_text() == f"ANTHROPIC_API_KEY={KEY}\n", "FAIL S40 A3 · the key file"
        assert stat.S_IMODE((home / ".env").stat().st_mode) == 0o600, \
            f"FAIL S40 A3 · the key file mode is {oct(stat.S_IMODE((home / '.env').stat().st_mode))}"

        # Case 4 · the next analysis of the same running helper → every reading sends that key
        helper._run("keys1", 0)
        assert api.requests, "FAIL S40 A3 · the analysis sent no reading"
        sent = {r["headers"].get("x-api-key") for r in api.requests}
        assert sent == {KEY}, f"FAIL S40 A3 · the readings sent other keys: {len(sent)} distinct"

        # Case 5 · a second key replaces the first in the running helper too
        page("POST", {"name": "ANTHROPIC_API_KEY", "value": KEY + "-2"})
        api.requests.clear()
        helper._run("keys2", 0)
        assert {r["headers"].get("x-api-key") for r in api.requests} == {KEY + "-2"}, \
            "FAIL S40 A3 · the running helper kept the old key"
        assert (home / ".env").read_text() == f"ANTHROPIC_API_KEY={KEY}-2\n", "FAIL S40 A3 · the key file after a change"

        # Case 6 · nothing the helper printed holds the key
        out = capsys.readouterr()
        assert KEY not in out.out + out.err, "FAIL S40 A3 · the helper printed the key"
    finally:
        httpd.shutdown()
        httpd.server_close()
        api.stop()
    print("PASS S40 A3 · A key saved from the extension (helper side)")
