"""S30 A3 (helper part) · The player says "signals, not verdicts" and what an analysis spends

Story: A person with a Spanish browser sees a card with "90%" confidence, and the foot of the side panel reads "Señales
automáticas, no veredictos" ("Automatic signals, not verdicts" in English). On a video not analysed yet, under
"Analizar este vídeo" a line reads "Usa tu suscripción de Claude: un vídeo de 1 h gasta una parte notable de tu
límite"; with Codex it names ChatGPT; with an API provider it reads "Se cobra en tu cuenta de API".

Setup: a temporary helper home whose `config.toml` changes per case, the helper's own HTTP server on a free port, and
failing fake `claude` and `codex` commands on PATH. The line itself is checked in s30-a3-signals-and-spend.test.ts;
here the helper names the provider that reads the parts, which picks the line.
"""
from s23_fakes import fail_clis
from s24_fakes import request, start_helper


def test_provider(tmp_path, monkeypatch):
    cli_log = fail_clis(tmp_path, monkeypatch)
    home = tmp_path / "helper"
    home.mkdir()
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.delenv("FACT_CHECK_PROVIDER", raising=False)
    port, stop = start_helper(home)
    try:
        # Case 1 · no settings → claude
        assert request(port, "/provider") == (200, {"provider": "claude"}), f"FAIL S30 A3 · {request(port, '/provider')}"

        # Case 2 · provider = "codex" → codex
        (home / "config.toml").write_text('provider = "codex"\n')
        assert request(port, "/provider") == (200, {"provider": "codex"})

        # Case 3 · the parts on their own API provider → that provider, not the default one
        (home / "config.toml").write_text('provider = "claude"\n\n[roles.parts]\nprovider = "chat"\nmodel = "m"\n')
        assert request(port, "/provider") == (200, {"provider": "chat"})

        # Case 4 · no `claude` or `codex` command was called
        assert not cli_log.exists() or cli_log.read_text() == ""
    finally:
        stop()
    print("PASS S30 A3 · The helper names the provider that reads the parts")
