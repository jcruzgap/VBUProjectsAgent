"""Typed CRUD repositories for each SQLite table."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, *, id: str, name: str, client: str = "", delivery_manager: str = "",
               progress_type: str, current_health: Optional[str] = None) -> None:
        now = _now()
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO projects (id, name, client, delivery_manager, progress_type,
                                      current_health, last_updated_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    client=excluded.client,
                    delivery_manager=excluded.delivery_manager,
                    progress_type=excluded.progress_type,
                    current_health=excluded.current_health,
                    last_updated_at=excluded.last_updated_at
            """, (id, name, client, delivery_manager, progress_type, current_health, now, now))

    def get(self, project_id: str) -> Optional[dict]:
        row = self.db.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM projects ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def update_health(self, project_id: str, health: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET current_health=?, last_updated_at=? WHERE id=?",
                (health, _now(), project_id),
            )


class SnapshotRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, *, run_id: str, project_id: str, mode: str,
               claude_provider: Optional[str], source_files: list[str],
               snapshot_path: str, context_hashes: dict[str, str],
               change_summary: Optional[str]) -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO project_snapshots
                (run_id, project_id, created_at, mode, claude_provider, source_files,
                 snapshot_path, context_hashes, change_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, project_id, _now(), mode, claude_provider,
                  json.dumps(source_files), snapshot_path,
                  json.dumps(context_hashes), change_summary))

    def get_latest(self, project_id: str) -> Optional[dict]:
        row = self.db.execute("""
            SELECT * FROM project_snapshots
            WHERE project_id=?
            ORDER BY created_at DESC LIMIT 1
        """, (project_id,)).fetchone()
        return dict(row) if row else None

    def get_by_run_id(self, run_id: str) -> Optional[dict]:
        row = self.db.execute(
            "SELECT * FROM project_snapshots WHERE run_id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_for_project(self, project_id: str, limit: int = 50) -> list[dict]:
        rows = self.db.execute("""
            SELECT * FROM project_snapshots
            WHERE project_id=?
            ORDER BY created_at DESC LIMIT ?
        """, (project_id, limit)).fetchall()
        return [dict(r) for r in rows]


class MetricsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, *, run_id: str, project_id: str, overall_percent: float,
               active_stage: Optional[str], health: str,
               velocity_per_day: Optional[float], forecast_date: Optional[str],
               forecast_conf: Optional[float], monthly_revenue: float = 0.0,
               revenue_at_risk: float = 0.0, raw_counts: Optional[dict] = None) -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO project_metrics
                (run_id, project_id, measured_at, overall_percent, active_stage,
                 health, velocity_per_day, forecast_date, forecast_conf,
                 monthly_revenue, revenue_at_risk, raw_counts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, project_id, _now(), overall_percent, active_stage,
                  health, velocity_per_day, forecast_date, forecast_conf,
                  monthly_revenue, revenue_at_risk,
                  json.dumps(raw_counts) if raw_counts else None))

    def get_history(self, project_id: str, metric: str = "overall_percent",
                    since: Optional[str] = None, limit: int = 90) -> list[dict]:
        sql = """
            SELECT measured_at, overall_percent, health, velocity_per_day,
                   forecast_date, forecast_conf, monthly_revenue, revenue_at_risk
            FROM project_metrics
            WHERE project_id=?
        """
        params: list[Any] = [project_id]
        if since:
            sql += " AND measured_at >= ?"
            params.append(since)
        sql += " ORDER BY measured_at ASC LIMIT ?"
        params.append(limit)
        rows = self.db.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def get_latest(self, project_id: str) -> Optional[dict]:
        row = self.db.execute("""
            SELECT * FROM project_metrics
            WHERE project_id=?
            ORDER BY measured_at DESC LIMIT 1
        """, (project_id,)).fetchone()
        return dict(row) if row else None


class MilestoneRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, *, run_id: str, project_id: str, milestone_id: str,
               name: str, target_date: Optional[str], forecast_date: Optional[str],
               percent_complete: float, state: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO milestone_snapshots
                (run_id, project_id, milestone_id, name, target_date, forecast_date,
                 percent_complete, state, measured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, project_id, milestone_id, name, target_date, forecast_date,
                  percent_complete, state, _now()))

    def get_history(self, project_id: str, milestone_id: str, limit: int = 60) -> list[dict]:
        rows = self.db.execute("""
            SELECT * FROM milestone_snapshots
            WHERE project_id=? AND milestone_id=?
            ORDER BY measured_at ASC LIMIT ?
        """, (project_id, milestone_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_latest_all(self, project_id: str) -> list[dict]:
        rows = self.db.execute("""
            SELECT ms.*
            FROM milestone_snapshots ms
            INNER JOIN (
                SELECT milestone_id, MAX(measured_at) AS max_at
                FROM milestone_snapshots WHERE project_id=?
                GROUP BY milestone_id
            ) latest ON ms.milestone_id=latest.milestone_id
                      AND ms.measured_at=latest.max_at
            WHERE ms.project_id=?
            ORDER BY ms.milestone_id
        """, (project_id, project_id)).fetchall()
        return [dict(r) for r in rows]


class RiskRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, *, id: str, project_id: str, description: str,
               severity: str, status: str, owner: str = "",
               opened_at: str, last_seen_at: Optional[str] = None,
               closed_at: Optional[str] = None) -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO risks
                (id, project_id, description, severity, status, owner,
                 opened_at, last_seen_at, closed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    description=excluded.description,
                    severity=excluded.severity,
                    status=excluded.status,
                    owner=excluded.owner,
                    last_seen_at=excluded.last_seen_at,
                    closed_at=excluded.closed_at
            """, (id, project_id, description, severity, status, owner,
                  opened_at, last_seen_at or _now(), closed_at))

    def get_open(self, project_id: str) -> list[dict]:
        rows = self.db.execute("""
            SELECT * FROM risks
            WHERE project_id=? AND status != 'closed'
            ORDER BY severity DESC, opened_at ASC
        """, (project_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_all(self, project_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM risks WHERE project_id=? ORDER BY opened_at",
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


class DecisionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, *, id: str, project_id: str, decided_at: str,
               decision: str, rationale: str = "", decided_by: str = "") -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO decisions
                (id, project_id, decided_at, decision, rationale, decided_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    decision=excluded.decision,
                    rationale=excluded.rationale,
                    decided_by=excluded.decided_by
            """, (id, project_id, decided_at, decision, rationale, decided_by))

    def get_all(self, project_id: str, limit: int = 50) -> list[dict]:
        rows = self.db.execute("""
            SELECT * FROM decisions WHERE project_id=?
            ORDER BY decided_at DESC LIMIT ?
        """, (project_id, limit)).fetchall()
        return [dict(r) for r in rows]


class ArtifactRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, *, project_id: Optional[str], run_id: Optional[str],
               kind: str, path: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO generated_artifacts
                (project_id, run_id, kind, path, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, run_id, kind, path, _now()))

    def get_latest(self, project_id: str, kind: str) -> Optional[dict]:
        row = self.db.execute("""
            SELECT * FROM generated_artifacts
            WHERE project_id=? AND kind=?
            ORDER BY created_at DESC LIMIT 1
        """, (project_id, kind)).fetchone()
        return dict(row) if row else None


class AdoSyncRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, *, project_id: str, started_at: str) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute("""
                INSERT INTO ado_sync_runs (project_id, started_at)
                VALUES (?, ?)
            """, (project_id, started_at))
            return cur.lastrowid  # type: ignore

    def finish(self, row_id: int, *, status: str,
               item_count: Optional[int] = None,
               error_summary: Optional[str] = None) -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                UPDATE ado_sync_runs
                SET finished_at=?, status=?, item_count=?, error_summary=?
                WHERE id=?
            """, (_now(), status, item_count, error_summary, row_id))
