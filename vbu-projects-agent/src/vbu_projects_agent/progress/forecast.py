"""Deterministic milestone forecasting from velocity + remaining work."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .velocity import VelocityResult


@dataclass
class ForecastResult:
    forecast_date: Optional[date]
    confidence: str         # "high" | "medium" | "low"
    days_remaining: Optional[int]
    velocity_per_day: float
    note: str = ""


def compute_forecast(
    remaining: float,
    velocity: Optional[VelocityResult],
    target_date: Optional[date] = None,
) -> ForecastResult:
    """
    Compute a forecast completion date from remaining work and velocity.
    Suppresses forecast when velocity is None, zero, or history is thin.
    """
    if velocity is None or velocity.per_day <= 0:
        return ForecastResult(
            forecast_date=None,
            confidence="low",
            days_remaining=None,
            velocity_per_day=0.0,
            note="Insufficient history or zero velocity — forecast suppressed.",
        )

    if velocity.data_points < 3:
        return ForecastResult(
            forecast_date=None,
            confidence="low",
            days_remaining=None,
            velocity_per_day=velocity.per_day,
            note="Too few data points for a reliable forecast (need ≥ 3).",
        )

    days_needed = math.ceil(remaining / velocity.per_day)
    forecast_date = date.today() + timedelta(days=days_needed)

    # Adjust confidence downward if forecast is very far out (>180 days)
    confidence = velocity.confidence
    if days_needed > 180 and confidence == "high":
        confidence = "medium"
    if days_needed > 365:
        confidence = "low"

    note = f"Based on {velocity.data_points} data points over {velocity.window_days} days."
    if target_date and forecast_date > target_date:
        days_late = (forecast_date - target_date).days
        note += f" Forecast is {days_late} day(s) beyond the target date — at risk."

    return ForecastResult(
        forecast_date=forecast_date,
        confidence=confidence,
        days_remaining=days_needed,
        velocity_per_day=velocity.per_day,
        note=note,
    )
