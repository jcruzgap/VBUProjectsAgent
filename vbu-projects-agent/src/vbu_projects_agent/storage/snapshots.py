"""Snapshot creation, reading, and rollback for project context files."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _run_id(source_files: list[str]) -> str:
    """Generate a stable run_id from UTC timestamp + hash of input filenames+sizes."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    digest = hashlib.sha256("|".join(sorted(source_files)).encode()).hexdigest()[:8]
    return f"{ts}-{digest}"


class SnapshotManager:
    def __init__(self, snapshots_root: Path) -> None:
        self.root = snapshots_root
        self.root.mkdir(parents=True, exist_ok=True)

    def create_snapshot(
        self,
        project_id: str,
        context_dir: Path,
        run_id: str,
        mode: str,
        source_files: list[str],
        metrics: Optional[dict] = None,
    ) -> Path:
        """Copy context dir + write metrics.json + meta.json into a timestamped folder."""
        snap_dir = self.root / project_id / run_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        # Copy context files
        ctx_dest = snap_dir / "context"
        if context_dir.exists():
            shutil.copytree(context_dir, ctx_dest, dirs_exist_ok=True)
        else:
            ctx_dest.mkdir(parents=True, exist_ok=True)

        # Compute content hashes
        hashes: dict[str, str] = {}
        for f in ctx_dest.rglob("*.md"):
            content = f.read_bytes()
            hashes[f.name] = hashlib.sha256(content).hexdigest()

        # Write metrics.json
        if metrics:
            (snap_dir / "metrics.json").write_text(
                json.dumps(metrics, indent=2, default=str), encoding="utf-8"
            )

        # Write meta.json
        meta = {
            "run_id": run_id,
            "project_id": project_id,
            "mode": mode,
            "source_files": source_files,
            "context_hashes": hashes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (snap_dir / "meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

        return snap_dir

    def get_context_hashes(self, snap_dir: Path) -> dict[str, str]:
        meta_file = snap_dir / "meta.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            return meta.get("context_hashes", {})
        return {}

    def list_snapshots(self, project_id: str) -> list[str]:
        """Return run_ids sorted newest first."""
        project_snap = self.root / project_id
        if not project_snap.exists():
            return []
        return sorted(
            [d.name for d in project_snap.iterdir() if d.is_dir()],
            reverse=True,
        )

    def get_snapshot_path(self, project_id: str, run_id: str) -> Optional[Path]:
        p = self.root / project_id / run_id
        return p if p.exists() else None

    def get_latest_snapshot_path(self, project_id: str) -> Optional[Path]:
        snaps = self.list_snapshots(project_id)
        if not snaps:
            return None
        return self.root / project_id / snaps[0]

    def restore_snapshot(
        self,
        project_id: str,
        run_id: str,
        context_dir: Path,
    ) -> Path:
        """Restore context files from a snapshot. Creates pre-restore safety snapshot first."""
        snap_dir = self.get_snapshot_path(project_id, run_id)
        if snap_dir is None:
            raise FileNotFoundError(
                f"Snapshot {run_id!r} not found for project {project_id!r}"
            )

        # Safety backup of current state before restoring
        safety_id = _run_id(["pre-rollback"])
        safety_dir = self.root / project_id / f"pre-rollback-{safety_id}"
        if context_dir.exists():
            shutil.copytree(context_dir, safety_dir / "context", dirs_exist_ok=True)

        # Restore
        src_ctx = snap_dir / "context"
        if context_dir.exists():
            shutil.rmtree(context_dir)
        if src_ctx.exists():
            shutil.copytree(src_ctx, context_dir)
        else:
            context_dir.mkdir(parents=True, exist_ok=True)

        return snap_dir

    def make_run_id(self, source_files: list[str]) -> str:
        return _run_id(source_files)
