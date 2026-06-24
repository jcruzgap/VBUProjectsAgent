"""Tests for context manager — parsing, writing, integrity, surgical edits."""
import pytest
from pathlib import Path

from ..projects.context_manager import ContextManager, _CONTEXT_FILES
from ..projects.scaffolder import ProjectScaffolder
from ..projects.conflicts import ConflictManager


class TestContextManager:
    def test_scaffold_creates_files(self, tmp_dir: Path):
        ctx_dir = tmp_dir / "context"
        mgr = ContextManager(ctx_dir)
        mgr.scaffold_empty_files("Test Project")
        for name in _CONTEXT_FILES:
            assert (ctx_dir / name).exists()

    def test_write_and_load_roundtrip(self, tmp_dir: Path):
        ctx_dir = tmp_dir / "context"
        mgr = ContextManager(ctx_dir)
        mgr.scaffold_empty_files("Test")
        # Write new body
        ctx_file = mgr.update_body("current_status.md", "# Current Status\n\nAll good.", "test")
        # Reload
        loaded = mgr.load_file("current_status.md")
        assert "All good." in loaded.body
        assert loaded.front_matter.get("last_update_source") == "test"
        assert "content_sha256" in loaded.front_matter

    def test_hash_integrity_check_passes(self, tmp_dir: Path):
        ctx_dir = tmp_dir / "context"
        mgr = ContextManager(ctx_dir)
        mgr.scaffold_empty_files("Test")
        mgr.update_body("delivery_notes.md", "# Notes\n\nSome notes.", "test")
        issues = mgr.verify_integrity()
        # After a proper write, no integrity issues
        assert len(issues) == 0

    def test_surgical_edit_preserves_other_files(self, tmp_dir: Path):
        ctx_dir = tmp_dir / "context"
        mgr = ContextManager(ctx_dir)
        mgr.scaffold_empty_files("Test")
        # Write to current_status only
        mgr.update_body("current_status.md", "# Status\n\nUpdated.", "source-a")
        # Other files should still have their original content
        overview = mgr.load_file("overview.md")
        assert "No content yet" in overview.body  # scaffold default

    def test_get_hashes_returns_dict(self, tmp_dir: Path):
        ctx_dir = tmp_dir / "context"
        mgr = ContextManager(ctx_dir)
        mgr.scaffold_empty_files("Test")
        hashes = mgr.get_hashes()
        assert len(hashes) > 0
        for h in hashes.values():
            assert len(h) == 64  # sha256 hex


class TestScaffolder:
    def test_create_project(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        project_dir = scaffolder.create("my-project", "My Project")
        assert project_dir.exists()
        assert (project_dir / "project.yaml").exists()
        assert (project_dir / "context").exists()
        assert (project_dir / "input").exists()

    def test_create_already_exists_raises(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        scaffolder.create("my-project", "My Project")
        with pytest.raises(FileExistsError):
            scaffolder.create("my-project", "My Project")

    def test_create_force_overwrites(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        scaffolder.create("my-project", "My Project")
        scaffolder.create("my-project", "My Project v2", force=True)
        assert (tmp_dir / "projects" / "my-project" / "project.yaml").exists()

    def test_list_projects(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        scaffolder.create("alpha", "Alpha")
        scaffolder.create("beta", "Beta")
        projects = scaffolder.list_projects()
        assert "alpha" in projects
        assert "beta" in projects


class TestConflicts:
    def test_record_and_list_conflicts(self, tmp_dir: Path):
        ctx_dir = tmp_dir / "context"
        ctx_mgr = ContextManager(ctx_dir)
        ctx_mgr.scaffold_empty_files("Test")
        conflict_mgr = ConflictManager(ctx_mgr)

        c = conflict_mgr.record_conflict(
            field="milestones.alpha.target_date",
            existing_value="2026-07-12",
            existing_source="milestones.md",
            incoming_value="2026-07-19",
            incoming_source="standup-notes.md",
            note="Client implied a one-week slip.",
        )

        assert c.id.startswith("CONFLICT-")
        open_ids = conflict_mgr.get_open_conflicts()
        assert c.id in open_ids

    def test_resolve_conflict(self, tmp_dir: Path):
        ctx_dir = tmp_dir / "context"
        ctx_mgr = ContextManager(ctx_dir)
        ctx_mgr.scaffold_empty_files("Test")
        conflict_mgr = ConflictManager(ctx_mgr)

        c = conflict_mgr.record_conflict("field.x", "old", "src-a", "new", "src-b")
        conflict_mgr.mark_resolved(c.id)
        open_ids = conflict_mgr.get_open_conflicts()
        assert c.id not in open_ids
