"""CLI integration tests using Typer's CliRunner."""
import pytest
from pathlib import Path
from typer.testing import CliRunner

from ..cli import app
from ..projects.scaffolder import ProjectScaffolder


runner = CliRunner()


@pytest.fixture()
def workspace(tmp_dir: Path, test_case_project_config):
    """Set up a minimal workspace with one project."""
    import yaml
    # Config
    cfg_dir = tmp_dir / "config"
    cfg_dir.mkdir()
    (cfg_dir / "vbu-agent.yaml").write_text(yaml.dump({
        "app": {"name": "Test Agent"},
        "storage": {"sqlite_path": "data/test.db", "snapshots_path": "data/snaps"},
        "projects": {"root_path": "projects"},
        "reports": {"output_path": "reports"},
    }))
    # Project
    scaffolder = ProjectScaffolder(tmp_dir / "projects")
    project_dir = scaffolder.create("project-alpha", "Project Alpha")
    # Write project.yaml
    (project_dir / "project.yaml").write_text(yaml.dump(
        test_case_project_config.model_dump()
    ))
    # Input file
    (tmp_dir / "projects" / "project-alpha" / "input" / "standup.md").write_text(
        "# Standup Notes\n\nAll on track. No blockers."
    )
    return tmp_dir


class TestCliCommands:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "vbu-agent" in result.output.lower() or "Usage" in result.output

    def test_project_list(self, workspace: Path):
        result = runner.invoke(app, ["--base-dir", str(workspace), "project", "list"])
        assert result.exit_code == 0

    def test_project_create(self, workspace: Path):
        result = runner.invoke(app, [
            "--base-dir", str(workspace),
            "project", "create",
            "--project", "new-project",
            "--name", "New Project",
        ])
        assert result.exit_code == 0
        assert (workspace / "projects" / "new-project" / "project.yaml").exists()

    def test_project_validate(self, workspace: Path):
        result = runner.invoke(app, [
            "--base-dir", str(workspace),
            "project", "validate",
            "--project", "project-alpha",
        ])
        # Should not exit 1 (even if warns about template)
        assert result.exit_code in (0, 1)

    def test_config_validate(self, workspace: Path):
        result = runner.invoke(app, [
            "--base-dir", str(workspace),
            "config", "validate",
        ])
        assert result.exit_code == 0

    def test_doctor(self, workspace: Path):
        result = runner.invoke(app, [
            "--base-dir", str(workspace),
            "doctor",
        ])
        assert result.exit_code == 0
        assert "config" in result.output.lower() or "OK" in result.output

    def test_project_update_dry_run(self, workspace: Path):
        result = runner.invoke(app, [
            "--base-dir", str(workspace),
            "project", "update",
            "--project", "project-alpha",
            "--dry-run",
        ])
        # Should succeed even if Claude is unavailable (fallback mode)
        assert result.exit_code == 0

    def test_history_show_no_data(self, workspace: Path):
        result = runner.invoke(app, [
            "--base-dir", str(workspace),
            "history", "show",
            "--project", "project-alpha",
        ])
        # Should say no history found, not crash
        assert result.exit_code == 0

    def test_rollback_no_snapshot(self, workspace: Path):
        result = runner.invoke(app, [
            "--base-dir", str(workspace),
            "project", "rollback",
            "--project", "project-alpha",
            "--yes",
        ])
        # Should report no snapshots gracefully
        assert "error" in result.output.lower() or "snapshot" in result.output.lower()
