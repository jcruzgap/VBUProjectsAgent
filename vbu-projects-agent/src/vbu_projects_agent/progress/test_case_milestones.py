"""Strategy 2: Test-case-passing milestones (Alpha=100, Beta=200, Production=300)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..ado.work_items import WorkItem
    from ..config.models import ProgressModelConfig, MilestoneConfig

from .velocity import compute_velocity
from .forecast import compute_forecast, ForecastResult


@dataclass
class MilestoneProgress:
    id: str
    name: str
    target_passing: int
    target_date: Optional[date]
    passing: int
    remaining: int
    percent: float
    state: str          # "done" | "on_track" | "at_risk" | "late"
    forecast: Optional[ForecastResult] = None


def compute_test_case_milestones(
    items: list["WorkItem"],
    config: "ProgressModelConfig",
    history: list[dict],
) -> tuple[list[MilestoneProgress], float, Optional[str], Optional[ForecastResult]]:
    """
    Returns (milestone_progress_list, overall_percent, active_milestone_id, active_forecast).
    """
    done_states = set(config.done_states)
    passing = sum(
        1 for wi in items
        if wi.work_item_type in ("Test Case",) and wi.state in done_states
    )
    # Also count non-typed items that are done if no test case filter matches
    if passing == 0:
        passing = sum(1 for wi in items if wi.state in done_states)

    velocity = compute_velocity(history, value_key="overall_percent")

    milestones_cfg = config.milestones
    if not milestones_cfg:
        return [], 0.0, None, None

    milestone_results: list[MilestoneProgress] = []
    active_milestone: Optional[str] = None
    active_forecast: Optional[ForecastResult] = None

    for m in milestones_cfg:
        target = m.target_passing
        pct = min(passing / target, 1.0) if target > 0 else 0.0
        remaining = max(target - passing, 0)

        try:
            tdate = date.fromisoformat(m.target_date) if m.target_date else None
        except ValueError:
            tdate = None

        # Compute forecast for this milestone
        forecast: Optional[ForecastResult] = None
        if remaining > 0 and velocity:
            from .forecast import compute_forecast
            forecast = compute_forecast(remaining, velocity, target_date=tdate)

        if pct >= 1.0:
            state = "done"
        elif tdate and forecast and forecast.forecast_date and forecast.forecast_date > tdate:
            state = "at_risk"
        elif tdate and date.today() > tdate:
            state = "late"
        else:
            state = "on_track"

        if pct < 1.0 and active_milestone is None:
            active_milestone = m.id
            active_forecast = forecast

        milestone_results.append(MilestoneProgress(
            id=m.id,
            name=m.name,
            target_passing=target,
            target_date=tdate,
            passing=passing,
            remaining=remaining,
            percent=pct,
            state=state,
            forecast=forecast,
        ))

    # Overall = progress toward the last (highest) milestone
    last = milestones_cfg[-1]
    overall = min(passing / last.target_passing, 1.0) if last.target_passing > 0 else 0.0

    return milestone_results, overall, active_milestone, active_forecast
