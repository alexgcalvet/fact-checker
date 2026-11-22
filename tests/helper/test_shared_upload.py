# S4 A3 · The owner's upload replaces the stored analysis
#
# Story: The owner runs `fact-checker shared upload <video> es` for a video already approved, read by the same model.
# The collector keeps the new upload, with its summary and prompts, in place of the old one. A stranger's upload of
# that video by the same model is still refused. (The collector's side: tests/collector/owner-replaces.test.ts.)
#
# Setup: a temporary helper home whose `config.toml` sets `feedback_url` to a fake collector on a free local port,
# FEEDBACK_ADMIN_TOKEN set to the fake's admin token, and the invented whole analysis of
# tests/support/shared_analysis_fakes.py saved as a local flag file. A second flag file that stops before the end.
import json
import sys

from fact_checker import cli
from fake_servers import FakeCollector, TOKEN
from shared_analysis_fakes import ANALYSIS, SHARED_VIDEO


def run(monkeypatch, capsys, *args) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["fact-checker", *args])
    try:
        cli.main()
        code = 0
    except SystemExit as end:
        code = end.code or 0
    return code, capsys.readouterr().out


def test_shared_upload(tmp_path, monkeypatch, capsys):
    home = tmp_path / "helper"
    (home / "videos").mkdir(parents=True)
    monkeypatch.setenv("FACT_CHECKER_HOME", str(home))
    monkeypatch.setenv("FEEDBACK_ADMIN_TOKEN", TOKEN)
    collector = FakeCollector()
    (home / "config.toml").write_text(f'feedback_url = "{collector.url}"\n')
    (home / "videos" / f"{SHARED_VIDEO}.json").write_text(json.dumps(ANALYSIS))
    half = ANALYSIS | {"video_id": "halfway1", "status": "stopped", "analysed_until": 10.0}
    (home / "videos" / "halfway1.json").write_text(json.dumps(half))
    try:
        # Case 1 · `shared upload <video> es` → one PUT with the admin token, the summary of the guest and the prompts
        code, out = run(monkeypatch, capsys, "shared", "upload", SHARED_VIDEO, "es")
        assert code == 0, out
        [put] = collector.puts()
        assert put["path"] == f"/analyses/{SHARED_VIDEO}" and put["query"]["lang"] == ["es"]
        assert put["auth"] == f"Bearer {TOKEN}"
        assert list(put["body"]["analysis"]["summary"]) == ["Invitado"]
        assert put["body"]["prompts"]["version"] == put["body"]["analysis"]["helper_version"]
        assert SHARED_VIDEO in out

        # Case 2 · a local analysis that does not cover the whole video, or none → exit 1, nothing sent
        assert run(monkeypatch, capsys, "shared", "upload", "halfway1", "es")[0] == 1
        assert run(monkeypatch, capsys, "shared", "upload", "unknown1", "es")[0] == 1
        assert len(collector.puts()) == 1
        print("PASS S4 A3 · shared upload sends the local analysis with its summary and prompts")
    finally:
        collector.stop()
