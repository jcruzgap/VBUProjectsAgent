"""Tests for .env auto-loading."""
import os
from pathlib import Path

from ..env import load_env_file


class TestLoadEnvFile:
    def test_loads_var_from_explicit_base_dir(self, tmp_dir: Path, monkeypatch):
        monkeypatch.delenv("VBU_ENV_TEST", raising=False)
        (tmp_dir / ".env").write_text("VBU_ENV_TEST=loaded\n", encoding="utf-8")
        used = load_env_file(tmp_dir)
        assert used == tmp_dir / ".env"
        assert os.environ["VBU_ENV_TEST"] == "loaded"

    def test_does_not_override_existing_var(self, tmp_dir: Path, monkeypatch):
        monkeypatch.setenv("VBU_ENV_TEST", "from-shell")
        (tmp_dir / ".env").write_text("VBU_ENV_TEST=from-file\n", encoding="utf-8")
        load_env_file(tmp_dir)
        assert os.environ["VBU_ENV_TEST"] == "from-shell"

    def test_returns_none_when_no_env_file(self, tmp_dir: Path, monkeypatch):
        # chdir into the isolated tmp tree so the fallback upward search
        # (find_dotenv from cwd) cannot climb into a real repo .env.
        missing = tmp_dir / "no-such-dir"
        missing.mkdir()
        monkeypatch.chdir(missing)
        assert load_env_file(missing) is None
