"""Forecast Explanation skill — plain-language explanation of forecast derivation."""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..claude.provider import ClaudeProvider
    from ..progress.forecast import ForecastResult

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a delivery-status writing assistant for an executive audience. "
    "Use only the provided forecast figures. Do not restate raw numbers beyond what is provided."
)

_PROMPT = """\
[INPUT]
forecast: {forecast_date}, confidence: {confidence}
basis: velocity {velocity:.2f}/day over {window} days; remaining {remaining:.1f}; \
history_points {data_points}; forecast_days {days_remaining}

[TASK]
Explain in 2-3 plain-language sentences how the forecast was derived and what would
change it. Convey the confidence level clearly.
"""


def generate_forecast_explanation(
    forecast: "ForecastResult",
    velocity_window: int,
    remaining: float,
    provider: Optional["ClaudeProvider"],
    model: Optional[str] = None,
) -> str:
    if forecast.forecast_date is None:
        return forecast.note or "Forecast unavailable — insufficient history."

    if not provider:
        return _fallback_explanation(forecast)

    prompt = _PROMPT.format(
        forecast_date=str(forecast.forecast_date),
        confidence=forecast.confidence,
        velocity=forecast.velocity_per_day,
        window=velocity_window,
        remaining=remaining,
        data_points=0,
        days_remaining=forecast.days_remaining or 0,
    )

    try:
        result = provider.complete(
            system=_SYSTEM,
            prompt=prompt,
            max_tokens=300,
            temperature=0.2,
            model=model,
        )
        return result.content.strip()
    except Exception as e:
        logger.warning("Forecast explanation failed: %s", e)
        return _fallback_explanation(forecast)


def _fallback_explanation(forecast: "ForecastResult") -> str:
    return (
        f"Forecast: {forecast.forecast_date} ({forecast.confidence} confidence). "
        f"At current velocity of {forecast.velocity_per_day:.2f} units/day, "
        f"completion in {forecast.days_remaining} days. "
        f"{forecast.note}"
    )
