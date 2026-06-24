"""Typed MCP tool implementations (§16.4)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class McpToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_project(project_id: str, projects_root: Path) -> Path:
    d = projects_root / project_id
    if not d.exists():
        raise McpToolError("ProjectNotFound", f"Project '{project_id}' not found at {d}")
    return d


def tool_read_project_context(
    project_id: str,
    projects_root: Path,
) -> dict:
    """Read all context files for a project."""
    from ..projects.context_manager import ContextManager, _CONTEXT_FILES
    from ..security.scanner import scan_text

    project_dir = _require_project(project_id, projects_root)
    ctx_mgr = ContextManager(project_dir / "context")
    context = ctx_mgr.load_all()

    files: dict[str, str] = {}
    for name, cf in context.items():
        content = cf.body
        scan_text(content, label=f"context/{name}")
        files[name] = content

    return {"files": files}


def tool_write_project_context(
    project_id: str,
    file_name: str,
    content: str,
    projects_root: Path,
    snapshot_manager=None,
) -> dict:
    """Surgical write to one context file (snapshot-guarded)."""
    from ..projects.context_manager import ContextManager, _CONTEXT_FILES
    from ..security.scanner import scan_text, SecretDetected

    if file_name not in _CONTEXT_FILES:
        raise McpToolError("InvalidFile", f"'{file_name}' is not a valid context file")

    scan_text(content, label=f"write/{file_name}")

    project_dir = _require_project(project_id, projects_root)
    ctx_mgr = ContextManager(project_dir / "context")

    # Snapshot before write
    if snapshot_manager:
        run_id = snapshot_manager.make_run_id([f"mcp-write-{file_name}"])
        snapshot_manager.create_snapshot(
            project_id=project_id,
            context_dir=project_dir / "context",
            run_id=run_id,
            mode="mcp-write",
            source_files=[file_name],
        )

    ctx_file = ctx_mgr.update_body(file_name, content, source="mcp-tool")
    return {"ok": True, "content_sha256": ctx_file.content_hash}


def tool_list_project_input_files(project_id: str, projects_root: Path) -> dict:
    """List pending input files for a project."""
    project_dir = _require_project(project_id, projects_root)
    input_dir = project_dir / "input"
    if not input_dir.exists():
        return {"files": []}
    files = [f.name for f in sorted(input_dir.iterdir()) if f.is_file()]
    return {"files": files}


def tool_archive_processed_input(
    project_id: str,
    projects_root: Path,
    archive_folder: str = "processed_input",
) -> dict:
    """Move all input files to timestamped archive folder."""
    import shutil
    from datetime import datetime, timezone

    project_dir = _require_project(project_id, projects_root)
    input_dir = project_dir / "input"
    files = list(input_dir.glob("*")) if input_dir.exists() else []
    if not files:
        raise McpToolError("NothingToArchive", "No files in input/ to archive")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    archive_dir = project_dir / archive_folder / ts
    archive_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.is_file():
            shutil.move(str(f), str(archive_dir / f.name))

    return {"archived_to": str(archive_dir), "file_count": len(files)}


def tool_calculate_project_progress(
    project_id: str,
    projects_root: Path,
    project_config,
    history: list[dict],
    work_items: list,
) -> dict:
    """Run the Progress Engine and return ProgressResult as dict."""
    from ..progress.engine import ProgressEngine

    engine = ProgressEngine()
    result = engine.compute(
        items=work_items,
        config=project_config.progress_model,
        health_thresholds=project_config.project.health_thresholds,
        history=history,
    )
    return result.to_dict()


def tool_save_project_snapshot(
    project_id: str,
    projects_root: Path,
    snapshot_manager,
    db=None,
) -> dict:
    """Persist snapshot + DB rows for a project."""
    project_dir = _require_project(project_id, projects_root)
    run_id = snapshot_manager.make_run_id([f"mcp-snapshot-{project_id}"])
    snap_path = snapshot_manager.create_snapshot(
        project_id=project_id,
        context_dir=project_dir / "context",
        run_id=run_id,
        mode="mcp-snapshot",
        source_files=["mcp-trigger"],
    )
    return {"run_id": run_id, "path": str(snap_path)}


def tool_query_project_history(
    project_id: str,
    metric_name: str,
    db,
) -> dict:
    """Return time-series data for a metric."""
    from ..storage.repositories import MetricsRepository

    known = {"overall_percent", "health", "velocity_per_day", "forecast_date", "monthly_revenue"}
    if metric_name not in known:
        raise McpToolError("UnknownMetric", f"Unknown metric: {metric_name!r}. Known: {sorted(known)}")

    repo = MetricsRepository(db)
    history = repo.get_history(project_id, metric=metric_name)
    return {"points": history}
