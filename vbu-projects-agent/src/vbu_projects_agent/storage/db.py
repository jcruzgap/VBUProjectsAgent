"""SQLite database connection and schema migration."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

_SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS projects (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    client            TEXT,
    delivery_manager  TEXT,
    progress_type     TEXT NOT NULL,
    current_health    TEXT,
    last_updated_at   TEXT,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_snapshots (
    run_id            TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL REFERENCES projects(id),
    created_at        TEXT NOT NULL,
    mode              TEXT NOT NULL,
    claude_provider   TEXT,
    source_files      TEXT,
    snapshot_path     TEXT NOT NULL,
    context_hashes    TEXT,
    change_summary    TEXT
);

CREATE TABLE IF NOT EXISTS project_metrics (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL REFERENCES project_snapshots(run_id),
    project_id        TEXT NOT NULL REFERENCES projects(id),
    measured_at       TEXT NOT NULL,
    overall_percent   REAL,
    active_stage      TEXT,
    health            TEXT,
    velocity_per_day  REAL,
    forecast_date     TEXT,
    forecast_conf     REAL,
    monthly_revenue   REAL,
    revenue_at_risk   REAL,
    raw_counts        TEXT
);

CREATE TABLE IF NOT EXISTS milestone_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL REFERENCES project_snapshots(run_id),
    project_id        TEXT NOT NULL REFERENCES projects(id),
    milestone_id      TEXT NOT NULL,
    name              TEXT,
    target_date       TEXT,
    forecast_date     TEXT,
    percent_complete  REAL,
    state             TEXT,
    measured_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risks (
    id                TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL REFERENCES projects(id),
    description       TEXT,
    severity          TEXT,
    status            TEXT,
    owner             TEXT,
    opened_at         TEXT NOT NULL,
    last_seen_at      TEXT,
    closed_at         TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id                TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL REFERENCES projects(id),
    decided_at        TEXT NOT NULL,
    decision          TEXT,
    rationale         TEXT,
    decided_by        TEXT
);

CREATE TABLE IF NOT EXISTS generated_artifacts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id        TEXT REFERENCES projects(id),
    run_id            TEXT REFERENCES project_snapshots(run_id),
    kind              TEXT NOT NULL,
    path              TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ado_sync_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id        TEXT NOT NULL REFERENCES projects(id),
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    status            TEXT,
    item_count        INTEGER,
    error_summary     TEXT
);

CREATE INDEX IF NOT EXISTS idx_metrics_project_time
    ON project_metrics(project_id, measured_at);
CREATE INDEX IF NOT EXISTS idx_milestone_project_time
    ON milestone_snapshots(project_id, measured_at);
CREATE INDEX IF NOT EXISTS idx_risks_project_status
    ON risks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_snapshots_project_time
    ON project_snapshots(project_id, created_at);
"""

_local = threading.local()


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._migrate()

    def _migrate(self) -> None:
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if not cur.fetchone():
            self._conn.executescript(_DDL)
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_version VALUES (?)", (_SCHEMA_VERSION,)
            )
            self._conn.commit()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        assert self._conn is not None
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        assert self._conn is not None
        return self._conn.execute(sql, params)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


_db_instance: Database | None = None


def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db_instance


def init_db(path: str | Path) -> Database:
    global _db_instance
    _db_instance = Database(path)
    _db_instance.connect()
    return _db_instance
