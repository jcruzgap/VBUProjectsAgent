"""Slack Status Writer skill — generates copy-ready executive Slack messages."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..claude.provider import ClaudeProvider
    from ..progress.engine import ProgressResult

from .validators import validate_slack_output

logger = logging.getLogger(__name__)

_SYSTEM_PREAMBLE = """\
You are a delivery-status writing assistant for an executive audience.
Rules:
- Use ONLY the figures, dates, names, and facts provided in the input block.
- NEVER invent, compute, round differently, or estimate any number or date.
- If a value is missing, omit it rather than guessing.
- Do not include secrets, tokens, PATs, internal IDs, or raw work-item titles
  unless explicitly present and permitted in the input.
- Match the requested structure and word budget exactly.
- Write in a {tone} tone."""

_PROMPT_TEMPLATE = """\
[INPUT]
project_name: {name}
health: {health}  (reasons: {reasons})
progress: {progress_summary}
next_milestone: {milestone_name} target {target_or_forecast_date}
top_risk: {top_risk_text}
open_ask: {ask_text}
max_words: {max_words}

[TASK]
Write a copy-ready executive Slack status with exactly these lines:
1) "{name} — Status: {health_cap}"
2) "Progress: ..."
3) "Next milestone: ..."
4) "Key risk: ..."   (omit if no risk)
5) "Ask: ..."        (omit if no ask)
Stay within {max_words} words. Use only the figures above.
"""


@dataclass
class SlackStatusInputs:
    project_name: str
    health: str
    health_reasons: list[str]
    progress_summary: str
    milestone_name: str
    target_or_forecast_date: str
    top_risk_text: str
    ask_text: str
    max_words: int = 180
    tone: str = "concise_executive"


def _deterministic_fallback(inputs: SlackStatusInputs) -> str:
    """Always-available template-based output when Claude is unavailable."""
    lines = [f"{inputs.project_name} — Status: {inputs.health.capitalize()}"]
    lines.append(f"Progress: {inputs.progress_summary}.")
    lines.append(f"Next milestone: {inputs.milestone_name} — {inputs.target_or_forecast_date}.")
    if inputs.top_risk_text and inputs.top_risk_text.lower() not in ("none", ""):
        lines.append(f"Key risk: {inputs.top_risk_text}.")
    if inputs.ask_text and inputs.ask_text.lower() not in ("none", ""):
        lines.append(f"Ask: {inputs.ask_text}.")
    lines.append("[Generated without narrative model; figures are computed.]")
    return "\n".join(lines)


def generate_slack_status(
    inputs: SlackStatusInputs,
    provider: Optional["ClaudeProvider"],
    model: Optional[str] = None,
    max_retries: int = 2,
) -> str:
    """Generate a Slack status message. Falls back to deterministic template on failure."""
    allowed_context = (
        f"{inputs.project_name} {inputs.health} {inputs.progress_summary} "
        f"{inputs.milestone_name} {inputs.target_or_forecast_date} "
        f"{inputs.top_risk_text} {inputs.ask_text}"
    )

    if not provider:
        logger.warning("No Claude provider — using deterministic Slack fallback")
        return _deterministic_fallback(inputs)

    system = _SYSTEM_PREAMBLE.format(tone=inputs.tone)
    prompt = _PROMPT_TEMPLATE.format(
        name=inputs.project_name,
        health=inputs.health,
        health_cap=inputs.health.capitalize(),
        reasons="; ".join(inputs.health_reasons),
        progress_summary=inputs.progress_summary,
        milestone_name=inputs.milestone_name,
        target_or_forecast_date=inputs.target_or_forecast_date,
        top_risk_text=inputs.top_risk_text or "None",
        ask_text=inputs.ask_text or "None",
        max_words=inputs.max_words,
    )

    for attempt in range(max_retries + 1):
        try:
            result = provider.complete(
                system=system,
                prompt=prompt,
                max_tokens=400,
                temperature=0.2,
                model=model,
            )
            output = result.content.strip()
            errors = validate_slack_output(output, allowed_context, inputs.max_words)
            if errors:
                logger.warning(
                    "Slack output validation failed (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, errors
                )
                if attempt < max_retries:
                    continue
                logger.warning("Falling back to deterministic template")
                return _deterministic_fallback(inputs)
            return output
        except Exception as e:
            logger.warning("Claude call failed (attempt %d): %s", attempt + 1, e)
            if attempt >= max_retries:
                break

    return _deterministic_fallback(inputs)
