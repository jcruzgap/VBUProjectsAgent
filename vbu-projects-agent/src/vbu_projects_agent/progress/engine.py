"""Progress Engine — strategy registry + unified ProgressResult."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from ..config.models import ProgressModelConfig, HealthThresholds
from ..ado.work_items import WorkItem
from .staged_tags import StageProgress, compute_staged_tags
from .test_case_milestones import MilestoneProgress, compute_test_case_milestones
from .weighted_workload import compute_weighted_workload
from .manual_kpi import KpiProgress, compute_manual_kpi
from .velocity import VelocityResult, compute_velocity
from .forecast import ForecastResult, compute_forecast
from .health import compute_health, HealthColor

# Re-export for public API
__all__ = [
    "ProgressEngine", "ProgressResult", "StageProgress", "VelocityResult", "ForecastResult",
]


@dataclass
class ProgressResult:
    overall_percent: float
    health: HealthColor
    health_reasons: list[str]
    stages: list[StageProgress] = field(default_factory=list)
    milestones: list[MilestoneProgress] = field(default_factory=list)
    kpis: list[KpiProgress] = field(default_factory=list)
    active_stage: Optional[str] = None
    velocity: Optional[VelocityResult] = None
    forecast: Optional[ForecastResult] = None
    notes: list[str] = field(default_factory=list)
    raw_counts: dict[str, Any] = field(default_factory=dict)
    measured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)


class ProgressEngine:
    """Computes progress for a project using the configured strategy."""

    def compute(
        self,
        items: list[WorkItem],
        config: ProgressModelConfig,
        health_thresholds: HealthThresholds,
        history: list[dict],
        open_risks: list[dict] | None = None,
    ) -> ProgressResult:
        strategy = config.type
        open_risks = open_risks or []
        open_high = sum(1 for r in open_risks if r.get("severity") in ("high", "critical"))

        if strategy == "staged_tags":
            stages, overall, active = compute_staged_tags(items, config)
            velocity = compute_velocity(history) if history else None
            forecast = None
            if velocity and stages:
                active_stage = next((s for s in stages if s.id == active), None)
                if active_stage:
                    remaining_pct = 1.0 - active_stage.percent
                    forecast = compute_forecast(remaining_pct * 100, velocity)
            color, reasons = compute_health(
                overall, health_thresholds, open_high,
                negative_velocity=(velocity is not None and velocity.per_day <= 0),
            )
            return ProgressResult(
                overall_percent=overall,
                health=color,
                health_reasons=reasons,
                stages=stages,
                active_stage=active,
                velocity=velocity,
                forecast=forecast,
                raw_counts={"strategy": "staged_tags", "item_count": len(items)},
            )

        elif strategy == "test_case_milestones":
            milestones, overall, active, forecast = compute_test_case_milestones(
                items, config, history
            )
            velocity = compute_velocity(history) if history else None
            color, reasons = compute_health(
                overall, health_thresholds, open_high,
                negative_velocity=(velocity is not None and velocity.per_day <= 0),
            )
            passing = sum(1 for wi in items if wi.state in set(config.done_states))
            return ProgressResult(
                overall_percent=overall,
                health=color,
                health_reasons=reasons,
                milestones=milestones,
                active_stage=active,
                velocity=velocity,
                forecast=forecast,
                raw_counts={
                    "strategy": "test_case_milestones",
                    "passing": passing,
                    "total_items": len(items),
                },
            )

        elif strategy == "weighted_workload":
            overall, completed_w, total_w = compute_weighted_workload(items, config)
            velocity = compute_velocity(history) if history else None
            forecast = None
            if velocity and total_w > completed_w:
                remaining = total_w - completed_w
                forecast = compute_forecast(remaining, velocity)
            color, reasons = compute_health(
                overall, health_thresholds, open_high,
                negative_velocity=(velocity is not None and velocity.per_day <= 0),
            )
            return ProgressResult(
                overall_percent=overall,
                health=color,
                health_reasons=reasons,
                active_stage=None,
                velocity=velocity,
                forecast=forecast,
                raw_counts={
                    "strategy": "weighted_workload",
                    "completed_weight": completed_w,
                    "total_weight": total_w,
                },
            )

        elif strategy == "manual_kpi":
            kpis, overall = compute_manual_kpi(config)
            color, reasons = compute_health(overall, health_thresholds, open_high)
            return ProgressResult(
                overall_percent=overall,
                health=color,
                health_reasons=reasons,
                kpis=kpis,
                raw_counts={"strategy": "manual_kpi", "kpi_count": len(kpis)},
            )

        else:
            raise ValueError(f"Unknown progress strategy: {strategy!r}")
