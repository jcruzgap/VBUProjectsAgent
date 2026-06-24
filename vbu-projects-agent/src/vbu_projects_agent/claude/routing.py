"""Per-task model routing using task_models config."""
from __future__ import annotations

from typing import Optional


_TASK_MAP = {
    "classify_input": "classify_input",
    "reconcile_context": "reconcile_context",
    "executive_summary": "executive_summary",
}


def resolve_model(
    task: str,
    task_models_config,  # ClaudeTaskModels
    default_model: str,
) -> Optional[str]:
    """
    Return the model to use for a given task, or None to use the provider default.
    None → provider uses its own default_model.
    """
    attr = _TASK_MAP.get(task)
    if attr:
        override = getattr(task_models_config, attr, None)
        if override:
            return override
    return default_model
