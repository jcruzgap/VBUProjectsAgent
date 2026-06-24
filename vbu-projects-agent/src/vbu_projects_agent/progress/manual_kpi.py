"""Strategy 4: Manual KPI progress (DM-supplied KPI values)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import ProgressModelConfig, ManualKpi


@dataclass
class KpiProgress:
    id: str
    name: str
    current: float
    target: float
    weight: float
    percent: float


def compute_manual_kpi(
    config: "ProgressModelConfig",
) -> tuple[list[KpiProgress], float]:
    """Returns (kpi_progress_list, overall_weighted_percent)."""
    kpis = config.kpis
    if not kpis:
        return [], 0.0

    results: list[KpiProgress] = []
    total_weight = sum(k.weight for k in kpis)
    weighted_sum = 0.0

    for kpi in kpis:
        pct = min(kpi.current / kpi.target, 1.0) if kpi.target > 0 else 0.0
        results.append(KpiProgress(
            id=kpi.id,
            name=kpi.name,
            current=kpi.current,
            target=kpi.target,
            weight=kpi.weight,
            percent=pct,
        ))
        weighted_sum += pct * kpi.weight

    overall = (weighted_sum / total_weight) if total_weight > 0 else 0.0
    return results, min(overall, 1.0)
