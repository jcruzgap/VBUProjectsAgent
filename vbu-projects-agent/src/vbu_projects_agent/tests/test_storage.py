"""Tests for SQLite storage layer — DB init, repositories, snapshots, rollback."""
import pytest
from pathlib import Path

from ..storage.repositories import (
    ProjectRepository, SnapshotRepository, MetricsRepository,
    RiskRepository, DecisionRepository,
)
from ..storage.snapshots import SnapshotManager


class TestDatabase:
    def test_db_initializes(self, db):
        # Should not raise; tables created
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        assert "projects" in tables
        assert "project_snapshots" in tables
        assert "project_metrics" in tables
        assert "risks" in tables

    def test_transaction_rollback_on_error(self, db):
        with pytest.raises(Exception):
            with db.transaction() as conn:
                conn.execute("INSERT INTO projects (id, name, progress_type, created_at) VALUES (?, ?, ?, ?)",
                             ("p1", "P1", "manual_kpi", "2026-01-01"))
                raise RuntimeError("force rollback")
        # Row should not exist
        row = db.execute("SELECT id FROM projects WHERE id='p1'").fetchone()
        assert row is None


class TestProjectRepository:
    def test_upsert_and_get(self, db):
        repo = ProjectRepository(db)
        repo.upsert(id="alpha", name="Alpha", client="Client A", progress_type="test_case_milestones")
        row = repo.get("alpha")
        assert row is not None
        assert row["name"] == "Alpha"

    def test_upsert_updates_existing(self, db):
        repo = ProjectRepository(db)
        repo.upsert(id="alpha", name="Alpha", progress_type="test_case_milestones")
        repo.upsert(id="alpha", name="Alpha Updated", progress_type="test_case_milestones")
        row = repo.get("alpha")
        assert row["name"] == "Alpha Updated"

    def test_list_all(self, db):
        repo = ProjectRepository(db)
        repo.upsert(id="alpha", name="Alpha", progress_type="manual_kpi")
        repo.upsert(id="beta", name="Beta", progress_type="staged_tags")
        projects = repo.list_all()
        ids = [p["id"] for p in projects]
        assert "alpha" in ids
        assert "beta" in ids

    def test_update_health(self, db):
        repo = ProjectRepository(db)
        repo.upsert(id="alpha", name="Alpha", progress_type="manual_kpi")
        repo.update_health("alpha", "green")
        row = repo.get("alpha")
        assert row["current_health"] == "green"


class TestMetricsRepository:
    def _setup_project(self, db, project_id="alpha"):
        ProjectRepository(db).upsert(id=project_id, name="Alpha", progress_type="manual_kpi")

    def test_insert_and_get_latest(self, db):
        self._setup_project(db)
        snap_repo = SnapshotRepository(db)
        snap_repo.insert(
            run_id="run-001", project_id="alpha", mode="sync",
            claude_provider=None, source_files=[], snapshot_path="/tmp/snap",
            context_hashes={}, change_summary=None,
        )
        metrics_repo = MetricsRepository(db)
        metrics_repo.insert(
            run_id="run-001", project_id="alpha",
            overall_percent=0.78, active_stage="alpha",
            health="yellow", velocity_per_day=2.0,
            forecast_date="2026-07-12", forecast_conf=0.8,
        )
        latest = metrics_repo.get_latest("alpha")
        assert latest is not None
        assert abs(float(latest["overall_percent"]) - 0.78) < 0.01

    def test_history_is_ordered(self, db):
        self._setup_project(db)
        snap_repo = SnapshotRepository(db)
        for i, run_id in enumerate(["run-001", "run-002", "run-003"]):
            snap_repo.insert(
                run_id=run_id, project_id="alpha", mode="sync",
                claude_provider=None, source_files=[], snapshot_path=f"/tmp/snap/{run_id}",
                context_hashes={}, change_summary=None,
            )
            MetricsRepository(db).insert(
                run_id=run_id, project_id="alpha",
                overall_percent=0.5 + i * 0.1, active_stage=None,
                health="yellow", velocity_per_day=None, forecast_date=None, forecast_conf=None,
            )
        history = MetricsRepository(db).get_history("alpha")
        percents = [r["overall_percent"] for r in history]
        assert percents == sorted(percents)


class TestSnapshotManager:
    def test_create_and_list(self, tmp_dir: Path):
        snap_mgr = SnapshotManager(tmp_dir / "snapshots")
        ctx_dir = tmp_dir / "context"
        ctx_dir.mkdir()
        (ctx_dir / "current_status.md").write_text("# Status\n\nAll good.")
        run_id = snap_mgr.make_run_id(["standup.md"])
        snap_path = snap_mgr.create_snapshot(
            project_id="alpha", context_dir=ctx_dir,
            run_id=run_id, mode="update", source_files=["standup.md"],
        )
        assert snap_path.exists()
        assert (snap_path / "meta.json").exists()
        snaps = snap_mgr.list_snapshots("alpha")
        assert run_id in snaps

    def test_rollback_restores_files(self, tmp_dir: Path):
        snap_mgr = SnapshotManager(tmp_dir / "snapshots")
        ctx_dir = tmp_dir / "context"
        ctx_dir.mkdir()
        (ctx_dir / "current_status.md").write_text("# Status\n\nOriginal content.")

        run_id = snap_mgr.make_run_id(["file.md"])
        snap_mgr.create_snapshot("alpha", ctx_dir, run_id, "update", ["file.md"])

        # Modify context
        (ctx_dir / "current_status.md").write_text("# Status\n\nModified content.")
        assert "Modified" in (ctx_dir / "current_status.md").read_text()

        # Restore
        snap_mgr.restore_snapshot("alpha", run_id, ctx_dir)
        assert "Original" in (ctx_dir / "current_status.md").read_text()

    def test_get_latest_snapshot(self, tmp_dir: Path):
        snap_mgr = SnapshotManager(tmp_dir / "snapshots")
        ctx_dir = tmp_dir / "context"
        ctx_dir.mkdir()
        run_id_1 = snap_mgr.make_run_id(["a.md"])
        snap_mgr.create_snapshot("alpha", ctx_dir, run_id_1, "update", ["a.md"])
        latest = snap_mgr.get_latest_snapshot_path("alpha")
        assert latest is not None
