"""Normalized WorkItem dataclass and field mapping."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config.models import FieldMappings


@dataclass(frozen=True)
class WorkItem:
    id: int
    title: str
    state: str
    tags: tuple[str, ...]
    story_points: Optional[float]
    work_item_type: str
    # raw dict is intentionally NOT included — stays in memory only


def map_work_item(raw: dict, mappings: FieldMappings) -> WorkItem:
    """Map a raw ADO work item dict to a normalized WorkItem."""
    fields = raw.get("fields", {})

    raw_tags = fields.get(mappings.tags, "") or ""
    tags = tuple(t.strip() for t in raw_tags.split(";") if t.strip())

    sp_raw = fields.get(mappings.story_points)
    story_points: Optional[float] = None
    if sp_raw is not None:
        try:
            story_points = float(sp_raw)
        except (TypeError, ValueError):
            pass

    return WorkItem(
        id=int(raw.get("id", fields.get(mappings.id, 0))),
        title=str(fields.get(mappings.title, "")),
        state=str(fields.get(mappings.state, "")),
        tags=tags,
        story_points=story_points,
        work_item_type=str(fields.get(mappings.work_item_type, "")),
    )
