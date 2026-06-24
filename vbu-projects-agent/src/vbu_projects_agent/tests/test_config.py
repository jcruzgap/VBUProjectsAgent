"""Tests for global and project config loading and validation."""
import pytest
from pathlib import Path

from ..config.models import GlobalConfig, ClaudeConfig, AppConfig
from ..config.loader import load_global_config, validate_global_config


class TestGlobalConfig:
    def test_defaults(self):
        cfg = GlobalConfig()
        assert cfg.app.name == "VBU-Projects-Agent"
        assert cfg.claude.model == "claude-sonnet-4-6"
        assert cfg.slack.max_words == 180

    def test_invalid_timezone(self):
        with pytest.raises(Exception):
            AppConfig(default_timezone="Not/ATimezone")

    def test_invalid_temperature(self):
        with pytest.raises(Exception):
            ClaudeConfig(temperature=2.0)

    def test_invalid_max_tokens(self):
        with pytest.raises(Exception):
            ClaudeConfig(max_tokens=100)

    def test_invalid_provider_priority_empty(self):
        with pytest.raises(Exception):
            ClaudeConfig(provider_priority=[])

    def test_invalid_provider_priority_duplicate(self):
        with pytest.raises(Exception):
            ClaudeConfig(provider_priority=["api_key", "api_key"])

    def test_load_from_yaml(self, tmp_dir: Path):
        import yaml
        cfg_path = tmp_dir / "config" / "vbu-agent.yaml"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(yaml.dump({
            "app": {"name": "Test Agent", "environment": "local"},
            "claude": {"model": "claude-haiku-4-5-20251001", "temperature": 0.1},
            "slack": {"max_words": 100},
        }))
        cfg = load_global_config(cfg_path, base_dir=tmp_dir)
        assert cfg.app.name == "Test Agent"
        assert cfg.claude.model == "claude-haiku-4-5-20251001"
        assert cfg.slack.max_words == 100

    def test_validate_issues_on_no_provider(self, tmp_dir: Path):
        cfg = GlobalConfig()
        # No api_key set, local_cli disabled
        cfg.claude.local_cli_enabled = False
        issues = validate_global_config(cfg, tmp_dir)
        assert any("provider" in i.lower() or "warning" in i.lower() or "api_key" in i.lower()
                   for i in issues)


class TestProjectConfig:
    def test_load_project_yaml(self, tmp_dir: Path, test_case_project_config):
        import yaml
        from ..config.loader import load_project_config
        project_dir = tmp_dir / "project-alpha"
        project_dir.mkdir()
        yaml_path = project_dir / "project.yaml"
        # Serialize and reload
        data = test_case_project_config.model_dump()
        yaml_path.write_text(yaml.dump(data))
        loaded = load_project_config(project_dir)
        assert loaded.project.id == "project-alpha"
        assert loaded.progress_model.type == "test_case_milestones"

    def test_missing_project_yaml(self, tmp_dir: Path):
        from ..config.loader import load_project_config
        with pytest.raises(FileNotFoundError):
            load_project_config(tmp_dir / "nonexistent")
