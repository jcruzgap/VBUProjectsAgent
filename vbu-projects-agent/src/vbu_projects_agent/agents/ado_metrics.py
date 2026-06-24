"""ADO Metrics Agent — WIQL → batch → normalized items → Progress Engine."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import ProjectConfig, GlobalConfig

from ..ado.client import AdoClient
from ..ado.errors import AdoPatMissing
from ..progress.engine import ProgressEngine, ProgressResult
from ..storage.repositories import (
    MetricsRepository, MilestoneRepository, AdoSyncRepository, ProjectRepository
)
from ..storage.snapshots import SnapshotManager
from ..storage.db import Database

logger = logging.getLogger(__name__)


class AdoMetricsAgent:
    """Orchestrates ADO sync → progress computation → metric persistence."""

    def __init__(
        self,
        project_config: "ProjectConfig",
        global_config: "GlobalConfig",
        db: Database,
        snapshot_manager: SnapshotManager,
    ) -> None:
        self.pcfg = project_config
        self.gcfg = global_config
        self.db = db
        self.snap_mgr = snapshot_manager

    def run(self, no_cache: bool = False) -> ProgressResult | None:
        project_id = self.pcfg.project.id
        started_at = datetime.now(timezone.utc).isoformat()

        ado_repo = AdoSyncRepository(self.db)
        sync_row = ado_repo.insert(project_id=project_id, started_at=started_at)

        try:
            client = AdoClient(
                ado_config=self.pcfg.azure_devops,
                field_mappings=self.pcfg.field_mappings,
                global_ado=self.gcfg.ado,
            )
            items = client.fetch_work_items(
                wiql=self.pcfg.work_items.wiql,
                no_cache=no_cache,
            )
            logger.info("ADO sync: %d work items for %s", len(items), project_id)

            # Load history for velocity/forecasting
            metrics_repo = MetricsRepository(self.db)
            history = metrics_repo.get_history(project_id)

            # Load risks for health modifiers
            from ..storage.repositories import RiskRepository
            risk_repo = RiskRepository(self.db)
            open_risks = risk_repo.get_open(project_id)

            engine = ProgressEngine()
            result = engine.compute(
                items=items,
                config=self.pcfg.progress_model,
                health_thresholds=self.pcfg.project.health_thresholds,
                history=history,
                open_risks=open_risks,
            )

            # Persist snapshot
            run_id = self.snap_mgr.make_run_id([f"ado-sync-{started_at}"])

            # The snapshot for ADO sync doesn't need context copy — just metrics
            snap_path = self.snap_mgr.root / project_id / run_id
            snap_path.mkdir(parents=True, exist_ok=True)
            import json
            (snap_path / "metrics.json").write_text(
                json.dumps(result.to_dict(), indent=2, default=str)
            )

            from ..storage.repositories import SnapshotRepository
            snap_repo = SnapshotRepository(self.db)
            snap_repo.insert(
                run_id=run_id,
                project_id=project_id,
                mode="sync",
                claude_provider=None,
                source_files=["ado-sync"],
                snapshot_path=str(snap_path),
                context_hashes={},
                change_summary=f"ADO sync: {len(items)} items, health={result.health}",
            )

            # Persist metrics
            fc = result.forecast
            metrics_repo.insert(
                run_id=run_id,
                project_id=project_id,
                overall_percent=result.overall_percent,
                active_stage=result.active_stage,
                health=result.health,
                velocity_per_day=result.velocity.per_day if result.velocity else None,
                forecast_date=str(fc.forecast_date) if fc and fc.forecast_date else None,
                forecast_conf=None,
                monthly_revenue=self.pcfg.revenue.monthly_revenue,
                raw_counts=result.raw_counts,
            )

            # Persist milestone snapshots
            ms_repo = MilestoneRepository(self.db)
            for m in result.milestones:
                ms_repo.insert(
                    run_id=run_id,
                    project_id=project_id,
                    milestone_id=m.id,
                    name=m.name,
                    target_date=str(m.target_date) if m.target_date else None,
                    forecast_date=str(m.forecast.forecast_date) if m.forecast and m.forecast.forecast_date else None,
                    percent_complete=m.percent,
                    state=m.state,
                )

            # Update project health
            proj_repo = ProjectRepository(self.db)
            proj_repo.update_health(project_id, result.health)

            ado_repo.finish(sync_row, status="success", item_count=len(items))
            logger.info("ADO sync complete for %s: health=%s, progress=%.1f%%",
                        project_id, result.health, result.overall_percent * 100)
            return result

        except AdoPatMissing as e:
            ado_repo.finish(sync_row, status="auth_error",
                            error_summary=str(e)[:500])
            raise
        except Exception as e:
            from ..security.redaction import redact
            ado_repo.finish(sync_row, status="error",
                            error_summary=redact(str(e))[:500])
            raise
