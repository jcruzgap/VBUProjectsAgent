"""Delivery Status Analyst Agent — produces the view-model for reporting and Slack."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import ProjectConfig
    from ..progress.engine import ProgressResult

from ..storage.repositories import MetricsRepository, RiskRepository, DecisionRepository, MilestoneRepository
from ..storage.db import Database


@dataclass
class ProjectStatusView:
    project_id: str
    project_name: str
    health: str
    health_reasons: list[str]
    overall_percent: float
    active_stage: Optional[str]
    progress_summary: str
    next_milestone_name: str
    next_milestone_date: str
    top_risk_text: str
    ask_text: str
    open_risks: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    latest_metrics: Optional[dict] = None
    revenue_monthly: float = 0.0
    revenue_at_risk: bool = False


class StatusAnalystAgent:
    """Assembles a ProjectStatusView from DB history + latest ProgressResult."""

    def __init__(self, db: Database, project_config: "ProjectConfig") -> None:
        self.db = db
        self.pcfg = project_config

    def analyze(self, progress: "ProgressResult") -> ProjectStatusView:
        project_id = self.pcfg.project.id
        project_name = self.pcfg.project.name

        risk_repo = RiskRepository(self.db)
        open_risks = risk_repo.get_open(project_id)

        dec_repo = DecisionRepository(self.db)
        decisions = dec_repo.get_all(project_id, limit=10)

        metrics_repo = MetricsRepository(self.db)
        history = metrics_repo.get_history(project_id, limit=60)

        # Build progress_summary text
        pct = progress.overall_percent * 100
        if progress.milestones:
            active_m = next(
                (m for m in progress.milestones if m.state != "done"), None
            )
            if active_m:
                remaining = active_m.target_passing - active_m.passing
                progress_summary = (
                    f"{active_m.name} is {active_m.percent * 100:.0f}% complete, "
                    f"with {remaining} test cases remaining"
                )
                next_ms_name = active_m.name
                if active_m.forecast and active_m.forecast.forecast_date:
                    next_ms_date = str(active_m.forecast.forecast_date)
                elif active_m.target_date:
                    next_ms_date = str(active_m.target_date)
                else:
                    next_ms_date = "TBD"
            else:
                progress_summary = f"All milestones complete ({pct:.0f}%)"
                next_ms_name = "Complete"
                next_ms_date = "—"
        elif progress.stages:
            active_s = next((s for s in progress.stages if s.status == "active"), None)
            if active_s:
                progress_summary = (
                    f"{active_s.name} is {active_s.percent * 100:.0f}% complete "
                    f"({active_s.completed}/{active_s.total} items)"
                )
                next_ms_name = active_s.name
                next_ms_date = "TBD"
            else:
                progress_summary = f"{pct:.0f}% complete"
                next_ms_name = "—"
                next_ms_date = "—"
        else:
            progress_summary = f"{pct:.0f}% complete"
            next_ms_name = "—"
            next_ms_date = "—"

        # Top risk
        high_risks = [r for r in open_risks if r.get("severity") in ("high", "critical")]
        if high_risks:
            top_risk = high_risks[0].get("description", "")[:120]
        elif open_risks:
            top_risk = open_risks[0].get("description", "")[:120]
        else:
            top_risk = "None"

        revenue_monthly = self.pcfg.revenue.monthly_revenue
        revenue_at_risk = progress.health in ("yellow", "red") and revenue_monthly > 0

        return ProjectStatusView(
            project_id=project_id,
            project_name=project_name,
            health=progress.health,
            health_reasons=progress.health_reasons,
            overall_percent=progress.overall_percent,
            active_stage=progress.active_stage,
            progress_summary=progress_summary,
            next_milestone_name=next_ms_name,
            next_milestone_date=next_ms_date,
            top_risk_text=top_risk,
            ask_text="",
            open_risks=open_risks,
            decisions=decisions,
            history=history,
            revenue_monthly=revenue_monthly,
            revenue_at_risk=revenue_at_risk,
        )
