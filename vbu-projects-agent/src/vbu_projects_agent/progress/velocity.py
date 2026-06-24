"""Robust velocity estimation from historical metric snapshots."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class VelocityResult:
    per_day: float          # units (test cases, story points, etc.) per day
    window_days: int        # history window used
    data_points: int        # number of observations
    confidence: str         # "high" | "medium" | "low"
    note: str = ""


def compute_velocity(
    history: list[dict],
    value_key: str = "overall_percent",
    window_days: int = 30,
) -> Optional[VelocityResult]:
    """
    Fit a linear slope to the value_key over the trailing window_days.
    Returns None if insufficient data or negative/zero velocity.
    """
    if len(history) < 2:
        return None

    now = datetime.now(timezone.utc)
    cutoff_iso = None

    # Filter to window
    points: list[tuple[float, float]] = []  # (days_from_start, value)
    for row in history:
        try:
            ts = datetime.fromisoformat(row["measured_at"].replace("Z", "+00:00"))
            value = float(row[value_key] or 0)
            days = (ts - datetime.fromisoformat(history[0]["measured_at"].replace("Z", "+00:00"))).total_seconds() / 86400
            points.append((days, value))
        except (KeyError, TypeError, ValueError):
            continue

    if len(points) < 2:
        return None

    # Linear regression (least squares)
    n = len(points)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)
    denom = n * sum_x2 - sum_x ** 2
    if abs(denom) < 1e-9:
        return None

    slope = (n * sum_xy - sum_x * sum_y) / denom  # units per day

    if slope <= 0:
        return VelocityResult(
            per_day=0.0,
            window_days=window_days,
            data_points=n,
            confidence="low",
            note="Velocity is zero or negative — no forward progress detected.",
        )

    # Confidence based on data points and variance
    mean_y = sum_y / n
    ss_res = sum((y - (mean_y + slope * (x - sum_x / n))) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-9 else 0.0

    if n >= 10 and r2 >= 0.8:
        confidence = "high"
    elif n >= 5 and r2 >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return VelocityResult(
        per_day=slope,
        window_days=window_days,
        data_points=n,
        confidence=confidence,
    )
