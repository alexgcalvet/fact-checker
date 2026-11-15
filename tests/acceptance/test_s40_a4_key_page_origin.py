"""S40 A4 · The key page refuses other sites

Story: A web page on another site posts a key to the helper's key page, or reaches it through a host name other than
127.0.0.1. The helper answers 403 and the key file does not change.

Setup: a temporary user home (HOME) and helper home (FACT_CHECKER_HOME); the helper home's settings say `provider = "anthropic"`, with a `.env` that holds one invented
ANTHROPIC_API_KEY. The helper's HTTP handler runs in this process on a free local port, never 8765–8769. Each request
is sent by hand with the Host and Origin headers that a browser would send for another site, or for a host name that
points at 127.0.0.1 (DNS rebinding). The keys are invented strings.
"""
import http.client
import stat
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

from s38_fakes import free_ports, guard

from fact_checker import server

OLD = "ANTHROPIC_API_KEY=sk-ant-invented-old\n"
NEW = "sk-ant-invented-new"


def test_key_page_origin(tmp_path, monkeypatch):
    guard(monkeypatch)
    for name in ("FACT_CHECK_PROVIDER", "ANTHROPIC_API_KEY", "HF_TOKEN", "FACT_CHECK_API_KEY"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)  # restored after the test: the helper sets each key it saves
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    (home / "config.toml").write_text('provider = "anthropic"\n')
    keys = home / ".env"
    keys.write_text(OLD)
    keys.chmod(0o600)
    port = free_ports()
    own = f"127.0.0.1:{port}"
    httpd = ThreadingHTTPServer(("127.0.0.1", port), server.handler(server.Helper(home)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def send(method: str, host: str, origin: str | None = None, form: dict | None = None) -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        body = urllib.parse.urlencode(form or {"name": "ANTHROPIC_API_KEY", "value": NEW}) if method == "POST" else None
        headers = {"Host": host} | ({"Origin": origin} if origin is not None else {}) | \
            ({"Content-Type": "application/x-www-form-urlencoded"} if body else {})
        conn.request(method, "/keys", body=body, headers=headers)
        res = conn.getresponse()
        answer = (res.status, res.read().decode(errors="replace"))
        conn.close()
        return answer

    def unchanged(case: str) -> None:
        assert keys.read_text() == OLD, f"FAIL S40 A4 · {case}: the key file changed"
        assert stat.S_IMODE(keys.stat().st_mode) == 0o600, f"FAIL S40 A4 · {case}: the key file mode changed"

    try:
        # Case 1 · another site posts a key (Origin https://evil.example) → 403, the key file does not change
        status, text = send("POST", own, "https://evil.example")
        assert status == 403, f"FAIL S40 A4 · a post from another site answered {status}"
        unchanged("another site")
        assert NEW not in text, "FAIL S40 A4 · the refusal echoes the key"

        # Case 2 · a post with Origin null, or with no Origin → 403, the key file does not change
        for origin in ("null", None):
            assert send("POST", own, origin)[0] == 403, f"FAIL S40 A4 · a post with Origin {origin} was not refused"
            unchanged(f"Origin {origin}")

        # Case 3 · a post through another host name (DNS rebinding), even with a matching Origin → 403, no change
        for host in (f"localhost:{port}", f"evil.example:{port}", "127.0.0.1", f"127.0.0.1:{port + 1}"):
            assert send("POST", host, f"http://{host}")[0] == 403, f"FAIL S40 A4 · a post through {host} was not refused"
            unchanged(f"Host {host}")

        # Case 4 · the page itself read through another host name → 403, no key name listed
        for host in (f"localhost:{port}", f"evil.example:{port}"):
            status, text = send("GET", host)
            assert status == 403 and "ANTHROPIC_API_KEY" not in text, f"FAIL S40 A4 · GET through {host}: {status}"

        # Case 5 · a key name the settings do not need, or a value with a line break → refused, no change
        for form in ({"name": "PATH", "value": "/tmp/evil"}, {"name": "OPENAI_API_KEY", "value": NEW},
                     {"name": "ANTHROPIC_API_KEY", "value": f"{NEW}\nPATH=/tmp/evil"}):
            status, _ = send("POST", own, f"http://{own}", form)
            assert status in (400, 403), f"FAIL S40 A4 · {form['name']} answered {status}"
            unchanged(f"form {form['name']}")

        # Case 6 · the two optional keys, from the helper's own page → saved
        added = OLD
        for name in ("HF_TOKEN", "FACT_CHECK_API_KEY"):
            status, _ = send("POST", own, f"http://{own}", {"name": name, "value": f"{name.lower()}-invented"})
            added += f"{name}={name.lower()}-invented\n"
            assert status == 200 and keys.read_text() == added, f"FAIL S40 A4 · {name} from the helper's own page: {status}"
    finally:
        httpd.shutdown()
        httpd.server_close()
    print("PASS S40 A4 · The key page refuses other sites")
