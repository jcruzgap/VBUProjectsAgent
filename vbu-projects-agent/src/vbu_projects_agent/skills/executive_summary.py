"""Executive Summary skill — 3-5 sentence delivery summary for reports/dashboard."""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..claude.provider import ClaudeProvider

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a delivery-status writing assistant for an executive audience. "
    "Use ONLY the figures, dates, names, and facts provided. "
    "NEVER invent or compute numbers. Write in a professional, concise tone."
)

_PROMPT = """\
[INPUT]
computed_facts: {facts_json}
recent_changes: {change_digest}
[TASK]
Write a 3-5 sentence executive summary of delivery status and trajectory.
State health and the single most important driver. Reference the next milestone
and any forecast with its confidence qualifier ("high/medium/low confidence").
Use only provided figures.
"""


def generate_executive_summary(
    facts: dict,
    recent_changes: str,
    provider: Optional["ClaudeProvider"],
    model: Optional[str] = None,
) -> str:
    if not provider:
        return _fallback_summary(facts)

    import json
    prompt = _PROMPT.format(
        facts_json=json.dumps(facts, default=str, indent=2),
        change_digest=recent_changes or "No recent changes summarized.",
    )

    try:
        result = provider.complete(
            system=_SYSTEM,
            prompt=prompt,
            max_tokens=500,
            temperature=0.2,
            model=model,
        )
        from ..security.scanner import scan_text
        scan_text(result.content, "executive summary output")
        return result.content.strip()
    except Exception as e:
        logger.warning("Executive summary generation failed: %s", e)
        return _fallback_summary(facts)


def _fallback_summary(facts: dict) -> str:
    health = facts.get("health", "unknown")
    pct = facts.get("overall_percent", 0)
    pct_display = f"{pct * 100:.1f}%" if isinstance(pct, float) else str(pct)
    milestone = facts.get("next_milestone", "")
    return (
        f"Delivery status is {health}. Overall progress is at {pct_display}. "
        f"{'Next milestone: ' + milestone + '.' if milestone else ''} "
        "[Summary generated from computed facts — narrative model unavailable.]"
    ).strip()
