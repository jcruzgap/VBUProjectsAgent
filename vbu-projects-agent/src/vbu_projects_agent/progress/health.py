"""Health scoring: green / yellow / red from progress + risk modifiers."""
from __future__ import annotations

from typing import Literal

from ..config.models import HealthThresholds

HealthColor = Literal["green", "yellow", "red"]


def compute_health(
    overall_percent: float,
    thresholds: HealthThresholds,
    open_high_risks: int = 0,
    negative_velocity: bool = False,
    has_blockers: bool = False,
) -> tuple[HealthColor, list[str]]:
    """
    Return (color, reasons_list).
    Base health from thresholds; modifiers can downgrade it.
    """
    reasons: list[str] = []

    # Base from progress
    if overall_percent >= thresholds.green:
        base: HealthColor = "green"
    elif overall_percent >= thresholds.yellow:
        base = "yellow"
    else:
        base = "red"

    color = base

    # Modifiers (can only downgrade)
    if has_blockers:
        reasons.append("Active blockers present")
        if color == "green":
            color = "yellow"

    if open_high_risks > 0:
        reasons.append(f"{open_high_risks} open high-severity risk(s)")
        if color == "green":
            color = "yellow"
        if open_high_risks >= 3 and color != "red":
            color = "red"

    if negative_velocity:
        reasons.append("Velocity trend is negative")
        if color == "green":
            color = "yellow"

    if not reasons:
        pct_display = f"{overall_percent * 100:.1f}%"
        if color == "green":
            reasons.append(f"On track at {pct_display} progress")
        elif color == "yellow":
            reasons.append(f"Below target — {pct_display} progress")
        else:
            reasons.append(f"Significantly behind — {pct_display} progress")

    return color, reasons
