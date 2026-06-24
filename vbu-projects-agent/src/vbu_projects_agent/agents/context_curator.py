"""Project Context Curator Agent — orchestrates the §8 update workflow."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import ProjectConfig, GlobalConfig
    from ..claude.provider import ClaudeProvider

from ..projects.update_workflow import UpdateWorkflow, UpdateResult
from ..storage.snapshots import SnapshotManager
from ..storage.db import Database

logger = logging.getLogger(__name__)


class ContextCuratorAgent:
    """
    High-level agent that drives the full context update workflow.
    Composes UpdateWorkflow with Claude, snapshots, and DB.
    """

    def __init__(
        self,
        project_dir: Path,
        project_config: "ProjectConfig",
        global_config: "GlobalConfig",
        db: Database,
        claude_provider: "ClaudeProvider",
        snapshot_manager: SnapshotManager,
    ) -> None:
        self.workflow = UpdateWorkflow(
            project_dir=project_dir,
            project_config=project_config,
            global_config=global_config,
            db=db,
            claude_provider=claude_provider,
            snapshot_manager=snapshot_manager,
        )

    def run(self, dry_run: bool = False, review_required: bool = False) -> UpdateResult:
        return self.workflow.run(dry_run=dry_run, review_required=review_required)
