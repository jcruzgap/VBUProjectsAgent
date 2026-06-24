"""Conflict detection and conflicts.md management."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .context_manager import ContextManager, ContextFile


@dataclass
class Conflict:
    id: str
    field: str
    existing_value: str
    existing_source: str
    incoming_value: str
    incoming_source: str
    note: str
    status: str = "unresolved"


def _next_conflict_id(existing_body: str, date_prefix: str) -> str:
    pattern = rf"CONFLICT-{date_prefix}-(\d+)"
    nums = [int(m) for m in re.findall(pattern, existing_body)]
    next_num = (max(nums) + 1) if nums else 1
    return f"CONFLICT-{date_prefix}-{next_num:02d}"


class ConflictManager:
    def __init__(self, context_manager: ContextManager) -> None:
        self.ctx = context_manager

    def record_conflict(
        self,
        field: str,
        existing_value: str,
        existing_source: str,
        incoming_value: str,
        incoming_source: str,
        note: str = "",
    ) -> Conflict:
        """Append a conflict block to conflicts.md and return the Conflict."""
        conflicts_file = self.ctx.load_file("conflicts.md")
        body = conflicts_file.body

        date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conflict_id = _next_conflict_id(body, date_prefix)

        block = (
            f"\n## {conflict_id}  (status: unresolved)\n"
            f"- field: {field}\n"
            f"- existing: {existing_value}  (source: {existing_source})\n"
            f"- incoming: {incoming_value}  (source: {incoming_source})\n"
            f"- note: {note or 'No additional context.'}\n"
            f"- recommended_action: Review and resolve manually before next sync.\n"
        )

        if "# Conflicts" not in body:
            body = "# Conflicts\n\nConflicts detected during context updates are recorded here.\n"
        body += block

        self.ctx.update_body("conflicts.md", body, source=incoming_source)

        return Conflict(
            id=conflict_id,
            field=field,
            existing_value=existing_value,
            existing_source=existing_source,
            incoming_value=incoming_value,
            incoming_source=incoming_source,
            note=note,
        )

    def get_open_conflicts(self) -> list[str]:
        """Return list of unresolved conflict IDs from conflicts.md."""
        conflicts_file = self.ctx.load_file("conflicts.md")
        return re.findall(r"(CONFLICT-\S+)\s+\(status: unresolved\)", conflicts_file.body)

    def mark_resolved(self, conflict_id: str) -> None:
        """Mark a conflict as resolved in conflicts.md."""
        conflicts_file = self.ctx.load_file("conflicts.md")
        new_body = conflicts_file.body.replace(
            f"{conflict_id}  (status: unresolved)",
            f"{conflict_id}  (status: resolved)",
        )
        self.ctx.update_body("conflicts.md", new_body, source="manual-resolution")
