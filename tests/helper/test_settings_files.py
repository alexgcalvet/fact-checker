"""`fact-checker setup` gives a new person a settings file that names their provider and a commented keys file, and
never overwrites their own."""
import tomllib

from fact_checker.install import settings_files
from fact_checker.server import read_env


def test_new_home_gets_commented_examples(tmp_path):
    settings_files(tmp_path, "codex")
    assert tomllib.loads((tmp_path / "config.toml").read_text()) == {"provider": "codex", "feedback_url": "https://fact-checker-feedback.alexgcalvet7.workers.dev"}
    assert read_env(tmp_path) == {}
    assert "TAVILY_API_KEY" in (tmp_path / ".env").read_text()


def test_existing_files_stay(tmp_path):
    (tmp_path / "config.toml").write_text('provider = "codex"\n')
    (tmp_path / ".env").write_text("HF_TOKEN=x\n")
    settings_files(tmp_path, "claude")
    assert (tmp_path / "config.toml").read_text() == 'provider = "codex"\n'
    assert (tmp_path / ".env").read_text() == "HF_TOKEN=x\n"
