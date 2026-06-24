"""Strategy 3: Weighted workload (story points / effort weights)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ado.work_items import WorkItem
    from ..config.models import ProgressModelConfig


def compute_weighted_workload(
    items: list["WorkItem"],
    config: "ProgressModelConfig",
) -> tuple[float, float, float]:
    """Returns (overall_percent, completed_weight, total_weight)."""
    done_states = set(config.done_states)
    type_weights = config.type_weights

    def weight_of(wi: "WorkItem") -> float:
        type_w = type_weights.get(wi.work_item_type, 1.0) if type_weights else 1.0
        sp = wi.story_points if wi.story_points is not None else 1.0
        return sp * type_w

    total = sum(weight_of(wi) for wi in items)
    completed = sum(weight_of(wi) for wi in items if wi.state in done_states)

    pct = (completed / total) if total > 0 else 0.0
    return min(pct, 1.0), completed, total
