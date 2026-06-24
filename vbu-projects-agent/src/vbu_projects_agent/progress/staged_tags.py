"""Strategy 1: Stage/tag-based progress (PBIs grouped into stages by tags)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ado.work_items import WorkItem
    from ..config.models import ProgressModelConfig


@dataclass
class StageProgress:
    id: str
    name: str
    tag: str
    total: int
    completed: int
    percent: float
    status: str  # "done" | "active" | "not_started"


def compute_staged_tags(
    items: list["WorkItem"],
    config: "ProgressModelConfig",
) -> tuple[list[StageProgress], float, str | None]:
    """
    Returns (stage_progress_list, overall_percent, active_stage_id).
    """
    stages = config.stages
    if not stages:
        return [], 0.0, None

    stage_results: list[StageProgress] = []
    all_done_weight = 0.0
    all_total_weight = 0.0

    active_stage: str | None = None

    for stage in stages:
        tagged = [wi for wi in items if stage.tag in wi.tags]
        completed = sum(1 for wi in tagged if wi.state in stage.done_states)
        total = stage.target_count if stage.target_count else len(tagged)
        if total == 0:
            pct = 0.0
        else:
            pct = min(completed / total, 1.0)

        if pct >= 1.0:
            status = "done"
        elif pct > 0.0 or (active_stage is None):
            status = "active" if active_stage is None else "not_started"
            if active_stage is None and pct < 1.0:
                active_stage = stage.id
        else:
            status = "not_started"

        stage_results.append(StageProgress(
            id=stage.id,
            name=stage.name,
            tag=stage.tag,
            total=total,
            completed=completed,
            percent=pct,
            status=status,
        ))

        all_done_weight += completed
        all_total_weight += total

    overall = (all_done_weight / all_total_weight) if all_total_weight > 0 else 0.0
    return stage_results, overall, active_stage
